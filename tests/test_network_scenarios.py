"""Laboratório stateful: HTTP/SQLite reais, rede e Windows exclusivamente simulados.

O adaptador abaixo modela efeitos de operações para testar o encadeamento do
produto. Ele não executa os scripts PowerShell e não substitui homologação de
Windows, firmware, mídia ou hardware. Qualquer I/O externo não previsto falha.
"""
from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import maintenance
import software_catalog
import software_jobs


class CorporateLab:
    """Equipamentos fictícios, com permissões, filas e arquivos persistentes."""

    def __init__(self, root):
        self.root = root
        self.lock = threading.RLock()
        self.calls = []
        self.attempted_hosts = set()
        self.hosts = {
            '10.77.0.1': dict(kind='computer', ports={5985, 445}, ping=False,
                            online=True, admin=True, winget=True, installed=set()),
            '10.77.0.2': dict(kind='printer', ports={9100}, ping=False, online=True),
            '10.77.0.3': dict(kind='printer', ports={631, 9100}, ping=False, online=True),
            '10.77.0.4': dict(kind='computer', ports=set(), ping=False,
                            online=False, admin=True, winget=True, installed=set()),
            '10.77.0.5': dict(kind='computer', ports={5985}, ping=True,
                            online=True, admin=False, winget=True, installed=set()),
            '10.77.0.6': dict(kind='computer', ports={5985}, ping=True,
                            online=True, admin=True, winget=False, installed=set()),
        }
        self.printers = {
            'Laser corporativa': dict(driver='Universal PCL 6', jobs=[1, 2, 3],
                                     error=8, status='Error', ip='10.77.0.2', zebra=False),
            'Zebra ZD421': dict(driver='ZDesigner ZD421-203dpi ZPL', jobs=[7, 8],
                               error=4, status='Error', ip='10.77.0.3', zebra=True),
        }
        self.spooler = 'Running'
        self.queue_locked = False
        self.spooler_starts = True
        self.blocked_packages = set()
        self.busy = set()
        self.files = []
        for profile, name, size, busy in (
                ('alice', 'old-cache.tmp', 4096, False),
                ('bob', 'busy-cache.temp', 2048, True),
                ('alice', 'report.pdf', 1024, False)):
            path = root / 'profiles' / profile / 'Temp' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'x' * size)
            old = time.time() - 60 * 86400
            os.utime(path, (old, old))
            self.files.append(path)
            if busy:
                self.busy.add(path)
        self.download = root / 'profiles' / 'bob' / 'Downloads' / 'personal.pdf'
        self.download.parent.mkdir(parents=True)
        self.download.write_bytes(b'personal download, preserved')

    def ping(self, target):
        host = self.hosts.get(target, {})
        return bool(host.get('online') and host.get('ping'))

    def connect(self, real_connect, address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                source_address=None, **kwargs):
        target, port = address
        if target in ('127.0.0.1', 'localhost', '::1'):
            return real_connect(address, timeout, source_address, **kwargs)
        if target not in self.hosts:
            raise AssertionError('Rede externa proibida no laboratório: ' + str(target))
        with self.lock:
            self.attempted_hosts.add(target)
            host = self.hosts[target]
            if host['online'] and port in host['ports']:
                return MagicMock()
        raise TimeoutError('SIM: porta filtrada, host lento ou desligado')

    def cleanup(self, config):
        eligible = [path for path in self.files if path.exists()
                    and path.suffix in ('.tmp', '.temp')
                    and path.stat().st_mtime < time.time() - config['days'] * 86400]
        found_bytes = sum(path.stat().st_size for path in eligible)
        removed = freed = failures = 0
        if config.get('commit'):
            for path in eligible:
                if path in self.busy:
                    failures += 1
                    continue
                freed += path.stat().st_size
                path.unlink()
                removed += 1
        return dict(ArquivosElegiveis=len(eligible), PotencialMB=found_bytes / 1048576,
                    ArquivosRemovidos=removed, LiberadosMB=freed / 1048576,
                    Falhas=failures, LimiteAtingido=False, PerfisInspecionados=2)

    def execute(self, target, body, timeout=28, argument=None):
        """Única fronteira de WinRM: ações desconhecidas falham, sem fallback."""
        with self.lock:
            self.calls.append(dict(target=target, timeout=timeout))
            host = self.hosts.get(target)
            if not host or not host['online']:
                raise RuntimeError('SIM: computador sem resposta no WinRM')
            if host.get('winrm_timeout'):
                raise RuntimeError('SIM: tempo limite WinRM em computador lento')
            if host.get('kind') != 'computer':
                raise AssertionError('WinRM não pode ser dirigido a uma impressora')
            config = json.loads(argument) if argument else {}
            if body == maintenance.PERFORMANCE_PS:
                return dict(Host=target, MemoriaLivreGB=0.2, MemoriaTotalGB=4,
                            Discos=[dict(DeviceID='C:', LivreGB=1.5, TotalGB=128)],
                            PerfisLocais=2, Spooler=self.spooler,
                            Nota='SIM: pressão de memória; limpeza não garante desempenho.')
            if body in (maintenance.DISK_100_PS, software_catalog.DISK_GUIDED_PS):
                return dict(Computador=target, EspacoLivrePorcento=1.2,
                            EventosDisco=[dict(ID=153, Origem='disk')],
                            Recomendacoes=['SIM: verificar backup e saúde física do disco'])
            if body == maintenance.CLEANUP_PS:
                return self.cleanup(config)
            if body == maintenance.QUICK_OPTIMIZE_PS:
                return dict(Computador=target, Limpeza=self.cleanup(config),
                            SegurancaWindowsAlterada=False, ProgramasRemovidos=0)
            if body in (software_catalog.INSTALL_PS, software_catalog.UNINSTALL_PS):
                if not host.get('admin'):
                    raise RuntimeError('SIM: identidade WinRM sem privilégios administrativos')
                if not host.get('winget'):
                    raise RuntimeError('SIM: WinGet indisponível no contexto corporativo')
                install = body == software_catalog.INSTALL_PS
                results = []
                for package in config['packages']:
                    code = 5 if package in self.blocked_packages else 0
                    if not code:
                        if install:
                            host['installed'].add(package)
                        else:
                            host['installed'].discard(package)
                    results.append(dict(Pacote=package, CodigoSaida=code,
                                        Escopo='machine', Resultado='SIM: política' if code else 'SIM: concluído'))
                return dict(Computador=target, Escopo='machine',
                            **{'Instalacoes' if install else 'Desinstalacoes': results})
            if body == software_catalog.INVENTORY_PS:
                return dict(Computador=target, AplicativosPorMaquina=[
                    dict(DisplayName=package, Escopo='machine')
                    for package in sorted(host['installed'])])
            # Import tardio permite coleta do laboratório junto aos testes antigos.
            import printer_support
            if body == printer_support.DIAGNOSTICS_PS:
                printer = self.printers[config['printer']]
                return dict(Nome=config['printer'], Driver=printer['driver'], Porta='TCP_SIM',
                            StatusWindows=printer['status'], Offline=False,
                            ErroDetectado=printer['error'], Spooler=self.spooler,
                            TrabalhosNaFila=len(printer['jobs']), FalhasFila=0,
                            EnderecoIP=printer['ip'], TesteTCP='Conexão TCP estabelecida',
                            Zebra=printer['zebra'])
            if body == printer_support.CLEAR_QUEUE_PS:
                printer = self.printers[config['printer']]
                before = len(printer['jobs'])
                printer['jobs'] = printer['jobs'][-1:] if self.queue_locked else []
                return dict(Impressora=config['printer'], Encontrados=before,
                            Removidos=before - len(printer['jobs']),
                            Restantes=len(printer['jobs']), Falhas=int(self.queue_locked),
                            Spooler=self.spooler)
            if body == printer_support.RESTART_SPOOLER_PS:
                before = self.spooler
                self.spooler = 'Running' if self.spooler_starts else 'Stopped'
                return dict(SpoolerAntes=before, Spooler=self.spooler)
            if 'Get-Printer -ErrorAction Stop | Select-Object' in body:
                return [dict(Name=name, DriverName=info['driver'],
                             PrinterStatus=info['status'], Shared=True)
                        for name, info in self.printers.items()]
            raise AssertionError('Script não modelado pelo laboratório; não executar nativamente')


class CorporateNetworkScenarios(unittest.TestCase):
    """Fluxos sequenciais que observam estados e resultados por HTTP."""

    def setUp(self):
        self.evidence = []
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='fleury-lab-')))
        self.lab = CorporateLab(root)
        self.stack.enter_context(patch.object(app, 'DB', root / 'lab.db'))
        self.stack.enter_context(patch.object(app, 'IMAGE_DIR', root))
        self.stack.enter_context(patch.object(app, 'WIN', True))
        self.stack.enter_context(patch.object(app, 'remote_script', side_effect=self.lab.execute))
        self.stack.enter_context(patch.object(app, 'ping_one', side_effect=self.lab.ping))
        real_connect = socket.create_connection
        self.stack.enter_context(patch.object(socket, 'create_connection',
            side_effect=lambda address, *args, **kwargs: self.lab.connect(real_connect, address, *args, **kwargs)))
        for owner, name in ((app.subprocess, 'Popen'), (app.subprocess, 'run'),
                            (app, 'build_opener'), (app.integrations, 'build_opener')):
            self.stack.enter_context(patch.object(owner, name,
                side_effect=AssertionError('Processo/HTTP externo proibido no laboratório')))
        app.initialize()
        manager = software_jobs.Manager(app.db, app.audit, app.now, app.execute_software)
        self.stack.enter_context(patch.object(app, 'SOFTWARE_MANAGER', manager))
        self.stack.callback(manager.pool.shutdown, wait=True)
        self.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.server.cleanup_previews = {}
        self.server.restore_previews = {}
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.stack.callback(self.close_server)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        self.opener = build_opener(ProxyHandler({}))

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, path, body=None, authorized=True):
        headers = {'X-Fleury-Token': app.TOKEN if authorized else 'invalid'}
        payload = None if body is None else json.dumps(body).encode('utf-8')
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        request = Request(self.base + path, data=payload, headers=headers)
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            content_type = response.headers.get('Content-Type', '')
            return response.status, json.loads(data) if 'json' in content_type else data

    def expect(self, observed, expected, name):
        self.evidence.append(dict(name=name, status='passed' if observed == expected else 'failed',
                                  expected=expected, observed=observed))
        self.assertEqual(observed, expected, name)

    def register_computer(self, target='10.77.0.1'):
        self.expect(self.request('/api/machines/add', dict(target=target, name='Computador fictício'))[0],
                    200, 'cadastro do computador fictício')
        self.expect(self.request('/api/machines/classify', dict(target=target, device_type='computer'))[0],
                    200, 'classificação explícita como computador')

    def get_for(self, path, target='10.77.0.1', **params):
        return self.request(path + '?' + urlencode(dict(target=target, **params)))

    def post_for(self, path, target='10.77.0.1', **body):
        return self.request(path, dict(target=target, **body))

    def await_job(self, ident):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status, jobs = self.request('/api/software/jobs')
            self.assertEqual(status, 200)
            job = next(item for item in jobs if item['id'] == ident)
            if job['state'] not in ('queued', 'running'):
                return job
            time.sleep(0.01)
        self.fail('Fila simulada não terminou no prazo de 5 segundos')

    def test_discovery_ping_blocked_and_offline_status(self):
        self.register_computer('10.77.0.4')
        with app.db() as connection:
            connection.execute("UPDATE machines SET status='Online' WHERE target='10.77.0.4'")
        status, result = self.request('/api/machines/scan',
            dict(mode='segments', segments=['10.77.0.0/29']))
        self.expect(status, 200, 'descoberta autorizada via HTTP')
        self.expect(result['found'], 5, 'cinco equipamentos acessíveis mesmo com ICMP bloqueado')
        self.expect(sorted(self.lab.attempted_hosts), sorted(self.lab.hosts),
                    'todos seis endereços do segmento foram inspecionados')
        machines = {item['target']: item for item in self.request('/api/machines')[1]}
        self.expect(machines['10.77.0.1']['device_type'], 'computer', 'PC lento encontrado por TCP/WinRM')
        self.expect(machines['10.77.0.2']['device_type'], 'printer', 'impressora comum detectada por TCP')
        self.expect(machines['10.77.0.3']['device_type'], 'printer', 'Zebra detectada por TCP')
        self.expect(machines['10.77.0.4']['status'], 'Sem resposta', 'estado Online antigo invalidado')
        verified = self.post_for('/api/machines/verify', target='10.77.0.1')[1]
        self.expect(verified['online'], True, 'reverificação aceita TCP quando ICMP está bloqueado')
        self.lab.hosts['10.77.0.1']['online'] = False
        verified = self.post_for('/api/machines/verify', target='10.77.0.1')[1]
        self.expect(verified['online'], False, 'queda posterior não permanece Online')

    def test_slow_computer_cleanup_partial_then_recovery(self):
        self.register_computer()
        status, performance = self.get_for('/api/diagnostics/performance')
        self.expect(status, 200, 'diagnóstico de lentidão HTTP')
        self.expect(performance['result']['MemoriaLivreGB'], 0.2, 'pressão de memória preservada no resultado')
        self.expect(self.get_for('/api/diagnostics/disk-100')[1]['result']['EventosDisco'][0]['ID'],
                    153, 'erro de armazenamento exige investigação, não promessa de limpeza')
        self.expect(self.post_for('/api/maintenance/cleanup', days=14, confirm=False)[0],
                    400, 'limpeza sem confirmação bloqueada')
        status, result = self.post_for('/api/maintenance/cleanup', days=14, confirm=True)
        self.expect(status, 200, 'limpeza parcialmente executada retorna resultado HTTP')
        self.expect(result['ok'], False, 'arquivo ocupado impede falso sucesso')
        self.expect(result['partial'], True, 'resultado parcial explícito')
        self.expect(result['result']['ArquivosRemovidos'], 1, 'TEMP elegível removido no filesystem simulado')
        self.expect([path.exists() for path in self.lab.files], [False, True, True],
                    'arquivo ocupado e documento pessoal preservados')
        self.expect(self.lab.download.exists(), True, 'otimização TEMP não apaga Downloads')
        self.lab.busy.clear()
        result = self.post_for('/api/maintenance/quick-optimize', days=14, confirm=True)[1]
        self.expect(result['ok'], True, 'nova execução após liberar arquivo conclui limpeza')
        self.expect(result['result']['Limpeza']['ArquivosRemovidos'], 1, 'somente TEMP restante foi apagado')
        self.expect(result['result']['SegurancaWindowsAlterada'], False, 'proteção corporativa não alterada')
        self.expect(self.lab.files[2].exists(), True, 'documento pessoal permanece após otimização')

    def test_all_catalog_packages_install_inventory_and_uninstall(self):
        self.register_computer()
        catalog = self.request('/api/software/catalog')[1]['programs']
        self.assertGreater(len(catalog), 20, 'Cenário precisa exercitar mais de um lote')
        keys = [item['key'] for item in catalog]
        expected_ids = sorted(item['winget_id'] for item in catalog)
        for operation in ('install', 'uninstall'):
            for offset in range(0, len(keys), 20):
                batch = keys[offset:offset + 20]
                with self.subTest(operation=operation, batch=offset // 20 + 1):
                    status, queued = self.post_for('/api/software/' + operation, packages=batch)
                    self.expect(status, 202, operation + ': lote aceito sem modal adicional')
                    job = self.await_job(queued['job_id'])
                    self.expect(job['state'], 'succeeded', operation + ': fila concluiu lote machine')
                    results = job['result']['Instalacoes' if operation == 'install' else 'Desinstalacoes']
                    self.expect(len(results), len(batch), operation + ': resultado individual por pacote')
            inventory = self.get_for('/api/software/installed')[1]['result']['AplicativosPorMaquina']
            self.expect(sorted(item['DisplayName'] for item in inventory),
                        expected_ids if operation == 'install' else [],
                        operation + ': inventário reflete todos os efeitos da fila')
        self.expect(len(self.lab.hosts['10.77.0.1']['installed']), 0,
                    'todos pacotes foram desinstalados no modelo corporativo')

    def test_corporate_install_failures_and_partial_result(self):
        for target, reason in (('10.77.0.4', 'sem resposta'), ('10.77.0.5', 'administrativos'),
                               ('10.77.0.6', 'WinGet')):
            with self.subTest(target=target, reason=reason):
                self.register_computer(target)
                status, queued = self.post_for('/api/software/install', target=target, packages=['7zip'])
                self.expect(status, 202, 'falha corporativa é processada pela fila')
                job = self.await_job(queued['job_id'])
                self.expect(job['state'], 'failed', 'falha corporativa não vira sucesso: ' + reason)
                self.expect(reason in job['error'], True, 'motivo corporativo disponível ao técnico')
                self.expect(len(self.lab.hosts[target]['installed']), 0, 'nenhuma instalação indevida após bloqueio')
        self.register_computer()
        self.lab.hosts['10.77.0.1']['winrm_timeout'] = True
        queued = self.post_for('/api/software/install', packages=['7zip'])[1]
        job = self.await_job(queued['job_id'])
        self.expect(job['state'], 'failed', 'timeout em PC lento registrado como falha')
        self.expect('tempo limite' in job['error'], True, 'timeout distingue indisponibilidade do instalador')
        self.lab.hosts['10.77.0.1']['winrm_timeout'] = False
        self.lab.blocked_packages.add('Mozilla.Firefox')
        queued = self.post_for('/api/software/install', packages=['7zip', 'firefox'])[1]
        job = self.await_job(queued['job_id'])
        self.expect(job['state'], 'failed', 'instalação parcial não vira lote bem sucedido')
        self.expect([item['CodigoSaida'] for item in job['result']['Instalacoes']], [0, 5],
                    'códigos por pacote mantêm sucesso e bloqueio distintos')
        self.expect(sorted(self.lab.hosts['10.77.0.1']['installed']), ['7zip.7zip'],
                    'apenas o pacote permitido consta no estado do computador')

    def test_incident_asset_metrics_and_http_session(self):
        self.register_computer()
        self.expect(self.request('/api/status', authorized=False)[0], 403, 'API não aceita sessão inválida')
        self.post_for('/api/assets/update', asset_tag='LAB-001', location='Rede simulada', owner='Pessoa fictícia')
        detail = self.get_for('/api/assets/detail')[1]
        self.expect(detail['asset_tag'], 'LAB-001', 'patrimônio persiste no SQLite do laboratório')
        self.post_for('/api/tickets/create', title='Computador lento na rede simulada', category='Lentidão', sla_hours=4)
        ticket = self.request('/api/tickets')[1][0]
        self.expect(self.request('/api/analytics')[1]['pending'], 1, 'indicador registra chamado em aberto')
        self.request('/api/tickets/update', dict(id=ticket['id'], status='Resolvido'))
        metrics = self.request('/api/analytics')[1]
        self.expect(metrics['resolved'], 1, 'resolução atualiza indicador real')
        self.expect(metrics['sla_met'], 1, 'SLA usa datas reais da simulação')
        self.request('/api/tickets/update', dict(id=ticket['id'], status='Aberto'))
        self.expect(self.request('/api/analytics')[1]['resolved'], 0, 'reabertura não conserva resolução anterior')
        status, exported = self.request('/api/tickets/export')
        self.expect(status, 200, 'exportação CSV retorna conteúdo')
        self.expect(b'Computador lento' in exported, True, 'CSV inclui chamado fictício persistido')
        self.expect(len(self.request('/api/logs')[1]) > 0, True, 'auditoria registra cadeia de operações')

    def test_laser_and_zebra_queues_and_physical_faults(self):
        self.register_computer()
        for name, code in (('Laser corporativa', 8), ('Zebra ZD421', 4)):
            with self.subTest(printer=name):
                status, diagnostic = self.get_for('/api/printers/diagnose', printer=name)
                self.expect(status, 200, 'diagnóstico de impressora comum/Zebra por HTTP')
                self.expect(diagnostic['result']['ErroDetectado'], code, 'defeito físico permanece no diagnóstico')
                self.expect(diagnostic['result']['healthy'], False, 'papel preso/ausente não é saúde normal')
                self.expect(self.post_for('/api/admin/clear-print', printer=name, confirm=False)[0],
                            400, 'excluir trabalhos exige confirmação')
        self.lab.queue_locked = True
        status, cleared = self.post_for('/api/admin/clear-print', printer='Zebra ZD421', confirm=True)
        self.expect(status, 200, 'fila parcialmente removida retorna contadores')
        self.expect(cleared['ok'], False, 'trabalho retido impede falso sucesso')
        self.expect(cleared['result']['Restantes'], 1, 'trabalho bloqueado continua na fila')
        self.expect(self.lab.printers['Laser corporativa']['jobs'], [1, 2, 3],
                    'limpeza Zebra não remove fila da impressora comum')
        self.lab.queue_locked = False
        cleared = self.post_for('/api/admin/clear-print', printer='Zebra ZD421', confirm=True)[1]
        self.expect(cleared['ok'], True, 'fila selecionada conclui após liberar bloqueio')
        diagnostic = self.get_for('/api/printers/diagnose', printer='Zebra ZD421')[1]
        self.expect(diagnostic['result']['healthy'], False,
                    'fila vazia não corrige falta de mídia da Zebra')
        self.lab.printers['Zebra ZD421'].update(error=0, status='Normal')
        diagnostic = self.get_for('/api/printers/diagnose', printer='Zebra ZD421')[1]
        self.expect(diagnostic['result']['healthy'], True,
                    'reposição física simulada de mídia permite diagnóstico saudável')
        self.lab.spooler = 'Stopped'
        self.lab.spooler_starts = False
        restarted = self.post_for('/api/admin/spooler', confirm=True)[1]
        self.expect(restarted['ok'], False, 'spooler que continua parado não vira sucesso')
        self.lab.spooler_starts = True
        restarted = self.post_for('/api/admin/spooler', confirm=True)[1]
        self.expect(restarted['ok'], True, 'recuperação do spooler confirma estado Running')


if __name__ == '__main__':
    unittest.main(verbosity=2)
