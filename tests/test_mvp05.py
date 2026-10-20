"""Testes não-destrutivos: não executa comandos Windows ou acessa rede corporativa."""
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maintenance
import app


class ValidationTests(unittest.TestCase):
    def test_restore_description(self):
        self.assertEqual(maintenance.validate_restore_desc(' Criar antes da manutenção '), 'Criar antes da manutenção')
        for value in ('ok', 'x'*101, None, 'fundo\nexclusao'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                maintenance.validate_restore_desc(value)

    def test_restore_sequence(self):
        for bad in ('0', '1;stop', '-1', '4294967296', True, None, '01'):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                maintenance.validate_restore_sequence(bad)
        self.assertEqual(maintenance.validate_restore_sequence(123), 123)

    def test_restore_delete_script_guard(self):
        ps = maintenance.RESTORE_DELETE_PS
        for guard in ('$all.Count -lt 2', '$date -gt (Get-Date).AddDays(-14)',
                      '$latestDate -lt (Get-Date).AddDays(-7)', 'SRRemoveRestorePoint'):
            self.assertIn(guard, ps)
        self.assertNotIn('vssadmin.exe', ps.lower())

    def test_cleanup_only_ephemeral_extensions(self):
        self.assertIn("'.tmp','.temp'", maintenance.CLEANUP_PS)
        self.assertNotIn("'.tmp','.temp','.log'", maintenance.CLEANUP_PS)
        self.assertNotIn('Remove-Item -Recurse', maintenance.CLEANUP_PS)


class WebHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.old_db = app.DB
        app.DB = Path(cls.tempdir.name) / 'test.db'
        app.initialize()
        app.save_machine('PC-TESTE-01', name='Teste', origin='Teste')
        cls.old_win = app.WIN
        app.WIN = True
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.server.cleanup_previews = {}
        cls.server.restore_previews = {}
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        app.WIN = cls.old_win
        app.DB = cls.old_db
        cls.tempdir.cleanup()

    def send(self, path, body=None, authorized=True):
        url = f'http://127.0.0.1:{self.server.server_port}{path}'
        headers={'X-Fleury-Token': app.TOKEN if authorized else 'badtoken'}
        data = None if body is None else json.dumps(body).encode('utf-8')
        if data is not None: headers['Content-Type']='application/json'
        req = Request(url, data=data, headers=headers)
        with urlopen(req, timeout=10) as resp:
            return resp.status, json.load(resp)

    def test_missing_token_rejected(self):
        with self.assertRaises(HTTPError) as err:
            self.send('/api/maintenance/restore-points?target=PC-TESTE-01', authorized=False)
        self.assertEqual(err.exception.code, 403)

    def test_list_then_delete_with_preview(self):
        points={'Computador':'PC-TESTE-01','Pontos':[
            {'Numero':23,'Descricao':'Recentemente','CriadoEm':'2026-10-19','IdadeDias':1,'MaisRecente':True},
            {'Numero':12,'Descricao':'Antigo','CriadoEm':'2026-09-12','IdadeDias':38,'MaisRecente':False}]}
        with patch.object(app, 'restore_points', return_value=points) as list_mock, \
             patch.object(app, 'delete_restore_point', return_value={'Removido':True,'Numero':12}) as del_mock:
            status, obj = self.send('/api/maintenance/restore-points?target=PC-TESTE-01')
            self.assertEqual(status, 200)
            self.assertEqual(len(obj['result']['Pontos']), 2)
            _, out=self.send('/api/maintenance/restore-delete', {'target':'PC-TESTE-01','sequence':12,'confirm':True})
            self.assertTrue(out['result']['Removido'])
            del_mock.assert_called_once_with('PC-TESTE-01',12)
            # Não repetir exclusão com prévia expirada/consumida.
            with self.assertRaises(HTTPError) as err:
                self.send('/api/maintenance/restore-delete', {'target':'PC-TESTE-01','sequence':12,'confirm':True})
            self.assertEqual(err.exception.code,400)

    def test_create_requires_confirm(self):
        with patch.object(app, 'create_restore_point') as create_mock:
            with self.assertRaises(HTTPError) as err:
                self.send('/api/maintenance/restore-create', {'target':'PC-TESTE-01','description':'Manutencao valida'})
            self.assertEqual(err.exception.code,400)
            create_mock.assert_not_called()

    def test_quick_script_avoids_unsafe_tweaks(self):
        self.assertIn("$cleanup = & {", maintenance.QUICK_OPTIMIZE_PS)
        self.assertIn("'.tmp','.temp'", maintenance.QUICK_OPTIMIZE_PS)
        self.assertNotIn('Remove-Item -Recurse', maintenance.QUICK_OPTIMIZE_PS)
        self.assertNotIn('Set-MpPreference', maintenance.QUICK_OPTIMIZE_PS)
        self.assertNotIn('Uninstall-', maintenance.QUICK_OPTIMIZE_PS)

    def test_cleanup_direct_without_simulation(self):
        with patch.object(app, 'cleanup_temps', return_value={
            'ArquivosRemovidos':5, 'LiberadosMB':2.5, 'Falhas':0}) as cleanup:
            _, result = self.send('/api/maintenance/cleanup', {
                'target':'PC-TESTE-01','days':14,'confirm':True})
            self.assertEqual(result['result']['ArquivosRemovidos'], 5)
            cleanup.assert_called_once_with('PC-TESTE-01', 14, True)

    def test_cleanup_rejects_without_technician_confirmation(self):
        with patch.object(app, 'cleanup_temps') as cleanup:
            with self.assertRaises(HTTPError) as err:
                self.send('/api/maintenance/cleanup', {'target':'PC-TESTE-01','days':14})
            self.assertEqual(err.exception.code,400)
            cleanup.assert_not_called()

    def test_quick_optimize_uses_selected_machine(self):
        result={'Limpeza':{'ArquivosRemovidos':1,'LiberadosMB':1.2,'Falhas':0}}
        with patch.object(app.maintenance, 'call', return_value=result) as call:
            _, data=self.send('/api/maintenance/quick-optimize', {
                'target':'PC-TESTE-01','days':14,'confirm':True})
            self.assertEqual(data['result'], result)
            self.assertEqual(call.call_args.args[1], 'PC-TESTE-01')
            self.assertEqual(call.call_args.args[2], maintenance.QUICK_OPTIMIZE_PS)
            self.assertEqual(call.call_args.args[3], {'days':14,'commit':True})

    def test_unknown_machine_blocked(self):
        with patch.object(app, 'cleanup_temps') as cleanup:
            with self.assertRaises(HTTPError) as err:
                self.send('/api/maintenance/cleanup', {
                    'target':'PC-OUTRO-01','days':14,'confirm':True})
            self.assertEqual(err.exception.code, 400)
            cleanup.assert_not_called()

    def test_local_dashboard(self):
        status, obj=self.send('/api/status')
        self.assertEqual(status,200)
        self.assertIn('machines',obj)


if __name__ == '__main__':
    unittest.main(verbosity=2)
