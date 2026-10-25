"""HTTP e arquivos temporários reais; perfis Windows e WinRM simulados."""
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import maintenance


class DownloadsAPITests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(app, 'DB', self.root / 'test.db'))
        self.stack.enter_context(patch.object(app, 'WIN', True))
        self.remote = self.stack.enter_context(patch.object(app, 'remote_script', side_effect=self.execute))
        self.calls = []
        self.files = {}
        self.records = []
        for user, filename in (('Alice', 'old.pdf'), ('Bob', 'installer.exe')):
            path = self.root / user / filename
            path.parent.mkdir()
            path.write_bytes(b'fictional file')
            windows = 'C:\\Users\\' + user + '\\Downloads\\' + filename
            self.files[windows] = path
            self.records.append(dict(path=windows, root='C:\\Users\\' + user + '\\Downloads',
                profile='C:\\Users\\' + user, size=path.stat().st_size,
                mtime_ticks='638000000000000000', creation_ticks='637000000000000000'))
        app.initialize()
        for target in ('PC-SIM', 'PC-OTHER'):
            app.save_machine(target)
            with app.db() as db:
                db.execute("UPDATE machines SET device_type='computer' WHERE target=?", (target,))
        self.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.server.downloads_previews = {}
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.stack.callback(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def execute(self, target, script, timeout, argument):
        self.assertEqual(script, maintenance.DOWNLOADS_PS)
        config = json.loads(argument)
        self.calls.append(config)
        if not config['commit']:
            return dict(Arquivos=[x for x in self.records if self.files[x['path']].exists()],
                        Falhas=0, LimiteAtingido=False)
        removed = failures = 0
        for entry in config['files']:
            path = self.files[entry['path']]
            if path.exists() and path.stat().st_size == entry['size']:
                path.unlink()
                removed += 1
            else:
                failures += 1
        return dict(ArquivosRemovidos=removed, Falhas=failures, LimiteAtingido=False)

    def request(self, path, body=None, token=True):
        headers = {'X-Fleury-Token': app.TOKEN} if token else {}
        data = None if body is None else json.dumps(body).encode()
        if data:
            headers['Content-Type'] = 'application/json'
        try:
            response = urlopen(Request('http://127.0.0.1:' + str(self.server.server_port) + path,
                                       data=data, headers=headers), timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def preview(self):
        status, result = self.request('/api/maintenance/downloads-preview?target=PC-SIM&days=30')
        self.assertEqual(status, 200, result)
        return result

    def body(self, preview, **changes):
        return dict(target='PC-SIM', preview_id=preview['preview_id'],
                    files=[preview['files'][0]['id']], confirm=True, **changes)

    def test_preview_then_selected_file_only_and_replay_rejected(self):
        preview = self.preview()
        self.assertEqual(len(preview['files']), 2)
        self.assertNotIn('C:\\Users', json.dumps(preview))
        self.assertTrue(all(path.exists() for path in self.files.values()))
        status, result = self.request('/api/maintenance/downloads-cleanup', self.body(preview))
        self.assertEqual(status, 200)
        self.assertTrue(result['ok'])
        self.assertFalse(next(iter(self.files.values())).exists())
        self.assertTrue(list(self.files.values())[1].exists())
        self.assertEqual(self.calls[-1]['days'], 30)
        self.assertEqual(self.request('/api/maintenance/downloads-cleanup', self.body(preview))[0], 400)
        self.assertEqual(len(self.calls), 2)

    def test_session_confirmation_target_and_ids_are_checked_before_io(self):
        self.assertEqual(self.request('/api/maintenance/downloads-preview?target=PC-SIM', token=False)[0], 403)
        preview = self.preview()
        original = self.body(preview)
        for changes in ({'confirm': False}, {'target': 'PC-OTHER'}, {'files': []},
                        {'files': ['C:\\Users\\Alice\\Downloads\\old.pdf']},
                        {'files': [preview['files'][0]['id']] * 2}, {'preview_id': 'bad'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.request('/api/maintenance/downloads-cleanup', {**original, **changes})[0], 400)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(all(path.exists() for path in self.files.values()))

    def test_expired_or_replaced_preview_cannot_delete(self):
        old = self.preview()
        new = self.preview()
        self.assertEqual(self.request('/api/maintenance/downloads-cleanup', self.body(old))[0], 400)
        self.server.downloads_previews[new['preview_id']]['at'] -= 301
        self.assertEqual(self.request('/api/maintenance/downloads-cleanup', self.body(new))[0], 400)
        self.assertEqual(len(self.calls), 2)

    def test_changed_file_preserved_and_partial_result_audited(self):
        preview = self.preview()
        next(iter(self.files.values())).write_bytes(b'changed after preview')
        _, result = self.request('/api/maintenance/downloads-cleanup', self.body(preview))
        self.assertFalse(result['ok'])
        self.assertTrue(result['partial'])
        self.assertTrue(all(path.exists() for path in self.files.values()))
        self.assertEqual(app.rows('SELECT success FROM audit ORDER BY id DESC LIMIT 1')[0]['success'], 0)

    def test_timeout_consumes_preview_without_retry(self):
        preview = self.preview()
        self.remote.side_effect = RuntimeError('SIM timeout; outcome unknown')
        self.assertEqual(self.request('/api/maintenance/downloads-cleanup', self.body(preview))[0], 400)
        self.remote.reset_mock()
        self.assertEqual(self.request('/api/maintenance/downloads-cleanup', self.body(preview))[0], 400)
        self.remote.assert_not_called()


if __name__ == '__main__':
    unittest.main()
