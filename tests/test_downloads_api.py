"""HTTP e arquivos temporários reais; limpeza WinRM integral simulada."""
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
        self.stack.enter_context(patch.object(app, 'DOWNLOADS_ACTIVE', set()))
        self.remote = self.stack.enter_context(patch.object(app, 'remote_script', side_effect=self.execute))
        self.calls = []
        self.locked = set()
        self.files = []
        for user, filename in (('Alice', 'recent.pdf'), ('Bob', 'installer.exe'), ('Alice', 'sub/part.crdownload')):
            path = self.root / user / 'Downloads' / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fictional file')
            self.files.append(path)
        self.outside = self.root / 'Alice' / 'Documents' / 'keep.pdf'
        self.outside.parent.mkdir()
        self.outside.write_bytes(b'preserve outside Downloads')
        app.initialize()
        for target, kind in (('PC-SIM', 'computer'), ('PRN-SIM', 'printer')):
            app.save_machine(target)
            with app.db() as db:
                db.execute('UPDATE machines SET device_type=? WHERE target=?', (kind, target))
        self.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.stack.callback(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def execute(self, target, script, timeout, argument):
        self.assertEqual(target, 'PC-SIM')
        self.assertEqual(script, maintenance.DOWNLOADS_PS)
        self.assertEqual(timeout, 900)
        config = json.loads(argument)
        self.assertEqual(config, {})
        self.calls.append(config)
        found = removed = failures = freed = 0
        for path in self.files:
            if not path.exists():
                continue
            found += 1
            if path in self.locked:
                failures += 1
            else:
                freed += path.stat().st_size
                path.unlink()
                removed += 1
        return dict(PerfisInspecionados=2, PastasDownloads=2, PastasIgnoradas=0,
                    ArquivosEncontrados=found, ArquivosRemovidos=removed,
                    Falhas=failures, Ignorados=0, BytesLiberados=freed)

    def request(self, path='/api/maintenance/downloads-cleanup', body=None, token=True):
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

    def test_one_post_clears_all_users_without_preview_selection_age_or_confirmation(self):
        status, result = self.request(body={'target': 'PC-SIM'})
        self.assertEqual(status, 200)
        self.assertTrue(result['ok'])
        self.assertEqual(result['result']['ArquivosRemovidos'], 3)
        self.assertTrue(all(not path.exists() for path in self.files))
        self.assertTrue(self.outside.exists())
        self.assertEqual(len(self.calls), 1)
        logs = app.rows('SELECT * FROM audit')
        self.assertEqual(logs[-1]['target'], 'PC-SIM')
        self.assertNotIn('recent.pdf', str(logs))

    def test_session_computer_and_windows_are_checked_before_io(self):
        self.assertEqual(self.request(body={'target': 'PC-SIM'}, token=False)[0], 403)
        for target in ('UNREGISTERED', 'PRN-SIM', 'PC-SIM;bad'):
            with self.subTest(target=target):
                self.assertEqual(self.request(body={'target': target})[0], 400)
        with patch.object(app, 'WIN', False):
            self.assertEqual(self.request(body={'target': 'PC-SIM'})[0], 400)
        self.remote.assert_not_called()
        self.assertTrue(all(path.exists() for path in self.files))

    def test_get_requests_never_delete_and_old_preview_route_is_gone(self):
        self.assertEqual(self.request()[0], 404)
        self.assertEqual(self.request('/api/maintenance/downloads-preview?target=PC-SIM')[0], 404)
        self.remote.assert_not_called()

    def test_partial_failure_cleans_other_profiles_and_audits_failure(self):
        self.locked.add(self.files[0])
        _, result = self.request(body={'target': 'PC-SIM'})
        self.assertFalse(result['ok'])
        self.assertTrue(result['partial'])
        self.assertEqual(result['result']['ArquivosRemovidos'], 2)
        self.assertTrue(self.files[0].exists())
        self.assertTrue(all(not path.exists() for path in self.files[1:]))
        self.assertEqual(app.rows('SELECT success FROM audit ORDER BY id DESC LIMIT 1')[0]['success'], 0)

    def test_malformed_results_and_ignored_folders_never_report_full_success(self):
        valid = dict(PerfisInspecionados=2, PastasDownloads=2, PastasIgnoradas=0,
                     ArquivosEncontrados=0, ArquivosRemovidos=0, Falhas=0, Ignorados=0)
        self.remote.side_effect = None
        for response in (None, {}, {**valid, 'ArquivosRemovidos': True}, {**valid, 'ArquivosRemovidos': 1}):
            with self.subTest(response=response):
                self.remote.return_value = response
                self.assertEqual(self.request(body={'target': 'PC-SIM'})[0], 400)
                self.assertFalse(app.DOWNLOADS_ACTIVE)
        self.remote.return_value = {**valid, 'PastasIgnoradas': 1, 'Ignorados': 1}
        _, result = self.request(body={'target': 'PC-SIM'})
        self.assertFalse(result['ok'])
        self.assertTrue(result['partial'])

    def test_timeout_does_not_retry_and_releases_active_marker(self):
        self.remote.side_effect = RuntimeError('SIM timeout; outcome unknown')
        self.assertEqual(self.request(body={'target': 'PC-SIM'})[0], 400)
        self.remote.assert_called_once()
        self.assertFalse(app.DOWNLOADS_ACTIVE)
        self.assertEqual(app.rows('SELECT success FROM audit ORDER BY id DESC LIMIT 1')[0]['success'], 0)

    def test_concurrent_click_for_same_computer_is_not_executed_twice(self):
        entered, release = threading.Event(), threading.Event()
        result = []
        def blocked(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('SIM test timed out')
            return self.execute(*args)
        self.remote.side_effect = blocked
        thread = threading.Thread(target=lambda: result.append(self.request(body={'target': 'PC-SIM'})))
        thread.start()
        try:
            self.assertTrue(entered.wait(3))
            self.assertEqual(self.request(body={'target': 'PC-SIM'})[0], 400)
            self.assertEqual(self.remote.call_count, 1)
        finally:
            release.set()
            thread.join(5)
        self.assertEqual(result[0][0], 200)
        self.assertFalse(app.DOWNLOADS_ACTIVE)


if __name__ == '__main__':
    unittest.main()
