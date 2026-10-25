"""Integração local com SQLite real e fronteiras Windows/HTTP simuladas."""
import base64
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import time
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import admin_scripts
import video_insights


class SimulatedOperations(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.stack.enter_context(patch.object(app, 'DB', Path(temp)/'test.db'))
        self.stack.enter_context(patch.object(app, 'IMAGE_DIR', Path(temp)))
        self.stack.enter_context(patch.object(app, 'WIN', True))
        # Tripwires: no OS process, corporate socket or external HTTP may escape.
        for owner, name in [(app.subprocess,'Popen'), (app.subprocess,'run'),
                            (app.socket,'create_connection'), (app,'build_opener'),
                            (app.integrations,'build_opener')]:
            self.stack.enter_context(patch.object(owner,name,side_effect=AssertionError('External I/O forbidden')))
        app.initialize()
        app.save_machine('PC-SIM')
        app.save_machine('PRN-SIM')
        with app.db() as c:
            c.execute("UPDATE machines SET device_type='computer' WHERE target='PC-SIM'")
            c.execute("UPDATE machines SET device_type='printer' WHERE target='PRN-SIM'")
        self.h = object.__new__(app.Handler)
        self.h.send = MagicMock()
        self.h.error = MagicMock()
        self.h.local_host = lambda: True
        self.h.authorized = lambda: True
        self.h.server = SimpleNamespace(restore_previews={}, shutdown=MagicMock())

    def post(self, path, **body):
        self.h.send.reset_mock()
        self.h.handle_post(path, {'target':'PC-SIM', 'confirm':True, **body})
        call = self.h.send.call_args
        return call.kwargs.get('obj', call.args[1] if len(call.args)>1 else {}) if call else {}

    def get(self, path):
        self.h.send.reset_mock()
        self.h.path = path + ('&' if '?' in path else '?') + 'target=PC-SIM'
        self.h.handle_get()
        return self.h.send.call_args.kwargs.get('obj', {})

    def test_all_remote_read_routes_success_and_failure(self):
        routes = ['/api/admin/inventory','/api/admin/printers',
            '/api/diagnostics/disk-guided','/api/diagnostics/disk-100',
            '/api/diagnostics/performance','/api/diagnostics/zebra?printer=Zebra',
            '/api/diagnostics/updates','/api/diagnostics/services',
            '/api/diagnostics/network','/api/diagnostics/pinpad','/api/software/installed']
        routes += ['/api/scripts/run?key='+x['key'] for x in admin_scripts.catalog()]
        routes += ['/api/diagnostics/remote-console?type='+k for k in video_insights.SAFE_QUERIES]
        for route in routes:
            for failed in (False,True):
                with self.subTest(route=route,failed=failed), patch.object(app,'remote_script',
                        side_effect=RuntimeError('SIM denied') if failed else None,
                        return_value={'Host':'PC-SIM'}) as remote:
                    if failed:
                        with self.assertRaises(RuntimeError): self.get(route)
                    else:
                        self.assertTrue(self.get(route)['ok'])
                    self.assertEqual(remote.call_args.args[0], 'PC-SIM')
                    row=app.rows('SELECT * FROM audit ORDER BY id DESC LIMIT 1')[0]
                    self.assertEqual(row['success'], int(not failed))
                    self.assertEqual(row['target'], 'PC-SIM')

    def test_remote_mutation_routes_success_failure_and_confirmation(self):
        routes = [('/api/maintenance/flush-dns',{}),
            ('/api/maintenance/disk-service',{'service':'SysMain'}),
            ('/api/maintenance/tef-restart',{'service':'SiTef'}),
            ('/api/maintenance/restore-create',{'description':'SIM restore'}),
            ('/api/admin/clear-print',{'printer':'Zebra'}),
            ('/api/admin/spooler',{})]
        routes += [('/api/maintenance/disk-tool',{'tool':t}) for t in
                   ('dism-check','dism-repair','chkdsk-scan','sfc-scan')]
        for route,body in routes:
            with self.subTest(route=route,body=body), patch.object(app,'remote_script',return_value={'Codigo':0}) as remote:
                with self.assertRaises(ValueError): self.post(route,confirm=False,**body)
                remote.assert_not_called()
                self.assertTrue(self.post(route,**body)['ok'])
                self.assertEqual(remote.call_args.args[0], 'PC-SIM')
                remote.side_effect=RuntimeError('SIM denied')
                with self.assertRaises(RuntimeError): self.post(route,**body)
                self.assertEqual(app.rows('SELECT success FROM audit ORDER BY id DESC LIMIT 1')[0]['success'],0)

    def test_cleanup_partial_result_is_not_reported_as_success(self):
        for path in ('/api/maintenance/cleanup','/api/maintenance/quick-optimize'):
            for metrics in ({'Falhas':1}, {'LimiteAtingido':True}, {'Falhas':0,'LimiteAtingido':False}):
                with self.subTest(path=path,metrics=metrics):
                    result={'Limpeza':metrics} if path.endswith('quick-optimize') else metrics
                    with patch.object(app,'remote_script',return_value=result):
                        out=self.post(path,days=14)
                    expected=not(metrics.get('Falhas') or metrics.get('LimiteAtingido'))
                    self.assertEqual(out['ok'],expected)
                    self.assertEqual(app.rows('SELECT success FROM audit ORDER BY id DESC LIMIT 1')[0]['success'],int(expected))

    def test_rdp_and_terminal_reject_printers_before_launch(self):
        for route in ('/api/admin/rdp','/api/admin/terminal'):
            with self.subTest(route=route), patch.object(app.subprocess,'Popen') as launch:
                with self.assertRaises(ValueError): self.post(route,target='PRN-SIM')
                launch.assert_not_called()
                self.assertTrue(self.post(route)['ok'])
                self.assertIn('PC-SIM',str(launch.call_args))

    def test_restart_uses_selected_computer_and_blocks_printer(self):
        with patch.object(app,'ps_json',return_value={'Mensagem':'Reinício solicitado'}) as ps:
            with self.assertRaises(ValueError): self.post('/api/admin/restart',target='PRN-SIM')
            with self.assertRaises(ValueError): self.post('/api/admin/restart',confirm=False)
            ps.assert_not_called()
            self.assertTrue(self.post('/api/admin/restart')['ok'])
            self.assertIn(base64.b64encode(b'PC-SIM').decode(),ps.call_args.args[0])
            ps.side_effect=RuntimeError('SIM denied')
            with self.assertRaises(RuntimeError): self.post('/api/admin/restart')
            self.assertEqual(app.rows('SELECT success FROM audit ORDER BY id DESC LIMIT 1')[0]['success'],0)

    def test_zammad_transport_error_does_not_leak_details(self):
        opener=MagicMock()
        opener.open.side_effect=URLError('secret-token PRIVATE')
        with patch.dict(app.os.environ,{'FLEURY_ZAMMAD_URL':'https://example.test','FLEURY_ZAMMAD_TOKEN':'secret-token'}), patch.object(app,'build_opener',return_value=opener):
            with self.assertRaises(RuntimeError): self.post('/api/tickets/zammad-sync')
        logs=str(app.rows('SELECT * FROM audit'))
        self.assertNotIn('secret-token',logs)
        self.assertNotIn('PRIVATE',logs)

    def test_local_tickets_assets_images_and_dashboards(self):
        self.post('/api/tickets/create',title='Impressora simulada',sla_hours=4)
        ticket=self.get('/api/tickets')[0]
        self.post('/api/tickets/category',id=ticket['id'],category='Impressora Zebra')
        self.post('/api/tickets/update',id=ticket['id'],status='Resolvido')
        self.assertTrue(self.get('/api/tickets')[0]['resolved_at'])
        self.post('/api/tickets/update',id=ticket['id'],status='Aberto')
        self.assertFalse(self.get('/api/tickets')[0]['resolved_at'])
        self.post('/api/assets/update',asset_tag='SIM-01',owner='Ficticio')
        self.assertEqual(self.get('/api/assets/detail')['asset_tag'],'SIM-01')
        data=base64.b64encode(bytes.fromhex('89504e470d0a1a0a')+b'SIM').decode()
        self.post('/api/assets/upload',data=data,name='sim.png')
        ident=self.get('/api/assets/images')[0]['id']
        self.get('/api/assets/image?id='+str(ident))
        self.assertIn('payload',self.h.send.call_args.kwargs)
        self.post('/api/assets/delete-image',id=ident)
        self.assertEqual(self.get('/api/assets/images'),[])
        for path in ('/api/status','/api/analytics','/api/logs','/api/machines',
                     '/api/scripts/catalog','/api/software/catalog','/api/software/jobs',
                     '/api/integrations/status','/api/tickets/export'):
            with self.subTest(path=path):
                self.get(path)
                self.h.send.assert_called_once()

    def test_discovery_routes_are_simulated(self):
        for mode,callback,body in [('neighbors','scan_neighbors',{}),
                ('segments','scan_segments',{'segments':['192.168.1.0/24']}),
                ('subnet','scan_subnet',{'cidr':'192.168.1.0/24'}),
                ('local','scan_segments',{})]:
            with self.subTest(mode=mode), patch.object(app,callback,return_value={'found':1}), patch.object(app,'local_segments',return_value=['192.168.1.0/24']):
                self.assertEqual(self.post('/api/machines/scan',mode=mode,**body)['found'],1)
        with patch.object(app,'ping_one',return_value=True):
            self.assertTrue(self.post('/api/machines/verify')['online'])

    def test_zebra_catalog_print_and_timeout(self):
        with patch.object(app.integrations,'api',return_value=[{'id':'p1','name':'Sim'}]):
            self.assertEqual(self.get('/api/zebra/catalog')['result']['printers'][0]['id'],'p1')
        with patch.object(app.integrations,'zpl_list',side_effect=lambda kind:[{'id':'p1' if kind=='printer' else 'l1'}]), patch.object(app.integrations,'api',return_value={'success':True}) as api:
            body={'printer':'p1','label':'l1','data':{'text':'PRIVATE_LABEL'}}
            self.assertTrue(self.post('/api/zebra/print',**body)['ok'])
            api.reset_mock()
            api.side_effect=RuntimeError('Serviço indisponível')
            with self.assertRaises(RuntimeError): self.post('/api/zebra/print',**body)
            api.assert_called_once()
        self.assertNotIn('PRIVATE_LABEL',str(app.rows('SELECT * FROM audit')))

    def test_original_winutil_simulated_launch(self):
        with patch.object(app.integrations,'launch_winutil',return_value={'message':'SIM local'}) as launch:
            with self.assertRaises(ValueError): self.post('/api/winutil/launch',confirm=False)
            launch.assert_not_called()
            self.assertTrue(self.post('/api/winutil/launch')['ok'])
            self.assertEqual(app.rows('SELECT target FROM audit ORDER BY id DESC LIMIT 1')[0]['target'],'Estação local')
            launch.side_effect=RuntimeError('SIM policy blocked')
            with self.assertRaises(RuntimeError): self.post('/api/winutil/launch')

    def test_software_install_and_uninstall_queue_routes(self):
        for operation in ('install','uninstall'):
            with self.subTest(operation=operation), patch.object(app.SOFTWARE_MANAGER,'submit',return_value={'job_id':'SIM'}) as submit:
                out=self.post('/api/software/'+operation,packages=['7zip'])
                self.assertEqual(self.h.send.call_args.args[0],202)
                self.assertEqual(out['scope'],'machine')
                submit.assert_called_once_with('PC-SIM',operation,['7zip'],['7zip.7zip'])

    def test_machine_registration_classification_and_shutdown(self):
        self.post('/api/machines/add',target='PC-SECOND',name='Segundo ficticio')
        self.post('/api/machines/classify',target='PC-SECOND',device_type='computer')
        app.require_computer('PC-SECOND')
        with patch.object(app.threading,'Thread') as thread:
            self.post('/api/system/shutdown')
            thread.return_value.start.assert_called_once()

    def test_csv_import_updates_without_duplicates(self):
        csv='numero;titulo;status\nSIM1;Teste ficticio;Aberto\n'
        self.assertEqual(self.post('/api/tickets/import',csv=csv)['created'],1)
        self.assertEqual(self.post('/api/tickets/import',csv=csv)['updated'],1)
        self.assertEqual(len(self.get('/api/tickets')),1)

    def test_zammad_pagination_limit_and_reimport(self):
        opener=MagicMock()
        def response(request,timeout):
            page=int(request.full_url.rsplit('=',1)[1])
            result=MagicMock()
            result.__enter__.return_value=result
            result.status=200
            result.read.return_value=json.dumps([{'id':page*100+i,'title':'SIM',
                'state':{'name':'custom-state'},'priority':{'name':'high'}} for i in range(100)]).encode()
            return result
        opener.open.side_effect=response
        with patch.dict(app.os.environ,{'FLEURY_ZAMMAD_URL':'https://example.test','FLEURY_ZAMMAD_TOKEN':'secret-token'}), patch.object(app,'build_opener',return_value=opener):
            out=self.post('/api/tickets/zammad-sync')
            self.assertEqual(out['created'],300)
            self.assertTrue(out['possibly_truncated'])
            self.assertEqual(opener.open.call_count,3)
            self.assertEqual(self.post('/api/tickets/zammad-sync')['updated'],300)
        self.assertEqual(len(self.get('/api/tickets')),300)
        self.assertEqual(self.get('/api/tickets')[0]['status'],'Aberto')

    def test_slow_computer_and_jammed_printer_stateful_recovery(self):
        state={'jobs':3,'spooler':'Stopped','reads':0}
        def simulated_remote(target,script,*args,**kwargs):
            self.assertEqual(target,'PC-SIM')
            time.sleep(.02)  # Delayed transport; never runs PowerShell.
            state['reads']+=1
            if 'Remove-PrintJob' in script:
                count=state['jobs'];state['jobs']=0
                return {'Impressora':'Zebra','Removidos':count}
            if 'Restart-Service -Name Spooler' in script:
                state['spooler']='Running';return {'Spooler':'Running'}
            if 'Get-Printer' in script:
                return [{'Name':'Zebra','PrinterStatus':'Error' if state['jobs'] else 'Normal','Jobs':state['jobs']}]
            return {'CPUPercent':98,'MemoriaLivreMB':128,'DiscoAtivoPercent':100,'Simulado':True}
        with patch.object(app,'remote_script',side_effect=simulated_remote):
            self.assertEqual(self.get('/api/diagnostics/performance')['result']['CPUPercent'],98)
            self.assertEqual(self.get('/api/admin/printers')['result'][0]['PrinterStatus'],'Error')
            self.assertEqual(self.post('/api/admin/clear-print',printer='Zebra')['result']['Removidos'],3)
            self.assertEqual(self.post('/api/admin/spooler')['result']['Spooler'],'Running')
            self.assertEqual(self.get('/api/admin/printers')['result'][0]['PrinterStatus'],'Normal')
        self.assertEqual(state['reads'],5)

    def test_timeout_and_native_failure_are_not_success(self):
        for path,body in [('/api/admin/spooler',{}),('/api/admin/clear-print',{'printer':'Zebra'}),('/api/maintenance/disk-tool',{'tool':'sfc-scan'})]:
            with self.subTest(path=path),patch.object(app,'remote_script',side_effect=RuntimeError('Tempo limite simulado; estado remoto desconhecido')):
                with self.assertRaises(RuntimeError):self.post(path,**body)
                self.assertEqual(app.rows('SELECT success FROM audit ORDER BY id DESC LIMIT 1')[0]['success'],0)
        with patch.object(app,'remote_script',return_value={'Codigo':1,'Saida':'Falha simulada'}):
            self.assertFalse(self.post('/api/maintenance/disk-tool',tool='sfc-scan')['ok'])

    def test_slow_software_queue_does_not_block_other_computer(self):
        import software_jobs
        entered,release,other=threading.Event(),threading.Event(),threading.Event()
        def execute(target,operation,ids):
            if target=='PC-SIM':entered.set();release.wait(3)
            else:other.set()
            return {'Instalacoes':[{'CodigoSaida':0}]}
        manager=software_jobs.Manager(app.db,app.audit,app.now,execute)
        try:
            manager.submit('PC-SIM','install',['7zip'],['7zip.7zip'])
            self.assertTrue(entered.wait(2))
            manager.submit('PC-SECOND','install',['7zip'],['7zip.7zip'])
            self.assertTrue(other.wait(2))
            self.assertTrue(any(j['state']=='running' for j in manager.list()))
        finally:
            release.set();manager.pool.shutdown(wait=True)
        self.assertTrue(all(j['state']=='succeeded' for j in manager.list()))


if __name__ == '__main__': unittest.main()
