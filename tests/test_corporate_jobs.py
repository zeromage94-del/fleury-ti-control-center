"""Stateful corporate installation simulation; no process or network may escape.

The fake WinRM host models machine software state and failures. It does not run
PowerShell/WinGet, and therefore does not certify individual vendors' installers.
"""
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import software_catalog
import software_jobs


class CorporateHost:
    def __init__(self, admin=True, winget=True, transport=True, failures=None):
        self.admin, self.winget, self.transport = admin, winget, transport
        self.failures = failures or {}
        self.installed = set()
        self.calls = []

    def execute(self, target, operation, ids):
        self.calls.append((target, operation, list(ids)))
        if not self.transport:
            raise RuntimeError('Tempo limite WinRM no computador lento simulado.')
        if not self.admin:
            raise RuntimeError('Identidade WinRM sem privilégios administrativos.')
        if not self.winget:
            raise RuntimeError('WinGet indisponível no contexto WinRM.')
        items = []
        for package in ids:
            code = self.failures.get(package, 0)
            if code in software_jobs.SUCCESS_CODES:
                if operation == 'install':
                    self.installed.add(package)
                else:
                    self.installed.discard(package)
            items.append({'Pacote': package, 'CodigoSaida': code, 'Escopo': 'machine'})
        return {'Computador': target, 'Escopo': 'machine',
                'Instalacoes' if operation == 'install' else 'Desinstalacoes': items}


class CorporateJobs(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.stack.enter_context(patch.object(app, 'DB', Path(self.temp) / 'jobs.db'))
        for owner, name in ((app.subprocess, 'run'), (app.subprocess, 'Popen'),
                            (app.socket, 'create_connection')):
            self.stack.enter_context(patch.object(owner, name, side_effect=AssertionError('Unsimulated I/O')))
        app.initialize()
        self.managers = []
        self.addCleanup(self.finish_managers)

    def finish_managers(self):
        for manager in self.managers:
            manager.pool.shutdown(wait=True)

    def manager(self, execute):
        manager = software_jobs.Manager(app.db, app.audit, app.now, execute)
        self.managers.append(manager)
        return manager

    def submit(self, manager, operation='install', keys=None, target='PC-SIM'):
        keys = keys or ['7zip', 'firefox']
        return manager.submit(target, operation, keys, software_catalog.validate_packages(keys))

    def test_all_catalog_packages_install_and_uninstall_in_batches(self):
        host = CorporateHost()
        keys = [entry['key'] for entry in software_catalog.catalog()]
        expected = {entry['winget_id'] for entry in software_catalog.catalog()}
        self.assertGreater(len(expected), 20)
        for operation in ('install', 'uninstall'):
            manager = self.manager(host.execute)
            for index in range(0, len(keys), 20):
                self.submit(manager, operation, keys[index:index + 20])
            manager.pool.shutdown(wait=True)
            rows = manager.list()
            self.assertTrue(all(row['state'] == 'succeeded' for row in rows))
            self.assertEqual(host.installed, expected if operation == 'install' else set())
        self.assertTrue(all(row['success'] for row in app.rows('SELECT * FROM audit')))

    def test_partial_disk_failure_keeps_successes_and_raw_result(self):
        host = CorporateHost(failures={'Mozilla.Firefox': 112})
        manager = self.manager(host.execute)
        self.submit(manager)
        manager.pool.shutdown(wait=True)
        job = manager.list()[0]
        self.assertEqual(job['state'], 'failed')
        self.assertEqual(host.installed, {'7zip.7zip'})
        self.assertEqual(job['result']['Resumo']['Concluidos'], 1)
        self.assertEqual(job['result']['Resumo']['Falhas'], 1)
        self.assertEqual(job['result']['Instalacoes'][1]['CodigoSaida'], 112)
        self.assertEqual(app.rows('SELECT success FROM audit ORDER BY id DESC LIMIT 1')[0]['success'], 0)

    def test_reboot_required_and_initiated_are_reported(self):
        host = CorporateHost(failures={'7zip.7zip': 3010, 'Mozilla.Firefox': 1641})
        manager = self.manager(host.execute)
        self.submit(manager)
        manager.pool.shutdown(wait=True)
        job = manager.list()[0]
        self.assertEqual(job['state'], 'succeeded')
        self.assertTrue(job['result']['Resumo']['ReinicioNecessario'])
        self.assertTrue(job['result']['Resumo']['ReinicioIniciadoPeloInstalador'])

    def test_transport_permissions_and_missing_winget_fail_without_installing(self):
        for kwargs in ({'transport': False}, {'admin': False}, {'winget': False}):
            with self.subTest(kwargs=kwargs):
                host = CorporateHost(**kwargs)
                manager = self.manager(host.execute)
                self.submit(manager, target='PC-' + str(len(self.managers)))
                manager.pool.shutdown(wait=True)
                job = manager.list()[0]
                self.assertEqual(job['state'], 'failed')
                self.assertTrue(job['error'])
                self.assertFalse(host.installed)
                self.assertEqual(len(host.calls), 1)

    def test_divergent_missing_duplicate_or_user_scope_never_succeeds(self):
        ids = ['7zip.7zip', 'Mozilla.Firefox']
        good = [{'Pacote': ident, 'CodigoSaida': 0, 'Escopo': 'machine'} for ident in ids]
        responses = [None, [], {'Escopo': 'machine'},
                     {'Escopo': 'machine', 'Instalacoes': [good[0], good[0]]},
                     {'Escopo': 'machine', 'Instalacoes': [good[0]]},
                     {'Escopo': 'machine', 'Instalacoes': good + [good[0]]},
                     {'Escopo': 'machine', 'Instalacoes': [{**good[0], 'Pacote': 'Other.ID'}, good[1]]},
                     {'Escopo': 'user', 'Instalacoes': good},
                     {'Escopo': 'machine', 'Instalacoes': [{**good[0], 'Escopo': 'user'}, good[1]]},
                     {'Escopo': 'machine', 'Instalacoes': [{**good[0], 'CodigoSaida': False}, good[1]]},
                     {'Escopo': 'machine', 'Instalacoes': ['bad', 'response']}]
        for index, response in enumerate(responses):
            with self.subTest(response=response):
                manager = self.manager(lambda *args, result=response: result)
                self.submit(manager, target=f'PC-BAD-{index}')
                manager.pool.shutdown(wait=True)
                self.assertEqual(manager.list()[0]['state'], 'failed')

    def test_executor_closed_does_not_leave_phantom_queued_job(self):
        host = CorporateHost()
        manager = self.manager(host.execute)
        manager.pool.shutdown(wait=True)
        with self.assertRaises(RuntimeError):
            self.submit(manager)
        self.assertEqual(manager.list()[0]['state'], 'failed')
        self.assertFalse(host.calls)

    def test_concurrency_two_hosts_and_serialization_for_same_host(self):
        gate = threading.Event()
        two_entered = threading.Event()
        lock = threading.Lock()
        active, violations, calls = set(), [], []
        def execute(target, operation, ids):
            with lock:
                if target.lower() in active or len(active) >= 2:
                    violations.append(target)
                active.add(target.lower())
                calls.append((target.lower(), operation))
                if len(active) == 2:
                    two_entered.set()
            try:
                if not gate.wait(3):
                    raise RuntimeError('Simulation gate timed out')
                return CorporateHost().execute(target, operation, ids)
            finally:
                with lock:
                    active.remove(target.lower())
        manager = self.manager(execute)
        try:
            first = self.submit(manager, target='PC-A')
            duplicate = self.submit(manager, target='pc-a')
            self.assertEqual(first['job_id'], duplicate['job_id'])
            self.assertTrue(duplicate['duplicate'])
            self.submit(manager, target='PC-B')
            self.assertTrue(two_entered.wait(2))
            self.submit(manager, operation='uninstall', target='pc-a')
        finally:
            gate.set()
        manager.pool.shutdown(wait=True)
        self.assertFalse(violations)
        self.assertEqual(len(calls), 3)
        self.assertEqual([x[1] for x in calls if x[0] == 'pc-a'], ['install', 'uninstall'])
        self.assertTrue(all(job['state'] == 'succeeded' for job in manager.list()))

    def test_recovery_is_idempotent_and_never_retries_automatically(self):
        host = CorporateHost()
        manager = self.manager(host.execute)
        self.submit(manager)
        manager.pool.shutdown(wait=True)
        with app.db() as db:
            db.execute("UPDATE software_jobs SET state='running'")
        manager.recover()
        manager.recover()
        self.assertEqual(manager.list()[0]['state'], 'interrupted')
        self.assertEqual(len(host.calls), 1)

    def test_catalog_limit_ids_and_operation_enforced_before_queue(self):
        host = CorporateHost()
        manager = self.manager(host.execute)
        for operation, keys, ids in [('execute', ['7zip'], ['7zip.7zip']),
                                     ('install', ['7zip'], ['Other.ID']),
                                     ('install', ['7zip'] * 21, ['7zip.7zip'] * 21),
                                     ('install', ['unknown'], ['Unknown.ID'])]:
            with self.subTest(operation=operation, keys=keys):
                with self.assertRaises(ValueError):
                    manager.submit('PC-SIM', operation, keys, ids)
        self.assertFalse(manager.list())
        self.assertFalse(host.calls)


if __name__ == '__main__':
    unittest.main()
