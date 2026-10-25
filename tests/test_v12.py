"""Validação estrutural, rotas e segurança sem administração remota real."""
import http.client
import json
import sys
import threading
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import video_insights

ROOT=Path(__file__).resolve().parents[1]

class V12Tests(unittest.TestCase):
    def test_media_suggestions_read_only(self):
        self.assertEqual(set(video_insights.SAFE_QUERIES),{'apps','processes','drives','startup'})
        for s in video_insights.SAFE_QUERIES.values():
            for forbidden in ['Remove-Item','Stop-Process','Uninstall-','Start-Process','Set-MpPreference','Set-ItemProperty','Remove-ItemProperty','iex ','Invoke-Expression']:
                self.assertNotIn(forbidden, s)

    def test_static_javascript_is_served(self):
        httpd=app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        port=httpd.server_port
        th=threading.Thread(target=httpd.serve_forever,daemon=True)
        th.start()
        try:
            c=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
            for filename in ['app.js','extra.js','workstation.js','selection.js','upgrade.js','video_tools.js']:
                c.request('GET','/static/'+filename,headers={'Host':'127.0.0.1:'+str(port)})
                r=c.getresponse()
                result=r.read()
                self.assertEqual(r.status,200, filename)
                self.assertGreater(len(result),500,filename)
            c.close()
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_unknown_script_is_rejected_and_local_shutdown_runs_directly(self):
        app.initialize()
        httpd=app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        port=httpd.server_port
        th=threading.Thread(target=httpd.serve_forever,daemon=True)
        th.start()
        try:
            c=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
            headers={'Host':'127.0.0.1:'+str(port),'X-Fleury-Token':app.TOKEN}
            c.request('GET','/api/diagnostics/remote-console?target=192.168.0.10&type=bad',headers=headers)
            r=c.getresponse();d=json.loads(r.read());self.assertEqual(r.status,400);self.assertIn('não permitida',d['error'])
            headers['Content-Type']='application/json'
            c.request('POST','/api/system/shutdown',body=json.dumps({}),headers=headers)
            r=c.getresponse();r.read();self.assertEqual(r.status,200)
            c.close()
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_packager_includes_portable_marker_and_inno(self):
        script=(ROOT/'build_windows.py').read_text('utf8')
        self.assertIn('PORTABLE_MODE',script)
        self.assertIn('PyInstaller',script)
        self.assertIn('instalador.iss',script)
        self.assertIn('LEIA_PRIMEIRO.txt',script)
        self.assertTrue((ROOT/'launcher.py').exists())
        s=(ROOT/'app.py').read_text('utf8')
        self.assertIn("_MEIPASS",s)
        self.assertIn('LOCALAPPDATA',s)

    def test_global_picker_and_additional_menu(self):
        s=(ROOT/'static/video_tools.js').read_text('utf8')
        self.assertIn('Console de Diagnóstico',s)
        self.assertIn('remote-readonly',s)
        self.assertIn('Encerrar aplicativo',s)
        h=(ROOT/'static/index.html').read_text('utf8')
        self.assertIn('/static/video_tools.js',h)
        self.assertIn('global-machine-picker',h)

if __name__=='__main__':unittest.main()
