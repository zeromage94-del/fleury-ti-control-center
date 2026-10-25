"""Start portable and silently installed builds on the disposable CI runner.
Only loopback HTTP and fictitious local records; no remote administrative calls.
"""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def smoke(exe, data, env):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    env={**env,'FLEURY_TI_PORT':str(port)}
    process=subprocess.Popen([str(exe),'--no-browser'],env=env)
    base=f'http://127.0.0.1:{port}'
    try:
        for _ in range(80):
            if process.poll() is not None:
                raise RuntimeError('Executable exited before HTTP startup: '+str(process.returncode))
            try:
                with urlopen(base,timeout=1) as response: html=response.read().decode()
                break
            except OSError: time.sleep(.25)
        else: raise RuntimeError('HTTP startup timeout')
        token=json.loads(re.search(r'window\.__APP_TOKEN__=("[^"]+")',html).group(1))
        def api(path,body=None):
            raw=json.dumps(body).encode() if body is not None else None
            request=Request(base+'/api/'+path,data=raw,headers={'X-Fleury-Token':token,'Content-Type':'application/json'})
            with urlopen(request,timeout=5) as response: return json.load(response)
        assert 'machines' in api('status')
        catalog=api('software/catalog')['programs']
        assert len(catalog)>40 and any(p['winget_id']=='7zip.7zip' for p in catalog)
        drivers=api('printers/drivers/catalog')
        assert 'packages' in drivers and drivers['official_url'].startswith('https://www.zebra.com/')
        with urlopen(base+'/static/upgrade.js',timeout=5) as response:
            script=response.read()
            assert b'downloads-cleanup' in script and b'downloads-preview' not in script
        with urlopen(base+'/static/integrations.js',timeout=5) as response: assert b'printers/drivers/change' in response.read()
        with urlopen(base+'/static/fleet.js',timeout=5) as response: assert b'softwareCatalogError' in response.read()
        api('machines/add',{'target':'PC-PACKAGE-SIM','name':'Ficticio CI'})
        assert any(x['target']=='PC-PACKAGE-SIM' for x in api('machines'))
        with urlopen(base+'/static/mark.png',timeout=5) as response: assert response.read().startswith(b'\x89PNG')
        api('system/shutdown',{'confirm':True})
        assert process.wait(timeout=15)==0
        assert (data/'fleury_ti.db').is_file(), str(data)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)

def main():
    if os.name!='nt': raise SystemExit('Windows only')
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        env={**os.environ,'LOCALAPPDATA':str(root/'local')}
        archive=next((ROOT/'entrega_windows').glob('*Portatil*_Windows_x64.zip'))
        with zipfile.ZipFile(archive) as package: package.extractall(root/'portable')
        exe=next((root/'portable').glob('*/FleuryTIControlCenter.exe'))
        smoke(exe,exe.parent/'data',env)
        # Restart checks that the packaged app can reopen its persisted SQLite DB.
        smoke(exe,exe.parent/'data',env)
        installer=next((ROOT/'entrega_windows').glob('*Instalador*_Windows_x64.exe'))
        install=root/'installed'
        subprocess.run([str(installer),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',f'/DIR={install}'],check=True,timeout=120,env=env)
        data=root/'local'/'FleuryTIControlCenter'/'data'
        try: smoke(install/'FleuryTIControlCenter.exe',data,env)
        finally:
            uninstaller=install/'unins000.exe'
            if uninstaller.exists(): subprocess.run([str(uninstaller),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],check=True,timeout=120,env=env)
        assert (data/'fleury_ti.db').exists(), 'Uninstall removed user data'
        print('Portable startup/restart, installed startup, loopback API, image asset and uninstall data preservation: PASS')

if __name__=='__main__': main()
