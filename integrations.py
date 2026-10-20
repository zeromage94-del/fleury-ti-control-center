"""Adaptadores HTTP explícitos. Segredos ficam apenas no ambiente do servidor."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError('Redirecionamento bloqueado para proteger a integração.')


def base_url(variable):
    value = os.environ.get(variable, '').strip().rstrip('/')
    p = urlsplit(value)
    try:
        port = p.port
    except ValueError as exc:
        raise ValueError('Porta inválida na configuração.') from exc
    if (not p.hostname or p.username or p.password or p.path or p.query or p.fragment
            or p.scheme not in ('http', 'https')):
        raise ValueError(f'Configure {variable} com a URL base do serviço, sem credenciais ou caminho.')
    if p.scheme == 'http' and p.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('HTTP permitido apenas no loopback. Use HTTPS para servidores remotos.')
    return value


def api(variable, path, method='GET', payload=None, token_variable=None):
    url = base_url(variable) + path
    headers = {'Accept': 'application/json', 'User-Agent': 'Fleury-TI/1.2.1'}
    if token_variable:
        token = os.environ.get(token_variable, '').strip()
        if not token or '\n' in token or '\r' in token:
            raise ValueError(f'Configure {token_variable} no ambiente do servidor.')
        headers['Authorization'] = 'Token token=' + token
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    try:
        with build_opener(NoRedirect()).open(Request(url, data=body, headers=headers, method=method), timeout=20) as response:
            data = response.read(3 * 1024 * 1024 + 1)
    except HTTPError as exc:
        raise RuntimeError(f'Serviço respondeu HTTP {exc.code}; confira configuração e permissões.') from exc
    except (URLError, OSError) as exc:
        # Não incluir cabeçalhos, tokens, corpo ou URL na mensagem/auditoria.
        raise RuntimeError('Serviço indisponível. Confira endereço, certificado e conectividade.') from exc
    if len(data) > 3 * 1024 * 1024:
        raise RuntimeError('Resposta acima do limite de 3 MB.')
    try:
        return json.loads(data.decode('utf-8')) if data else {}
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError('O serviço não retornou JSON válido.') from exc


def zpl_list(kind):
    if kind not in ('printer', 'label'):
        raise ValueError('Recurso ZPL inválido.')
    result = api('FLEURY_ZPL_REST_URL', '/rest/' + kind)
    if isinstance(result, dict):
        result = result.get('printers' if kind == 'printer' else 'labels', result.get('data', []))
    if not isinstance(result, list):
        raise RuntimeError('Lista ZPL inválida.')
    return [{'id': str(x.get('_id') or x.get('id') or ''), 'name': str(x.get('name', ''))[:120],
             'address': str(x.get('address', ''))[:180], 'density': str(x.get('density', ''))[:30]}
            for x in result[:500] if isinstance(x, dict)]


def zpl_print(body):
    if body.get('confirm') is not True:
        raise ValueError('Confirme a impressão na Zebra selecionada.')
    printer, label = body.get('printer'), body.get('label')
    if not isinstance(printer, str) or not isinstance(label, str):
        raise ValueError('Selecione impressora e modelo cadastrados no zpl-rest.')
    if printer not in {x['id'] for x in zpl_list('printer')} or label not in {x['id'] for x in zpl_list('label')}:
        raise ValueError('Impressora ou modelo não cadastrado; atualize as listas.')
    data = body.get('data', {})
    if not isinstance(data, dict) or len(json.dumps(data).encode('utf-8')) > 16000:
        raise ValueError('Variáveis devem ser um objeto JSON de até 16 KB.')
    for key, value in data.items():
        if (not re.fullmatch(r'[A-Za-z0-9_]{1,64}', key) or not isinstance(value, (str, int, float, bool))
                or any(c in str(value) for c in ('^', '~', '\x00', '\r', '\n'))):
            raise ValueError('Variáveis inválidas: use valores simples, sem comandos ZPL ou quebras de linha.')
    result = api('FLEURY_ZPL_REST_URL', '/rest/print', 'POST', {'printer': printer, 'label': label, 'data': data})
    if isinstance(result, dict) and (result.get('success') is False or result.get('error')):
        raise RuntimeError('O servidor ZPL recusou a impressão. Consulte o serviço antes de tentar novamente.')
    return {'message': 'Pedido aceito pelo servidor ZPL; confira a saída física. Não repita sem verificar a fila.'}


def launch_winutil():
    """Executa somente cópia local revisada, com SHA256 definido pelo administrador."""
    path = Path(os.environ.get('FLEURY_WINUTIL_PATH', ''))
    expected = os.environ.get('FLEURY_WINUTIL_SHA256', '').lower()
    if not path.is_file() or path.suffix.lower() != '.ps1' or not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('Configure FLEURY_WINUTIL_PATH e FLEURY_WINUTIL_SHA256 com uma cópia local revisada do WinUtil.')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Hash do WinUtil divergente. Revise a cópia antes de executar.')
    if os.name != 'nt':
        raise RuntimeError('WinUtil requer Windows.')
    # Sem ExecutionPolicy Bypass, download/iex, alteração de GPO ou elevação automática.
    subprocess.Popen(['powershell.exe', '-NoProfile', '-NoExit', '-File', str(path.resolve())],
                     creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
    return {'message': 'WinUtil aberto na estação local do técnico. As alterações feitas nele não são auditadas pelo Fleury.'}


def status():
    return {'zpl': bool(os.environ.get('FLEURY_ZPL_REST_URL')),
            'zammad': bool(os.environ.get('FLEURY_ZAMMAD_URL') and os.environ.get('FLEURY_ZAMMAD_TOKEN')),
            'winutil': bool(os.environ.get('FLEURY_WINUTIL_PATH') and os.environ.get('FLEURY_WINUTIL_SHA256'))}
