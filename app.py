"""Fleury TI Control Center - MVP interno para Windows (Python 3.10+ / stdlib).
Servidor exclusivamente local. Ações remotas dependem de permissões já concedidas.
"""
import base64
import video_insights
import csv
import io
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import secrets
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse, urlsplit
import webbrowser
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
import maintenance
import insights
import software_catalog
import integrations
import admin_scripts

# Arquivos da aplicação empacotada podem ficar no diretório protegido _internal.
# Os dados reais nunca devem ser criados dentro desse diretório nem em Program Files.
APP = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
if getattr(sys, 'frozen', False):
    _binary_dir = Path(sys.executable).resolve().parent
    if (_binary_dir / 'PORTABLE_MODE').is_file():
        DATA = _binary_dir / 'data'
    else:
        DATA = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'FleuryTIControlCenter' / 'data'
else:
    DATA = APP / 'data'
DATA.mkdir(parents=True, exist_ok=True)
IMAGE_DIR = DATA / 'images'
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
CATEGORIES = ('Lentidão', 'Disco 100%', 'Impressora Zebra', 'PINPAD / TEF', 'Impressão geral', 'Rede', 'Sistema Windows', 'Outros', 'Não classificado')
DB = DATA / 'fleury_ti.db'
WIN = os.name == 'nt'
TOKEN = secrets.token_urlsafe(36)
LOCK = threading.RLock()
HOST_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,126}$')
STATUSES = {'Aberto', 'Em andamento', 'Pendente', 'Resolvido'}
PRIORITIES = {'Baixa', 'Média', 'Alta', 'Crítica'}


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


@contextmanager
def db():
    c = sqlite3.connect(DB, timeout=20)
    try:
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL')
        with c:
            yield c
    finally:
        c.close()


def initialize():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS machines(
          target TEXT PRIMARY KEY, name TEXT NOT NULL, mac TEXT DEFAULT '',
          status TEXT DEFAULT 'Não verificada', origin TEXT DEFAULT 'Manual',
          last_seen TEXT DEFAULT '', updated_at TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS tickets(
          id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT DEFAULT '',
          title TEXT NOT NULL, requester TEXT DEFAULT '', target TEXT DEFAULT '',
          priority TEXT DEFAULT 'Média', status TEXT DEFAULT 'Aberto',
          assigned TEXT DEFAULT '', origin TEXT DEFAULT 'Local',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS ticket_external ON tickets(origin, external_id)
          WHERE external_id != '';
        CREATE TABLE IF NOT EXISTS audit(
          id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, username TEXT,
          action TEXT NOT NULL, target TEXT, success INTEGER NOT NULL, details TEXT);
        CREATE TABLE IF NOT EXISTS asset_details(
          target TEXT PRIMARY KEY, asset_tag TEXT DEFAULT '', location TEXT DEFAULT '',
          department TEXT DEFAULT '', owner TEXT DEFAULT '', notes TEXT DEFAULT '',
          updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS asset_images(
          id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT NOT NULL,
          filename TEXT NOT NULL, original_name TEXT NOT NULL,
          mime TEXT NOT NULL, bytes INTEGER NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY (target) REFERENCES machines(target));
        ''')
        columns = {r['name'] for r in c.execute('PRAGMA table_info(tickets)')}
        for name, decl in (
            ('category', "TEXT DEFAULT 'Não classificado'"),
            ('resolved_at', "TEXT DEFAULT ''"),
            ('sla_due_at', "TEXT DEFAULT ''"),
            ('resolution_notes', "TEXT DEFAULT ''")):
            if name not in columns:
                c.execute('ALTER TABLE tickets ADD COLUMN ' + name + ' ' + decl)
        c.execute('CREATE INDEX IF NOT EXISTS ticket_category_idx ON tickets(category)')
        c.execute('CREATE INDEX IF NOT EXISTS asset_images_target_idx ON asset_images(target)')


def rows(query, params=()):
    with db() as c:
        return [dict(x) for x in c.execute(query, params).fetchall()]


def audit(action, target, success, details=''):
    with LOCK, db() as c:
        c.execute('INSERT INTO audit(at,username,action,target,success,details) VALUES (?,?,?,?,?,?)',
                  (now(), os.environ.get('USERNAME') or os.environ.get('USER') or '', action,
                   target or '', int(bool(success)), str(details)[:700]))


def validate_target(target, registered=False):
    if not isinstance(target, str) or not HOST_RE.fullmatch(target) or '..' in target:
        raise ValueError('Informe um IP ou nome de computador válido.')
    try:
        address = ipaddress.ip_address(target)
        if address.version != 4 or not (address.is_private or address.is_loopback):
            raise ValueError('Somente endereços IPv4 internos são permitidos.')
    except ValueError as exc:
        if target[0].isdigit() and all(c in '0123456789.' for c in target):
            raise ValueError('Endereço IP inválido.') from exc
        if isinstance(exc, ValueError) and 'Somente' in str(exc):
            raise
    if registered and not rows('SELECT target FROM machines WHERE target=?', (target,)):
        raise ValueError('Cadastre ou descubra a máquina antes de executar ações.')
    return target


def ps_literal(value):
    b = base64.b64encode(value.encode('utf-8')).decode('ascii')
    return "[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + b + "'))"


def powershell(script, timeout=28):
    if not WIN:
        raise RuntimeError('Esta função requer Windows 10/11 e PowerShell.')
    args = ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand',
            base64.b64encode(script.encode('utf-16-le')).decode('ascii')]
    try:
        p = subprocess.run(args, capture_output=True, text=True, errors='replace',
                           timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.TimeoutExpired:
        raise RuntimeError('Tempo esgotado. Verifique conectividade, WinRM e permissões.')
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout or 'Falha na execução remota').strip()[:750])
    return p.stdout.strip()


def ps_json(script, timeout=28):
    output = powershell('$ErrorActionPreference="Stop"; ' + script, timeout)
    if not output:
        return []
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        raise RuntimeError('Resposta inválida do PowerShell: ' + output[:280])


def remote_script(target, body, timeout=28, argument=None):
    validate_target(target, registered=True)
    arglist = '-ArgumentList ' + ps_literal(argument) if argument is not None else ''
    return ps_json('$t=' + ps_literal(target) + '; '
                   + 'Invoke-Command -ComputerName $t -ScriptBlock { '
                   + body + ' } ' + arglist + ' -ErrorAction Stop | ConvertTo-Json -Depth 6 -Compress', timeout)


def ping_one(target):
    if not WIN:
        return False
    try:
        p = subprocess.run(['ping', '-n', '1', '-w', '650', target],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=2.8, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return p.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def save_machine(target, name=None, mac='', status='Não verificada', origin='Manual'):
    validate_target(target)
    name = (name or target).strip()[:120]
    with LOCK, db() as c:
        c.execute('''INSERT INTO machines(target,name,mac,status,origin,last_seen,updated_at)
        VALUES(?,?,?,?,?,?,?) ON CONFLICT(target) DO UPDATE SET
        name=CASE WHEN excluded.name=machines.target THEN machines.name ELSE excluded.name END,
        mac=CASE WHEN excluded.mac='' THEN machines.mac ELSE excluded.mac END,
        status=excluded.status, origin=excluded.origin,
        last_seen=CASE WHEN excluded.status='Online' THEN excluded.last_seen ELSE machines.last_seen END,
        updated_at=excluded.updated_at''',
        (target, name, mac[:60], status, origin, now() if status == 'Online' else '', now()))


def discover_neighbors():
    output = ps_json('''Get-NetNeighbor -AddressFamily IPv4 -ErrorAction Stop |
      Select-Object IPAddress,LinkLayerAddress,State | ConvertTo-Json -Compress''')
    if isinstance(output, dict):
        output = [output]
    result = []
    for item in (output or []):
        ip = item.get('IPAddress', '')
        try:
            addr = ipaddress.IPv4Address(ip)
        except ValueError:
            continue
        if not addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_unspecified:
            continue
        if item.get('State') in ('Unreachable', 'Incomplete', 'Invalid'):
            continue
        result.append((ip, item.get('LinkLayerAddress') or ''))
    return result


def scan_neighbors():
    seen = discover_neighbors()
    with ThreadPoolExecutor(max_workers=24) as pool:
        futures = {pool.submit(ping_one, target): (target, mac) for target, mac in seen[:250]}
        online = 0
        for future in as_completed(futures):
            target, mac = futures[future]
            alive = future.result()
            online += int(alive)
            save_machine(target, mac=mac, status='Online' if alive else 'Sem resposta', origin='Vizinho de rede')
    audit('Descoberta de vizinhos', '', True, f'{len(seen)} encontrados / {online} ICMP')
    return {'found': min(len(seen), 250), 'online': online,
            'note': 'O ping pode ser bloqueado pelo firewall; sem resposta não significa desligado.'}


def scan_subnet(cidr):
    try:
        subnet = ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        raise ValueError('CIDR inválido. Exemplo: 192.168.1.0/24')
    private_blocks = [ipaddress.ip_network(x) for x in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
    if subnet.version != 4 or not any(subnet.subnet_of(block) for block in private_blocks) or subnet.num_addresses > 256:
        raise ValueError('Informe uma sub-rede IPv4 privada de até 256 endereços (/24 ou menor).')
    targets = [str(i) for i in subnet.hosts()]
    count = 0
    with ThreadPoolExecutor(max_workers=24) as pool:
        futures = {pool.submit(ping_one, target): target for target in targets}
        for future in as_completed(futures):
            target = futures[future]
            if future.result():
                count += 1
                save_machine(target, status='Online', origin='Varredura autorizada')
    audit('Varredura de sub-rede', str(subnet), True, f'{count}/{len(targets)} ICMP')
    return {'found': count, 'online': count,
            'note': 'Somente máquinas que respondem a ICMP são incluídas; outras podem estar ligadas.'}


def metrics():
    with db() as c:
        machines = c.execute('SELECT COUNT(*) FROM machines').fetchone()[0]
        online = c.execute("SELECT COUNT(*) FROM machines WHERE status='Online'").fetchone()[0]
        tickets = c.execute('SELECT COUNT(*) FROM tickets').fetchone()[0]
        open_t = c.execute("SELECT COUNT(*) FROM tickets WHERE status!='Resolvido'").fetchone()[0]
        priority = c.execute("SELECT COUNT(*) FROM tickets WHERE priority IN ('Alta','Crítica') AND status!='Resolvido'").fetchone()[0]
        return {'machines': machines, 'online': online, 'tickets': tickets, 'open_tickets': open_t,
                'priority_tickets': priority, 'windows': WIN, 'zpl_rest_configured': bool(os.environ.get('FLEURY_ZPL_REST_URL')), 'zammad_configured': bool(os.environ.get('FLEURY_ZAMMAD_URL') and os.environ.get('FLEURY_ZAMMAD_TOKEN')),
                'username': os.environ.get('USERNAME') or os.environ.get('USER') or 'Técnico', 'at': now()}


def ticket_import(csv_text):
    if len(csv_text.encode('utf-8')) > 1024 * 1024:
        raise ValueError('Arquivo grande demais: máximo 1 MB.')
    text = csv_text.lstrip('\ufeff')
    try:
        delimiter = csv.Sniffer().sniff(text[:2000], delimiters=',;\t').delimiter
    except csv.Error:
        delimiter = ';' if text[:300].count(';') > text[:300].count(',') else ','
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError('CSV sem cabeçalho.')
    def col(r, *names):
        cleaned = {str(k).casefold().strip().replace(' ', '_'): (v or '').strip()
                   for k, v in r.items() if k}
        return next((cleaned[x] for x in names if cleaned.get(x)), '')
    created = 0; updated = 0
    with LOCK, db() as c:
        for ix, r in enumerate(reader):
            if ix >= 500: raise ValueError('CSV limitado a 500 atendimentos por importação.')
            title = col(r, 'titulo', 'título', 'title', 'assunto', 'subject', 'descricao', 'descrição', 'short_description')[:250]
            if not title: continue
            external = col(r, 'numero', 'número', 'ticket', 'chamado', 'id', 'number')[:90]
            requester = col(r, 'solicitante', 'requester', 'usuario', 'usuário', 'caller')[:120]
            machine = col(r, 'maquina', 'máquina', 'computador', 'hostname', 'machine', 'target')[:120]
            priority = col(r, 'prioridade', 'priority').capitalize()
            priority = priority if priority in PRIORITIES else 'Média'
            status = col(r, 'status', 'situacao', 'situação').capitalize()
            status = status if status in STATUSES else 'Aberto'
            assigned = col(r, 'tecnico', 'técnico', 'assigned', 'atendente', 'responsavel', 'responsável')[:120]
            category = col(r, 'categoria', 'category')
            if category not in CATEGORIES: category = insights.suggest_category(title)
            raw_created = col(r, 'created_at', 'data_abertura', 'aberto_em')
            raw_resolved = col(r, 'resolved_at', 'data_resolucao', 'resolvido_em', 'closed_at')
            raw_sla = col(r, 'sla_due_at', 'prazo_sla', 'limite_sla')
            created_date = iso_or_blank(raw_created) if raw_created else now()
            resolved_date = iso_or_blank(raw_resolved) if raw_resolved and status == 'Resolvido' else ''
            sla_date = iso_or_blank(raw_sla) if raw_sla else ''
            vals = (external,title,requester,machine,priority,status,assigned,'CSV',created_date,now(),category,resolved_date,sla_date)
            if external and c.execute('SELECT id FROM tickets WHERE origin=? AND external_id=?', ('CSV',external)).fetchone():
                c.execute('''UPDATE tickets SET title=?,requester=?,target=?,priority=?,status=?,assigned=?,
                             updated_at=?,category=?,resolved_at=?,sla_due_at=? WHERE origin='CSV' AND external_id=?''',
                          (title,requester,machine,priority,status,assigned,now(),category,resolved_date,sla_date,external))
                updated += 1
            else:
                c.execute('''INSERT INTO tickets(external_id,title,requester,target,priority,status,assigned,
                             origin,created_at,updated_at,category,resolved_at,sla_due_at)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', vals)
                created += 1
    audit('Importação CSV', '', True, f'{created} novos, {updated} atualizados')
    return {'created': created, 'updated': updated}


def get_inventory(target):
    body = '''$os=Get-CimInstance Win32_OperatingSystem -ErrorAction Stop;
      $pc=Get-CimInstance Win32_ComputerSystem;
      $cpu=Get-CimInstance Win32_Processor | Select-Object -First 1;
      $sp=Get-Service -Name Spooler -ErrorAction SilentlyContinue;
      [PSCustomObject]@{ Host=$env:COMPUTERNAME; SO=$os.Caption; Versao=$os.Version;
      MemoriaGB=[math]::Round($pc.TotalPhysicalMemory/1GB,1);
      Processador=$cpu.Name; Dominio=$pc.Domain; Usuario=$pc.UserName;
      UltimoBoot=([string]$os.LastBootUpTime); Spooler=([string]$sp.Status) }'''
    return remote_script(target, body)


def list_printers(target):
    body = '''@(Get-Printer -ErrorAction Stop | Select-Object Name,PrinterStatus,DriverName,Shared)'''
    response = remote_script(target, body)
    if not isinstance(response, list):
        return [] if response is None else [response]
    return response


def clear_printer(target, printer):
    if not isinstance(printer, str) or not 1 <= len(printer.strip()) <= 150:
        raise ValueError('Selecione o nome de uma impressora válida.')
    body = '''param($p)
      $printer=Get-Printer -Name $p -ErrorAction Stop;
      $jobs=@(Get-PrintJob -PrinterName $printer.Name -ErrorAction Stop);
      foreach($j in $jobs) { Remove-PrintJob -PrinterName $printer.Name -ID $j.ID -ErrorAction Stop };
      [PSCustomObject]@{ Impressora=$printer.Name; Removidos=$jobs.Count }'''
    return remote_script(target, body, 35, printer)


def restart_spooler(target):
    return remote_script(target, '''Restart-Service -Name Spooler -Force -ErrorAction Stop;
       [PSCustomObject]@{ Spooler=(Get-Service Spooler).Status.ToString() }''', 35)


def restart_machine(target):
    validate_target(target, registered=True)
    return ps_json('$t=' + ps_literal(target) + '; '
                   + 'Restart-Computer -ComputerName $t -Force -ErrorAction Stop; '
                   + '[PSCustomObject]@{ Mensagem="Reinício solicitado" } | ConvertTo-Json -Compress', timeout=40)




def disk_100_check(target):
    return maintenance.call(remote_script, target, maintenance.DISK_100_PS, timeout=110)


def restart_disk_service(target, service):
    service = maintenance.validate_disk_service(service)
    return maintenance.call(remote_script, target, maintenance.DISK_SERVICE_PS,
                            {'service': service}, timeout=90)


def disk_tool(target, tool):
    tools = {
        'dism-check': (maintenance.DISM_CHECK_PS, 150),
        'dism-repair': (maintenance.DISM_REPAIR_PS, 1500),
        'chkdsk-scan': (maintenance.DISK_SCAN_PS, 900),
        'sfc-scan': (maintenance.SFC_SCAN_PS, 900),
    }
    if tool not in tools:
        raise ValueError('Ferramenta de disco desconhecida.')
    script, timeout = tools[tool]
    return maintenance.call(remote_script, target, script, timeout=timeout)



def performance_check(target):
    return maintenance.call(remote_script, target, maintenance.PERFORMANCE_PS, timeout=65)


def cleanup_temps(target, days=14, commit=False):
    days = maintenance.validate_days(days)
    return maintenance.call(remote_script, target, maintenance.CLEANUP_PS,
                            {'days': days, 'commit': bool(commit)}, timeout=180)


def zebra_check(target, printer):
    printer = maintenance.validate_printer(printer)
    return maintenance.call(remote_script, target, maintenance.ZEBRA_PS,
                            {'printer': printer}, timeout=55)


def pinpad_check(target):
    return maintenance.call(remote_script, target, maintenance.PINPAD_PS, timeout=65)


def tef_service_restart(target, service):
    service = maintenance.validate_service(service)
    return maintenance.call(remote_script, target, maintenance.TEF_SERVICE_PS,
                            {'service': service}, timeout=65)




def zpl_rest_printers():
    printers = integrations.zpl_list('printer')
    return {'Quantidade': len(printers), 'Impressoras': [
        {'Id': x['id'], 'Nome': x['name'], 'Endereco': x['address'], 'Densidade': x['density']}
        for x in printers], 'Modo': 'Somente leitura'}


def restore_points(target):
    return maintenance.call(remote_script, target, maintenance.RESTORE_LIST_PS, timeout=75)


def create_restore_point(target, description):
    return maintenance.call(remote_script, target, maintenance.RESTORE_CREATE_PS,
                            {'description': maintenance.validate_restore_desc(description)}, timeout=180)


def delete_restore_point(target, sequence):
    return maintenance.call(remote_script, target, maintenance.RESTORE_DELETE_PS,
                            {'sequence': maintenance.validate_restore_sequence(sequence)}, timeout=150)


def text_field(b, field, max_len=150):
    v = b.get(field, '')
    if not isinstance(v, str) or len(v) > max_len:
        raise ValueError('Campo inválido: ' + field)
    return v.strip()


def iso_or_blank(value):
    if not value: return ''
    d = insights.parse_date(value)
    if d is None: raise ValueError('Data inválida. Use formato ISO, por exemplo 2026-10-20T12:00:00-03:00.')
    return d.isoformat(timespec='seconds')


def asset_details(target):
    validate_target(target, registered=True)
    found = rows('SELECT * FROM asset_details WHERE target=?', (target,))
    return found[0] if found else {'target': target, 'asset_tag': '', 'location': '',
                                 'department': '', 'owner': '', 'notes': ''}


def update_asset(target, b):
    validate_target(target, registered=True)
    fields = [text_field(b, 'asset_tag', 70), text_field(b, 'location', 120),
              text_field(b, 'department', 120), text_field(b, 'owner', 120),
              text_field(b, 'notes', 1200)]
    with LOCK, db() as c:
        c.execute('''INSERT INTO asset_details(target,asset_tag,location,department,owner,notes,updated_at)
          VALUES(?,?,?,?,?,?,?) ON CONFLICT(target) DO UPDATE SET asset_tag=excluded.asset_tag,
          location=excluded.location,department=excluded.department,owner=excluded.owner,
          notes=excluded.notes,updated_at=excluded.updated_at''',
          (target, *fields, now()))
    audit('Atualizar patrimônio', target, True, f'Patrimônio {fields[0]}')
    return asset_details(target)


def list_asset_images(target):
    validate_target(target, registered=True)
    return rows('''SELECT id,target,original_name,mime,bytes,created_at FROM asset_images
                   WHERE target=? ORDER BY id DESC''', (target,))


def detect_image_format(data):
    if data.startswith(bytes.fromhex('89504e470d0a1a0a')): return 'image/png','.png'
    if data.startswith(bytes.fromhex('ffd8ff')) and data.endswith(bytes.fromhex('ffd9')): return 'image/jpeg','.jpg'
    if len(data)>=12 and data.startswith(b'RIFF') and data[8:12]==b'WEBP': return 'image/webp','.webp'
    raise ValueError('Formato não suportado. Use PNG, JPEG ou WebP válido.')


def add_image(target, obj):
    validate_target(target, registered=True)
    raw = obj.get('data', '')
    if not isinstance(raw, str) or len(raw) > 1900000:
        raise ValueError('Imagem muito grande (limite 1 MB).')
    try:
        content = base64.b64decode(raw, validate=True)
    except (ValueError, Exception) as exc:
        raise ValueError('Imagem Base64 inválida.') from exc
    if not 1 <= len(content) <= 1024*1024:
        raise ValueError('A imagem deve ter no máximo 1 MB.')
    mime, ext = detect_image_format(content)
    filename = secrets.token_hex(20) + ext
    original = text_field(obj, 'name', 100) or 'Imagem do patrimônio'
    with LOCK, db() as c:
        count = c.execute('SELECT COUNT(*) FROM asset_images WHERE target=?', (target,)).fetchone()[0]
        if count >= 8: raise ValueError('Limite de oito imagens por equipamento.')
        dest = IMAGE_DIR / filename
        try:
            with dest.open('xb') as f: f.write(content)
            c.execute('''INSERT INTO asset_images(target,filename,original_name,mime,bytes,created_at)
                         VALUES(?,?,?,?,?,?)''', (target, filename, original, mime, len(content), now()))
        except Exception:
            dest.unlink(missing_ok=True)
            raise
    audit('Anexar imagem de patrimônio', target, True, f'{mime}, {len(content)} bytes')
    return {'ok': True, 'images': list_asset_images(target)}


def remove_image(target, ident):
    validate_target(target, registered=True)
    with LOCK, db() as c:
        rec = c.execute('SELECT filename FROM asset_images WHERE id=? AND target=?', (ident,target)).fetchone()
        if rec is None: raise ValueError('Imagem não encontrada para este equipamento.')
        c.execute('DELETE FROM asset_images WHERE id=? AND target=?', (ident,target))
    (IMAGE_DIR / rec['filename']).unlink(missing_ok=True)
    audit('Excluir imagem de patrimônio', target, True, str(ident))
    return {'ok': True}


def ticket_statistics():
    return insights.metrics(rows('SELECT category, title, status,created_at,resolved_at,sla_due_at FROM tickets'))

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Redirecionamento da API Zammad bloqueado para proteger o token.')


def sync_zammad():
    # Importação somente leitura; token não é armazenado no SQLite nem enviado ao navegador.
    base = (os.environ.get('FLEURY_ZAMMAD_URL') or '').strip().rstrip('/')
    token = (os.environ.get('FLEURY_ZAMMAD_TOKEN') or '').strip()
    url = urlparse(base)
    if not token or url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('Configure FLEURY_ZAMMAD_URL=https://... e FLEURY_ZAMMAD_TOKEN no ambiente do servidor.')
    if url.path not in ('', '/'):
        raise ValueError('Informe somente a URL base HTTPS do Zammad, sem caminho.')
    opener = build_opener(NoRedirect())
    all_tickets = []
    for page in range(1, 4):
        request = Request(base + f'/api/v1/tickets?expand=true&per_page=100&page={page}',
                          headers={'Authorization': 'Token token=' + token, 'Accept': 'application/json'},
                          method='GET')
        try:
            with opener.open(request, timeout=15) as resp:
                if resp.status != 200:
                    raise RuntimeError('Resposta HTTP inesperada da API de atendimentos.')
                data = resp.read(3 * 1024 * 1024 + 1)
                if len(data) > 3 * 1024 * 1024:
                    raise RuntimeError('Resposta do Zammad acima do limite de 3 MB.')
                chunk = json.loads(data.decode('utf-8'))
        except HTTPError as exc:
            raise RuntimeError(f'Zammad respondeu HTTP {exc.code}. Confira permissões de agente e token.') from exc
        except URLError as exc:
            raise RuntimeError('Não foi possível conectar ao Zammad por HTTPS: ' + str(exc.reason)[:160]) from exc
        if not isinstance(chunk, list):
            raise RuntimeError('Formato de resposta não suportado pela API do Zammad.')
        all_tickets.extend(chunk)
        if len(chunk) < 100:
            break
    def label(obj):
        if isinstance(obj, dict):
            return str(obj.get('name') or obj.get('label') or obj.get('login') or '')
        return str(obj or '')
    def state(t):
        name = label(t.get('state')).lower().strip()
        if name in ('closed', 'resolved', 'fechado', 'resolvido', 'merged', 'removed'):
            return 'Resolvido'
        if 'pending' in name or 'pendente' in name:
            return 'Pendente'
        if name in ('open', 'aberto', 'em andamento'):
            return 'Em andamento'
        return 'Aberto'
    def priority(t):
        name = label(t.get('priority')).lower().strip()
        if any(x in name for x in ('critical', 'crítica', 'critica', 'very high')): return 'Crítica'
        if any(x in name for x in ('high', 'alta')): return 'Alta'
        if any(x in name for x in ('low', 'baixa')): return 'Baixa'
        return 'Média'
    created, updated = 0, 0
    with LOCK, db() as c:
        for t in all_tickets:
            if not isinstance(t, dict) or not t.get('id'):
                continue
            external = str(t.get('number') or t['id'])[:90]
            title = str(t.get('title') or 'Atendimento Zammad')[:250]
            requester = label(t.get('customer'))[:120]
            assigned = label(t.get('owner'))[:120]
            ticket_state = state(t)
            category = insights.suggest_category(title)
            created_date = iso_or_blank(t.get('created_at')) if t.get('created_at') else now()
            closed = t.get('close_at') or t.get('last_close_at')
            resolved = iso_or_blank(closed) if closed and ticket_state == 'Resolvido' else ''
            due = iso_or_blank(t.get('close_escalation_at')) if t.get('close_escalation_at') else ''
            values = (title, requester, priority(t), ticket_state, assigned, now(),
                      category, resolved, due, external)
            match = c.execute('SELECT id FROM tickets WHERE origin=? AND external_id=?', ('Zammad', external)).fetchone()
            if match:
                c.execute('''UPDATE tickets SET title=?,requester=?,priority=?,status=?,assigned=?,updated_at=?,
                             category=?,resolved_at=?,sla_due_at=?
                             WHERE origin='Zammad' AND external_id=?''', values)
                updated += 1
            else:
                c.execute('''INSERT INTO tickets(external_id,title,requester,target,priority,status,assigned,
                     origin,created_at,updated_at,category,resolved_at,sla_due_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                     (external,title,requester,'',priority(t),ticket_state,assigned,'Zammad',created_date,now(),
                      category,resolved,due))
                created += 1
    audit('Sincronizar Zammad', '', True, f'{created} novos / {updated} atualizados; máximo de 300 registros')
    return {'created': created, 'updated': updated, 'total': len(all_tickets), 'possibly_truncated': len(all_tickets) == 300,
            'note': 'Sincronização de leitura; até 300 tickets e apenas campos básicos. Verifique os nomes de estados conforme a configuração da sua instância.'}


class Handler(BaseHTTPRequestHandler):
    server_version = 'FleuryTI/1.2'

    def log_message(self, fmt, *args):
        if not self.path.startswith('/api/'):
            return
        print('[HTTP]', fmt % args)

    def send(self, code=200, obj=None, typ='application/json; charset=utf-8', payload=None, extra=None):
        data = payload if payload is not None else json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', typ)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def error(self, code, message):
        self.send(code, {'error': str(message)})

    def local_host(self):
        # Impede DNS rebinding: o token da interface nunca deve ser servido
        # sob outro hostname, mesmo que encaminhado ao loopback por terceiros.
        hostname = self.headers.get('Host', '').lower()
        port = self.server.server_port
        return hostname in (f'127.0.0.1:{port}', f'localhost:{port}')

    def authorized(self):
        return secrets.compare_digest(self.headers.get('X-Fleury-Token') or '', TOKEN)

    def do_GET(self):
        try:
            self.handle_get()
        except (ValueError, RuntimeError) as exc:
            self.error(400, str(exc))
        except Exception as exc:
            print('ERRO GET:', repr(exc))
            self.error(500, 'Erro interno. Consulte o terminal.')

    def handle_get(self):
        if not self.local_host():
            return self.error(403, 'Acesso local via 127.0.0.1 ou localhost obrigatório.')
        url = urlparse(self.path)
        path = url.path
        if path == '/':
            html = (APP / 'static' / 'index.html').read_text('utf-8')
            html = html.replace('__SESSION_TOKEN__', json.dumps(TOKEN))
            self.send(200, typ='text/html; charset=utf-8', payload=html.encode('utf-8'))
            return
        static = {'/static/app.css': 'text/css; charset=utf-8',
                  '/static/app.js': 'text/javascript; charset=utf-8',
                  '/static/extra.js': 'text/javascript; charset=utf-8',
                  '/static/workstation.js': 'text/javascript; charset=utf-8',
                  '/static/selection.js': 'text/javascript; charset=utf-8',
                  '/static/upgrade.js': 'text/javascript; charset=utf-8',
                  '/static/video_tools.js': 'text/javascript; charset=utf-8',
                  '/static/integrations.js': 'text/javascript; charset=utf-8',
                  '/static/mark.png': 'image/png'}
        if path in static:
            data = (APP / path.lstrip('/')).read_bytes()
            self.send(200, typ=static[path], payload=data)
            return
        if not path.startswith('/api/'):
            return self.error(404, 'Não encontrado.')
        if not self.authorized():
            return self.error(403, 'Sessão não autorizada.')
        params = parse_qs(url.query)
        target = (params.get('target') or [''])[0]
        if path == '/api/status':
            return self.send(obj=metrics())
        if path == '/api/integrations/status':
            return self.send(obj=integrations.status())
        if path == '/api/scripts/catalog':
            return self.send(obj=admin_scripts.catalog())
        if path == '/api/scripts/run':
            key = (params.get('key') or [''])[0]
            body = admin_scripts.body(key)
            return self.run_read_admin('Script ' + key, target,
                lambda: remote_script(target, body, timeout=90))
        if path == '/api/zebra/catalog':
            return self.run_read_admin('Consultar catálogo Zebra', '', lambda: {
                'printers': integrations.zpl_list('printer'), 'labels': integrations.zpl_list('label')})
        if path == '/api/software/catalog':
            return self.send(obj={'programs': software_catalog.catalog(), 'max_batch': 5})
        if path == '/api/machines':
            return self.send(obj=rows('SELECT * FROM machines ORDER BY CASE status WHEN "Online" THEN 0 ELSE 1 END, name COLLATE NOCASE'))
        if path == '/api/tickets':
            return self.send(obj=rows('SELECT * FROM tickets ORDER BY CASE status WHEN "Resolvido" THEN 1 ELSE 0 END, id DESC'))
        if path == '/api/analytics':
            return self.send(obj=ticket_statistics())
        if path == '/api/assets/detail':
            return self.send(obj=asset_details(target))
        if path == '/api/assets/images':
            return self.send(obj=list_asset_images(target))
        if path == '/api/assets/image':
            ident = int((params.get('id') or ['0'])[0])
            rec = rows('SELECT filename,mime FROM asset_images WHERE id=?', (ident,))
            if not rec: return self.error(404, 'Imagem inexistente.')
            content = (IMAGE_DIR / rec[0]['filename']).read_bytes()
            return self.send(200, typ=rec[0]['mime'], payload=content)
        if path == '/api/logs':
            return self.send(obj=rows('SELECT * FROM audit ORDER BY id DESC LIMIT 150'))
        if path == '/api/admin/inventory':
            return self.run_read_admin('Inventário remoto', target, lambda: get_inventory(target))
        if path == '/api/admin/printers':
            return self.run_read_admin('Consultar impressoras', target, lambda: list_printers(target))
        if path == '/api/diagnostics/disk-guided':
            return self.run_read_admin('Diagnóstico orientado HD 100%', target,
                 lambda: maintenance.call(remote_script, target, software_catalog.DISK_GUIDED_PS, timeout=85))
        if path == '/api/diagnostics/disk-100':
            return self.run_read_admin('Diagnóstico HD 100%', target, lambda: disk_100_check(target))
        if path == '/api/diagnostics/performance':
            return self.run_read_admin('Diagnóstico de desempenho', target, lambda: performance_check(target))
        if path == '/api/diagnostics/zebra':
            printer = (params.get('printer') or [''])[0]
            return self.run_read_admin('Diagnóstico Zebra', target, lambda: zebra_check(target, printer))
        if path == '/api/diagnostics/zpl-rest':
            try:
                result = zpl_rest_printers()
                audit('Consultar impressoras ZPL REST', '', True, f'{result["Quantidade"]} impressoras')
                return self.send(obj={'ok': True, 'result': result})
            except Exception as exc:
                audit('Consultar impressoras ZPL REST', '', False, str(exc))
                raise
        if path == '/api/maintenance/restore-points':
            validate_target(target, registered=True)
            if not WIN:
                raise RuntimeError('A consulta de pontos de restauração requer Windows.')
            try:
                result = restore_points(target)
                ids = {int(pt['Numero']) for pt in result.get('Pontos', [])}
                self.server.restore_previews[target] = (time.monotonic(), ids)
                audit('Listar pontos de restauração', target, True, f'{len(ids)} ponto(s)')
                return self.send(obj={'ok': True, 'result': result})
            except Exception as exc:
                audit('Listar pontos de restauração', target, False, str(exc))
                raise
        # Somente operações pré-definidas. Não aceita PowerShell fornecido pelo navegador.
        if path == '/api/diagnostics/updates':
            return self.run_read_admin('Consultar atualizações', target,
                lambda: maintenance.call(remote_script, target, maintenance.UPDATE_STATUS_PS, timeout=75))
        if path == '/api/diagnostics/services':
            return self.run_read_admin('Consultar serviços', target,
                lambda: maintenance.call(remote_script, target, maintenance.SERVICE_STATUS_PS, timeout=75))
        if path == '/api/diagnostics/network':
            return self.run_read_admin('Diagnóstico de rede', target,
                lambda: maintenance.call(remote_script, target, maintenance.NETWORK_DIAG_PS, timeout=75))
        if path == '/api/diagnostics/pinpad':
            return self.run_read_admin('Diagnóstico PINPAD', target, lambda: pinpad_check(target))
        if path == '/api/diagnostics/remote-console':
            kind = (params.get('type') or [''])[0]
            routine = video_insights.SAFE_QUERIES.get(kind)
            if routine is None:
                raise ValueError('Consulta remota não permitida.')
            return self.run_read_admin(video_insights.LABELS[kind], target,
                lambda: maintenance.call(remote_script, target, routine, timeout=90))

        if path == '/api/tickets/export':
            output = io.StringIO()
            writer = csv.writer(output, delimiter=';')
            keys = ['id','external_id','title','requester','target','priority','status','assigned','origin','category','created_at','resolved_at','sla_due_at']
            writer.writerow(keys)
            for t in rows('SELECT * FROM tickets ORDER BY id'):
                writer.writerow([t[x] for x in keys])
            return self.send(200, payload=('\ufeff' + output.getvalue()).encode('utf-8'),
                             typ='text/csv; charset=utf-8',
                             extra={'Content-Disposition':'attachment; filename="fila_atendimentos.csv"'})
        self.error(404, 'Rota não encontrada.')

    def run_read_admin(self, action, target, cb):
        try:
            result = cb()
            audit(action, target, True)
            return self.send(obj={'ok': True, 'result': result})
        except Exception as exc:
            audit(action, target, False, str(exc))
            raise

    def do_POST(self):
        try:
            if not self.local_host():
                return self.error(403, 'Acesso local via 127.0.0.1 ou localhost obrigatório.')
            if not self.authorized():
                return self.error(403, 'Sessão não autorizada.')
            origin = self.headers.get('Origin') or ''
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.error(403, 'Origem não permitida.')
            size = int(self.headers.get('Content-Length') or '0')
            if size <= 0 or size > 2100000:
                return self.error(400, 'Dados ausentes ou tamanho excedido.')
            body = json.loads(self.rfile.read(size).decode('utf-8'))
            if not isinstance(body, dict):
                raise ValueError('Dados inválidos.')
            self.handle_post(urlparse(self.path).path, body)
        except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
            self.error(400, str(exc))
        except Exception as exc:
            print('ERRO POST:', repr(exc))
            self.error(500, 'Erro interno. Consulte o terminal.')

    def handle_post(self, path, b):
        target = b.get('target', '')
        if path in ('/api/zebra/print', '/api/winutil/launch'):
            if b.get('confirm') is not True:
                raise ValueError('Confirmação explícita obrigatória.')
            action = 'Imprimir Zebra' if path.endswith('/print') else 'Abrir WinUtil local'
            destination = str(b.get('printer', ''))[:100] if path.endswith('/print') else 'Estação local'
            try:
                result = integrations.zpl_print(b) if path.endswith('/print') else integrations.launch_winutil()
                audit(action, destination, True, 'Pedido enviado; sem conteúdo de etiquetas na auditoria.')
                return self.send(obj={'ok': True, 'result': result})
            except Exception as exc:
                audit(action, destination, False, str(exc))
                raise
        if path == '/api/system/shutdown':
            if b.get('confirm') is not True:
                raise ValueError('Confirme o encerramento do aplicativo.')
            audit('Encerrar aplicativo local', '', True)
            self.send(obj={'ok': True, 'message': 'Encerrando o servidor local.'})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if path == '/api/assets/update':
            return self.send(obj={'ok': True, 'detail': update_asset(target, b)})
        if path == '/api/assets/upload':
            return self.send(obj=add_image(target, b))
        if path == '/api/assets/delete-image':
            if b.get('confirm') is not True:
                raise ValueError('Confirme a exclusão da imagem.')
            return self.send(obj=remove_image(target, int(b.get('id') or 0)))
        if path == '/api/tickets/category':
            category = b.get('category')
            if category not in CATEGORIES: raise ValueError('Categoria inválida.')
            ident = int(b.get('id', 0))
            with LOCK, db() as c:
                x = c.execute('UPDATE tickets SET category=?,updated_at=? WHERE id=?',
                              (category, now(), ident))
                if not x.rowcount: raise ValueError('Chamado não encontrado.')
            audit('Classificação de atendimento', str(ident), True, category)
            return self.send(obj={'ok': True})
        if path == '/api/machines/add':
            validate_target(target)
            save_machine(target, name=b.get('name'), origin='Manual')
            audit('Cadastro de máquina', target, True)
            return self.send(obj={'ok': True})
        if path == '/api/machines/scan':
            if not WIN:
                raise RuntimeError('Descoberta de rede disponível somente no Windows.')
            mode = b.get('mode')
            if mode == 'neighbors':
                return self.send(obj=scan_neighbors())
            if mode == 'subnet':
                return self.send(obj=scan_subnet(str(b.get('cidr', '')).strip()))
            raise ValueError('Modo de descoberta inválido.')
        if path == '/api/machines/verify':
            validate_target(target, registered=True)
            online = ping_one(target)
            with LOCK, db() as c:
                c.execute('''UPDATE machines SET status=?, updated_at=?,
                last_seen=CASE WHEN ? THEN ? ELSE last_seen END WHERE target=?''',
                          ('Online' if online else 'Sem resposta', now(), int(online), now(), target))
            return self.send(obj={'ok': True, 'online': online, 'note': 'ICMP pode ser bloqueado.'})
        if path == '/api/tickets/zammad-sync':
            try:
                return self.send(obj=sync_zammad())
            except Exception as exc:
                audit('Sincronizar Zammad', '', False, str(exc))
                raise
        if path == '/api/maintenance/restore-create':
            validate_target(target, registered=True)
            if not WIN:
                raise RuntimeError('A criação de pontos de restauração requer Windows.')
            if b.get('confirm') is not True:
                raise ValueError('Confirme a criação do ponto de restauração.')
            description = maintenance.validate_restore_desc(b.get('description'))
            try:
                result = create_restore_point(target, description)
                self.server.restore_previews.pop(target, None)
                audit('Criar ponto de restauração', target, True, f'desc={description}')
                return self.send(obj={'ok': True, 'result': result})
            except Exception as exc:
                audit('Criar ponto de restauração', target, False, str(exc))
                raise
        if path == '/api/maintenance/restore-delete':
            validate_target(target, registered=True)
            if not WIN:
                raise RuntimeError('A exclusão de pontos de restauração requer Windows.')
            if b.get('confirm') is not True:
                raise ValueError('Confirmação explícita obrigatória.')
            sequence = maintenance.validate_restore_sequence(b.get('sequence'))
            preview = self.server.restore_previews.get(target)
            if not preview or time.monotonic() - preview[0] > 600 or sequence not in preview[1]:
                raise ValueError('Atualize a lista de pontos desta máquina antes de excluir (validade de 10 minutos).')
            try:
                result = delete_restore_point(target, sequence)
                self.server.restore_previews.pop(target, None)
                audit('Excluir ponto de restauração', target, True, f'sequencia={sequence}')
                return self.send(obj={'ok': True, 'result': result})
            except Exception as exc:
                audit('Excluir ponto de restauração', target, False, str(exc))
                raise
        if path in ('/api/maintenance/cleanup', '/api/maintenance/quick-optimize'):
            validate_target(target, registered=True)
            if not WIN:
                raise RuntimeError('Ação disponível apenas no Windows.')
            # Sem etapa de simulação, mas sempre com confirmação explícita do técnico.
            if b.get('confirm') is not True:
                raise ValueError('Confirme a manutenção no computador selecionado.')
            days = maintenance.validate_days(b.get('days', 14))
            quick = path.endswith('quick-optimize')
            label = 'Otimização rápida (TEMP)' if quick else 'Limpeza direta de TEMP'
            try:
                if quick:
                    result = maintenance.call(remote_script, target, maintenance.QUICK_OPTIMIZE_PS,
                                              {'days': days, 'commit': True}, timeout=135)
                    metrics = result.get('Limpeza', {}) or {}
                else:
                    result = cleanup_temps(target, days, True)
                    metrics = result
                audit(label, target, True,
                      f'dias={days}; removidos={metrics.get("ArquivosRemovidos", 0)}; '
                      f'liberadosMB={metrics.get("LiberadosMB", 0)}; falhas={metrics.get("Falhas", 0)}')
                return self.send(obj={'ok': True, 'result': result})
            except Exception as exc:
                audit(label, target, False, str(exc))
                raise
        if path == '/api/software/uninstall':
            validate_target(target, registered=True)
            if not WIN:
                raise RuntimeError('Desinstalação por WinGet requer Windows e WinRM autorizado.')
            if b.get('confirm') is not True:
                raise ValueError('Confirmação do técnico obrigatória.')
            package_ids = software_catalog.validate_packages(b.get('packages'))
            # Permitido apenas para pacotes listados, com autenticação WinRM existente.
            try:
                result = maintenance.call(remote_script, target, software_catalog.UNINSTALL_PS,
                                          {'packages': package_ids}, timeout=1500)
                outcomes = result.get('Desinstalacoes', []) if isinstance(result, dict) else []
                if isinstance(outcomes, dict): outcomes=[outcomes]
                success = (len(outcomes) == len(package_ids) and
                           all(x.get('CodigoSaida') == 0 for x in outcomes))
                audit('Desinstalação WinGet', target, success, ', '.join(package_ids))
                return self.send(obj={'ok': success, 'result': result})
            except Exception as exc:
                audit('Desinstalação WinGet', target, False, str(exc))
                raise
        if path == '/api/software/install':
            validate_target(target, registered=True)
            if not WIN:
                raise RuntimeError('Instalação por WinGet requer Windows e WinRM autorizado.')
            if b.get('confirm') is not True:
                raise ValueError('Confirmação do técnico obrigatória.')
            package_ids = software_catalog.validate_packages(b.get('packages'))
            # Integração apenas por catálogo fixo; nunca recebe comando arbitrário ou URL.
            try:
                result = maintenance.call(remote_script, target, software_catalog.INSTALL_PS,
                                          {'packages': package_ids}, timeout=1500)
                outcomes = result.get('Instalacoes', []) if isinstance(result, dict) else []
                if isinstance(outcomes, dict): outcomes=[outcomes]
                success = (len(outcomes) == len(package_ids) and all(x.get('CodigoSaida') == 0 for x in outcomes))
                audit('Instalação de software WinGet', target, success, ', '.join(package_ids))
                return self.send(obj={'ok': success, 'result': result})
            except Exception as exc:
                audit('Instalação de software WinGet', target, False, str(exc))
                raise
        if path == '/api/diagnostics/disk-guided':
            raise ValueError('Use GET para diagnóstico de disco.')
        if path == '/api/maintenance/flush-dns':
            validate_target(target, registered=True)
            if not WIN:
                raise RuntimeError('Requer Windows com WinRM.')
            if b.get('confirm') is not True:
                raise ValueError('Confirmação explícita obrigatória.')
            try:
                result = maintenance.call(remote_script, target, maintenance.FLUSH_DNS_PS, timeout=70)
                audit('Limpar cache DNS', target, True)
                return self.send(obj={'ok': True, 'result': result})
            except Exception as exc:
                audit('Limpar cache DNS', target, False, str(exc))
                raise
        if path == '/api/maintenance/disk-service':
            validate_target(target, registered=True)
            if not WIN:
                raise RuntimeError('Requer Windows.')
            if b.get('confirm') is not True:
                raise ValueError('Confirmação explícita necessária para reiniciar serviço.')
            service = maintenance.validate_disk_service(b.get('service'))
            try:
                result = restart_disk_service(target, service)
                audit('Reinício pontual ' + service, target, True)
                return self.send(obj={'ok': True, 'result': result})
            except Exception as exc:
                audit('Reinício pontual ' + service, target, False, str(exc))
                raise
        if path == '/api/maintenance/disk-tool':
            validate_target(target, registered=True)
            if not WIN:
                raise RuntimeError('Requer Windows.')
            if b.get('confirm') is not True:
                raise ValueError('Confirmação explícita obrigatória.')
            tool = str(b.get('tool') or '')
            if tool not in ('dism-check', 'dism-repair', 'chkdsk-scan', 'sfc-scan'):
                raise ValueError('Ferramenta não permitida.')
            try:
                result = disk_tool(target, tool)
                success = result.get('Codigo') in (0, 3010)
                audit('Verificação de disco/Windows ' + tool, target, success,
                      'código=' + str(result.get('Codigo', '')))
                return self.send(obj={'ok': success, 'result': result})
            except Exception as exc:
                audit('Verificação de disco/Windows ' + tool, target, False, str(exc))
                raise
        if path == '/api/maintenance/tef-restart':
            validate_target(target, registered=True)
            if b.get('confirm') is not True:
                raise ValueError('Confirme que não existem transações de pagamento em andamento.')
            if not WIN:
                raise RuntimeError('Requer Windows.')
            try:
                result = tef_service_restart(target, b.get('service'))
                audit('Reiniciar middleware TEF', target, True, str(b.get('service')))
                return self.send(obj={'ok': True, 'result': result})
            except Exception as exc:
                audit('Reiniciar middleware TEF', target, False, str(exc))
                raise
        if path == '/api/tickets/import':
            if not isinstance(b.get('csv'), str):
                raise ValueError('Informe um CSV válido.')
            return self.send(obj=ticket_import(b['csv']))
        if path == '/api/tickets/create':
            title = text_field(b, 'title', 250)
            if len(title) < 2: raise ValueError('Título deve ter de 2 a 250 caracteres.')
            priority = b.get('priority', 'Média')
            if priority not in PRIORITIES: raise ValueError('Prioridade inválida.')
            category = b.get('category') or insights.suggest_category(title)
            if category not in CATEGORIES: raise ValueError('Categoria inválida.')
            due = ''
            hours = b.get('sla_hours', '')
            if str(hours).strip():
                try: hours = int(hours)
                except (ValueError, TypeError): raise ValueError('SLA precisa ser em horas inteiras.')
                if not 1 <= hours <= 720: raise ValueError('SLA permitido entre 1 e 720 horas.')
                due = (datetime.now().astimezone() + timedelta(hours=hours)).isoformat(timespec='seconds')
            with LOCK, db() as c:
                c.execute('''INSERT INTO tickets(title,requester,target,priority,status,assigned,origin,
                    created_at,updated_at,category,sla_due_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                    (title, text_field(b,'requester',120), text_field(b,'target',120),
                     priority, 'Aberto', text_field(b,'assigned',120), 'Local',now(),now(),category,due))
            audit('Novo atendimento', '', True, title)
            return self.send(obj={'ok': True})
        if path == '/api/tickets/update':
            status = b.get('status')
            if status not in STATUSES: raise ValueError('Status inválido.')
            ident = int(b.get('id',0))
            with LOCK, db() as c:
                previous = c.execute('SELECT status,resolved_at FROM tickets WHERE id=?',(ident,)).fetchone()
                if previous is None: raise ValueError('Atendimento não encontrado.')
                resolved = previous['resolved_at']
                if status == 'Resolvido' and previous['status'] != 'Resolvido': resolved = now()
                if status != 'Resolvido': resolved = ''
                c.execute('UPDATE tickets SET status=?,updated_at=?,resolved_at=? WHERE id=?',
                          (status,now(),resolved,ident))
            audit('Atualizar atendimento', str(ident), True, status)
            return self.send(obj={'ok': True})
        remote = {'/api/admin/rdp':'Abrir RDP','/api/admin/terminal':'Abrir sessão PowerShell',
                  '/api/admin/restart':'Reiniciar computador','/api/admin/clear-print':'Limpar fila de impressão',
                  '/api/admin/spooler':'Reiniciar serviço Spooler'}
        if path in remote:
            validate_target(target, registered=True)
            if path in ('/api/admin/restart', '/api/admin/clear-print', '/api/admin/spooler') and b.get('confirm') is not True:
                raise ValueError('Confirmação explícita obrigatória.')
            if not WIN:
                raise RuntimeError('Ação disponível apenas no Windows.')
            action = remote[path]
            try:
                if path == '/api/admin/rdp':
                    subprocess.Popen(['mstsc.exe', '/v:' + target],
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    result = {'message': 'Área de Trabalho Remota aberta. Autenticação Windows necessária.'}
                elif path == '/api/admin/terminal':
                    command = 'Enter-PSSession -ComputerName ' + target
                    subprocess.Popen(['powershell.exe', '-NoExit', '-NoProfile', '-Command', command],
                                     creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
                    result = {'message': 'Console PowerShell aberto. Permissões WinRM necessárias.'}
                elif path == '/api/admin/restart':
                    result = restart_machine(target)
                elif path == '/api/admin/clear-print':
                    result = clear_printer(target, b.get('printer', ''))
                else:
                    result = restart_spooler(target)
                audit(action, target, True, json.dumps(result, ensure_ascii=False)[:500])
                return self.send(obj={'ok':True,'result':result})
            except Exception as exc:
                audit(action, target, False, str(exc))
                raise
        self.error(404, 'Rota não encontrada.')


def main():
    initialize()
    port = int(os.environ.get('FLEURY_TI_PORT', '8765'))
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.cleanup_previews = {}
    server.restore_previews = {}
    url = f'http://127.0.0.1:{port}/'
    print('==============================================')
    print(' FLEURY TI CONTROL CENTER - versão MVP 1.2')
    print(' Local:', url)
    print(' Usuário:', metrics()['username'])
    print(' Windows:', WIN)
    print(' Dados:', DB)
    print(' Para encerrar: CTRL+C')
    print('==============================================')
    if '--no-browser' not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print('\nAplicação encerrada.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
