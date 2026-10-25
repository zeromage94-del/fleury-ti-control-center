"""Diagnóstico de impressão e catálogo local revisado de drivers Zebra.

Não baixa drivers, não envia ZPL e não instala pacotes. A troca usa somente um
driver já instalado no computador selecionado e aprovado no catálogo local.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

OFFICIAL_URL = 'https://www.zebra.com/us/en/support-downloads.html'


def validate_printer(value):
    if (not isinstance(value, str) or not 1 <= len(value.strip()) <= 150
            or any(ord(c) < 32 or c in '*?[]' for c in value)):
        raise ValueError('Selecione o nome exato de uma impressora, sem curingas.')
    return value.strip()


def _text(value, label, maximum=150):
    if (not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum
            or any(ord(c) < 32 for c in value)):
        raise ValueError('Campo inválido no catálogo de drivers: ' + label)
    return value.strip()


def _regular_file(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('Use caminho relativo com / para o arquivo INF.')
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts or ':' in relative:
        raise ValueError('O INF deve permanecer dentro do repositório local.')
    current = root
    for part in rel.parts:
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Links e reparse points não são permitidos no repositório.')
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError('Arquivo do driver fora do repositório ou inválido.')
    return resolved


def driver_catalog(repository=None):
    """Lê manifest.json local; metadados installed-only dispensam INF.

    Cada entrada precisa declarar reviewed=true. Se um INF for cadastrado, seu
    SHA256 é obrigatório e conferido a cada leitura. Isso verifica o inventário
    local; não substitui a assinatura do pacote de um fabricante no Windows.
    """
    location = repository or os.environ.get('FLEURY_ZEBRA_DRIVER_REPOSITORY', '')
    result = {'configured': bool(location), 'packages': [], 'official_url': OFFICIAL_URL,
              'note': 'Catálogo local revisado; a troca usa drivers já instalados no alvo. '
                      'Obtenha drivers oficiais para cada modelo/SO e valide a assinatura no Windows. '
                      'Não há download, instalação ou coleção completa de drivers embutida.'}
    if not location:
        return result
    root = Path(location)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Configure um diretório local válido para o repositório Zebra.')
    root = root.resolve(strict=True)
    try:
        manifest = _regular_file(root, 'manifest.json')
        if manifest.stat().st_size > 1024 * 1024:
            raise ValueError('Manifesto de drivers excede 1 MB.')
        data = json.loads(manifest.read_text('utf-8'))
        entries = data.get('packages') if isinstance(data, dict) else None
        if not isinstance(entries, list) or len(entries) > 500:
            raise ValueError('Manifesto deve conter packages com até 500 entradas.')
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict) or entry.get('reviewed') is not True:
                raise ValueError('Cada driver precisa estar explicitamente revisado (reviewed=true).')
            ident = _text(entry.get('id'), 'id', 64)
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', ident) or ident.casefold() in seen:
                raise ValueError('Identificador de driver inválido ou duplicado.')
            seen.add(ident.casefold())
            name = _text(entry.get('driver_name'), 'driver_name')
            if not re.search(r'Zebra|ZDesigner', name, re.I) or any(c in name for c in '*?[]'):
                raise ValueError('Cadastre somente nomes exatos de drivers Zebra/ZDesigner.')
            models = entry.get('models')
            if not isinstance(models, list) or not 1 <= len(models) <= 50:
                raise ValueError('Informe modelos compatíveis para cada driver Zebra.')
            models = [_text(model, 'models', 60) for model in models]
            if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 ._-]{1,59}', m) for m in models):
                raise ValueError('Use modelos específicos, sem curingas ou expressões regulares.')
            package = {'id': ident, 'title': _text(entry.get('title', name), 'title'),
                       'models': models, 'driver_name': name,
                       'reviewed': True,
                       'version': _text(entry.get('version', 'Não informada'), 'version', 60),
                       'package_present': False, 'verified': False}
            inf, checksum = entry.get('inf'), entry.get('sha256')
            if inf is not None or checksum is not None:
                if not isinstance(checksum, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', checksum):
                    raise ValueError('Informe o SHA256 do INF cadastrado.')
                file = _regular_file(root, inf)
                if file.suffix.lower() != '.inf' or file.stat().st_size > 16 * 1024 * 1024:
                    raise ValueError('Arquivo INF inválido ou acima de 16 MB.')
                digest = hashlib.sha256()
                with file.open('rb') as stream:
                    for block in iter(lambda: stream.read(65536), b''):
                        digest.update(block)
                if digest.hexdigest() != checksum.lower():
                    raise ValueError('SHA256 divergente para o INF do driver ' + ident)
                package.update(package_present=True, verified=True, sha256=checksum.lower())
            result['packages'].append(package)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Não foi possível ler o catálogo local de drivers Zebra.') from exc
    return result


def _call(remote_script, target, script, config=None, timeout=65):
    return remote_script(target, script, timeout, json.dumps(config or {}, ensure_ascii=False))


# Nomes de filas são comparados literalmente depois da consulta. Metadados de
# documentos/usuários nunca são retornados. A conexão TCP não envia conteúdo.
DIAGNOSTICS_PS = r'''param($json)
$ErrorActionPreference='Stop'
$cfg=$json | ConvertFrom-Json
$name=[string]$cfg.printer
$p=Get-Printer -Name $name -ErrorAction Stop
if(-not [string]::Equals([string]$p.Name,$name,[StringComparison]::OrdinalIgnoreCase)){throw 'Nome de impressora divergente.'}
$jobs=@(Get-PrintJob -PrinterName $p.Name -ErrorAction Stop)
$spooler=Get-Service Spooler -ErrorAction Stop
$port=Get-PrinterPort -Name $p.PortName -ErrorAction Stop
$wmi=@(Get-CimInstance Win32_Printer -ErrorAction Stop | Where-Object {$_.Name -eq $p.Name})
$offline=$false; $detected=0
if($wmi.Count -eq 1){$offline=[bool]$wmi[0].WorkOffline;$detected=[int]$wmi[0].DetectedErrorState}
$addr=[string]$port.PrinterHostAddress
$tcp='Não aplicável'; $portNumber=9100
if($port.PortNumber){$portNumber=[int]$port.PortNumber}
if($addr -and $portNumber -ge 1 -and $portNumber -le 65535){
 $client=New-Object Net.Sockets.TcpClient
 try{
  $pending=$client.BeginConnect($addr,$portNumber,$null,$null)
  if($pending.AsyncWaitHandle.WaitOne(1700,$false)){
   try{$client.EndConnect($pending);$tcp='Conexão TCP estabelecida'}catch{$tcp='Porta indisponível'}
  }else{$tcp='Tempo limite TCP'}
 }catch{$tcp='Porta indisponível'}finally{$client.Close()}
}
[PSCustomObject]@{
 Nome=$p.Name; Driver=$p.DriverName; Porta=$p.PortName
 StatusWindows=[string]$p.PrinterStatus; Offline=$offline; ErroDetectado=$detected
 Spooler=$spooler.Status.ToString(); TrabalhosNaFila=$jobs.Count
 FalhasFila=@($jobs | Where-Object {[string]$_.JobStatus -match 'Error|Offline|PaperOut|Blocked|UserIntervention'}).Count
 EnderecoIP=$addr; TesteTCP=$tcp
 Zebra=([string]$p.DriverName -match 'Zebra|ZDesigner' -or [string]$p.Name -match 'Zebra|\bZ[DT]\d|\bG[CKX]\d')
}'''


CLEAR_QUEUE_PS = r'''param($json)
$ErrorActionPreference='Stop'
$cfg=$json | ConvertFrom-Json
$name=[string]$cfg.printer
$p=Get-Printer -Name $name -ErrorAction Stop
if(-not [string]::Equals([string]$p.Name,$name,[StringComparison]::OrdinalIgnoreCase)){throw 'Nome de impressora divergente.'}
$jobs=@(Get-PrintJob -PrinterName $p.Name -ErrorAction Stop)
$removed=0; $failed=0
foreach($job in $jobs){
 try{Remove-PrintJob -PrinterName $p.Name -ID $job.ID -ErrorAction Stop;$removed++}catch{$failed++}
}
$remaining=@(Get-PrintJob -PrinterName $p.Name -ErrorAction Stop)
[PSCustomObject]@{Impressora=$p.Name;Encontrados=$jobs.Count;Removidos=$removed;
 Restantes=$remaining.Count;Falhas=$failed;Spooler=(Get-Service Spooler -ErrorAction Stop).Status.ToString()}
'''


RESTART_SPOOLER_PS = r'''param($json)
$ErrorActionPreference='Stop'
$service=Get-Service Spooler -ErrorAction Stop
$before=$service.Status.ToString()
Restart-Service -InputObject $service -Force -ErrorAction Stop
$service.WaitForStatus([ServiceProcess.ServiceControllerStatus]::Running,[TimeSpan]::FromSeconds(20))
$service.Refresh()
[PSCustomObject]@{SpoolerAntes=$before;Spooler=$service.Status.ToString()}
'''


INSTALLED_DRIVERS_PS = r'''param($json)
$ErrorActionPreference='Stop'
@(Get-PrinterDriver -ErrorAction Stop | Where-Object {$_.Name -match 'Zebra|ZDesigner'} |
 Select-Object Name,Manufacturer,MajorVersion,PrinterEnvironment)
'''


SWITCH_DRIVER_PS = r'''param($json)
$ErrorActionPreference='Stop'
$cfg=$json | ConvertFrom-Json
$name=[string]$cfg.printer; $new=[string]$cfg.driver_name
$p=Get-Printer -Name $name -ErrorAction Stop
if(-not [string]::Equals([string]$p.Name,$name,[StringComparison]::OrdinalIgnoreCase)){throw 'Nome de impressora divergente.'}
if([string]$p.DriverName -notmatch 'Zebra|ZDesigner' -and [string]$p.Name -notmatch 'Zebra|\bZ[DT]\d|\bG[CKX]\d'){throw 'Impressora não reconhecida como Zebra.'}
if($new -notmatch 'Zebra|ZDesigner'){throw 'Driver não é Zebra/ZDesigner.'}
$compatible=$false
foreach($model in @($cfg.models)){
 $pattern='(?i)(?<![a-z0-9])'+[regex]::Escape([string]$model)+'(?![a-z0-9])'
 if(([string]$p.Name+' '+[string]$p.DriverName) -match $pattern){$compatible=$true}
}
if(-not $compatible){throw 'Modelo da impressora não corresponde ao catálogo revisado.'}
$driver=Get-PrinterDriver -Name $new -ErrorAction Stop
if(-not [string]::Equals([string]$driver.Name,$new,[StringComparison]::OrdinalIgnoreCase)){throw 'Driver exato não instalado no alvo.'}
if((Get-Service Spooler -ErrorAction Stop).Status -ne 'Running'){throw 'Spooler não está em execução.'}
if(@(Get-PrintJob -PrinterName $p.Name -ErrorAction Stop).Count -gt 0){throw 'Fila contém trabalhos. Trate a fila antes de trocar o driver.'}
$before=[string]$p.DriverName
Set-Printer -Name $p.Name -DriverName $driver.Name -ErrorAction Stop
$after=Get-Printer -Name $p.Name -ErrorAction Stop
[PSCustomObject]@{Impressora=$p.Name;DriverAnterior=$before;DriverAtual=[string]$after.DriverName}
'''


def assess_diagnostics(snapshot):
    """Interpreta observações Windows; não promete detectar defeito físico."""
    if not isinstance(snapshot, dict) or not snapshot.get('Nome'):
        raise RuntimeError('Diagnóstico da impressora retornou resposta inválida.')
    result = dict(snapshot)
    issues = []
    def issue(code, message):
        issues.append({'code': code, 'severity': 'warning', 'message': message})
    if snapshot.get('Spooler') != 'Running':
        issue('spooler_stopped', 'Spooler parado ou indisponível; verificar serviço antes de imprimir.')
    if snapshot.get('Offline') or str(snapshot.get('StatusWindows', '')).lower() in ('offline', 'error'):
        issue('printer_offline', 'Windows informa impressora offline/com erro; conferir alimentação, rede e porta.')
    detected = snapshot.get('ErroDetectado')
    errors = {3: ('supply_low', 'Suprimento baixo; conferir consumíveis.'),
              4: ('paper_out', 'Sem papel/mídia; conferir alimentação e sensor.'),
              5: ('toner_low', 'Pouco toner; conferir suprimento.'),
              6: ('toner_out', 'Sem toner; conferir suprimento.'),
              7: ('cover_open', 'Tampa aberta; conferir travamento da tampa.'),
              8: ('paper_jam', 'Papel/mídia atolado; seguir procedimento do fabricante.'),
              9: ('printer_offline', 'Dispositivo informa estado offline.'),
              11: ('output_bin_full', 'Bandeja de saída cheia.')}
    if detected in errors:
        issue(*errors[detected])
    if snapshot.get('FalhasFila', 0):
        issue('queue_error', 'Há trabalhos com erro/bloqueados na fila selecionada.')
    if snapshot.get('TesteTCP') in ('Porta indisponível', 'Tempo limite TCP'):
        issue('network_unreachable', 'Porta de impressão indisponível; verificar IP, rede e conectividade.')
    if snapshot.get('Zebra'):
        result['guidance'] = [
            'Etiquetas em branco/cortadas/desalinhadas: conferir mídia/ribbon, largura, altura, DPI e linguagem ZPL/EPL no driver.',
            'Gap/marca preta, escuridão, velocidade e calibração dependem do modelo; seguir manual Zebra e fazer homologação.',
            'Trocar driver não resolve cabeça de impressão, sensor, rolete ou ribbon defeituoso. Nenhum comando de calibração foi enviado.']
    else:
        result['guidance'] = ['Conferir papel, toner/tinta, tampa, atolamentos, porta e driver do fabricante antes de repetir a impressão.']
    result.update(issues=issues, healthy=not issues,
                  note='Estado observado no Windows/rede; não comprova saída física nem qualidade de impressão. Nenhum documento foi enviado.')
    return result


def diagnose(remote_script, target, printer):
    return assess_diagnostics(_call(remote_script, target, DIAGNOSTICS_PS,
                                   {'printer': validate_printer(printer)}))


def clear_queue(remote_script, target, printer):
    result = _call(remote_script, target, CLEAR_QUEUE_PS,
                   {'printer': validate_printer(printer)}, timeout=45)
    if not isinstance(result, dict) or any(type(result.get(k)) is not int or result[k] < 0
            for k in ('Encontrados', 'Removidos', 'Restantes', 'Falhas')):
        raise RuntimeError('Limpeza da fila retornou resposta inválida; confira o estado antes de repetir.')
    result = dict(result)
    ok = result['Restantes'] == 0 and result['Falhas'] == 0 and result.get('Spooler') == 'Running'
    result.update(ok=ok, partial=not ok,
                  message='Fila selecionada vazia; confirme a impressão física.' if ok else
                          'Fila não foi recuperada completamente; confira trabalhos restantes e Spooler antes de repetir.')
    return result


def restart_spooler(remote_script, target):
    result = _call(remote_script, target, RESTART_SPOOLER_PS, timeout=60)
    if not isinstance(result, dict) or not isinstance(result.get('Spooler'), str):
        raise RuntimeError('Reinício do Spooler retornou resposta inválida.')
    result = dict(result)
    result.update(ok=result['Spooler'] == 'Running', partial=result['Spooler'] != 'Running',
                  message='Spooler em execução; filas e saída física ainda precisam ser verificadas.'
                          if result['Spooler'] == 'Running' else 'Spooler não voltou ao estado Running.')
    return result


def installed_drivers(remote_script, target):
    result = _call(remote_script, target, INSTALLED_DRIVERS_PS)
    if result is None:
        return []
    if isinstance(result, dict):
        result = [result]
    if not isinstance(result, list) or any(not isinstance(x, dict) or not isinstance(x.get('Name'), str) for x in result):
        raise RuntimeError('Lista de drivers instalados inválida.')
    return result


def switch_driver(remote_script, target, printer, driver_id, repository=None):
    printer = validate_printer(printer)
    packages = driver_catalog(repository)['packages']
    entry = next((x for x in packages if x['id'] == driver_id), None)
    if entry is None:
        raise ValueError('Selecione um driver do catálogo local revisado.')
    result = _call(remote_script, target, SWITCH_DRIVER_PS,
                   {'printer': printer, 'driver_name': entry['driver_name'], 'models': entry['models']}, timeout=90)
    if not isinstance(result, dict) or not result.get('DriverAtual'):
        raise RuntimeError('Troca de driver retornou resposta inválida; verifique o driver atual antes de repetir.')
    result = dict(result)
    ok = result['DriverAtual'].casefold() == entry['driver_name'].casefold()
    result.update(ok=ok, partial=not ok, driver_id=entry['id'],
                  message='Driver selecionado aplicado; validar tamanho, DPI, mídia e impressão física.' if ok else
                          'O driver atual não corresponde ao solicitado; confira a fila antes de tentar novamente.')
    return result
