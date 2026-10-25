"""Drivers locais reais e respostas de impressão simuladas; sem hardware."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import printer_support as printers


class PrinterSupportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entry = dict(id='zd421', title='Driver de homologação', models=['ZD421'],
                          driver_name='ZDesigner ZD421-203dpi ZPL', reviewed=True)
        self.save()

    def save(self, entry=None):
        (self.root / 'manifest.json').write_text(json.dumps({'packages': [entry or self.entry]}), encoding='utf-8')

    def test_installed_only_catalog_does_not_claim_package_verification(self):
        package = printers.driver_catalog(self.root)['packages'][0]
        self.assertTrue(package['reviewed'])
        self.assertFalse(package['verified'])
        self.assertFalse(package['package_present'])
        self.assertNotIn(str(self.root), json.dumps(package))

    def test_local_inf_checksum_is_checked_every_read(self):
        inf = self.root / 'driver.inf'
        inf.write_bytes(b'Fake INF for test only')
        self.entry.update(inf='driver.inf', sha256=hashlib.sha256(inf.read_bytes()).hexdigest())
        self.save()
        self.assertTrue(printers.driver_catalog(self.root)['packages'][0]['verified'])
        inf.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            printers.driver_catalog(self.root)

    def test_unsafe_manifest_does_not_reach_remote_machine(self):
        for changes in ({'reviewed': False}, {'driver_name': 'Untrusted Driver'},
                        {'models': ['.*']}, {'inf': '../outside.inf', 'sha256': '0' * 64},
                        {'inf': 'missing.inf'}, {'driver_name': 'ZDesigner*'}):
            with self.subTest(changes=changes):
                self.save({**self.entry, **changes})
                remote = Mock()
                with self.assertRaises(ValueError):
                    printers.switch_driver(remote, 'PC-SIM', 'Zebra ZD421', 'zd421', self.root)
                remote.assert_not_called()

    def test_symlink_inf_is_rejected(self):
        outside = self.root / 'original.inf'
        outside.write_bytes(b'fake')
        link = self.root / 'link.inf'
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest('Creation of symlinks unavailable on this runner')
        self.entry.update(inf='link.inf', sha256=hashlib.sha256(b'fake').hexdigest())
        self.save()
        with self.assertRaises(ValueError):
            printers.driver_catalog(self.root)

    def test_common_and_zebra_faults_have_guidance_without_printing(self):
        for code, expected in ((4, 'paper_out'), (8, 'paper_jam'), (7, 'cover_open'), (9, 'printer_offline')):
            for zebra in (True, False):
                with self.subTest(code=code, zebra=zebra):
                    result = printers.assess_diagnostics(dict(Nome='SIM', Spooler='Running',
                        ErroDetectado=code, Zebra=zebra, FalhasFila=1, TesteTCP='Tempo limite TCP'))
                    self.assertFalse(result['healthy'])
                    codes = [item['code'] for item in result['issues']]
                    self.assertIn(expected, codes)
                    self.assertIn('queue_error', codes)
                    self.assertIn('network_unreachable', codes)
                    self.assertTrue(result['guidance'])

    def test_remaining_jobs_or_failed_spooler_are_partial(self):
        remote = Mock(return_value=dict(Encontrados=3, Removidos=2, Restantes=1, Falhas=1, Spooler='Running'))
        self.assertFalse(printers.clear_queue(remote, 'PC-SIM', 'Laser comum')['ok'])
        self.assertEqual(json.loads(remote.call_args.args[3]), {'printer': 'Laser comum'})
        remote.return_value = dict(Encontrados=1, Removidos=1, Restantes=0, Falhas=0, Spooler='Stopped')
        self.assertTrue(printers.clear_queue(remote, 'PC-SIM', 'Laser comum')['partial'])
        remote.return_value = {'Spooler': 'Stopped'}
        self.assertFalse(printers.restart_spooler(remote, 'PC-SIM')['ok'])
        remote.side_effect = RuntimeError('SIM: WinRM timeout')
        with self.assertRaises(RuntimeError):
            printers.restart_spooler(remote, 'PC-SIM')

    def test_change_requires_catalog_entry_and_verifies_returned_driver(self):
        remote = Mock(return_value={'DriverAnterior': 'ZDesigner antigo', 'DriverAtual': self.entry['driver_name']})
        self.assertTrue(printers.switch_driver(remote, 'PC-SIM', 'Zebra ZD421', 'zd421', self.root)['ok'])
        script, config = remote.call_args.args[1], json.loads(remote.call_args.args[3])
        self.assertEqual(script, printers.SWITCH_DRIVER_PS)
        self.assertEqual(config['models'], ['ZD421'])
        self.assertEqual(config['driver_name'], self.entry['driver_name'])
        remote.return_value['DriverAtual'] = 'ZDesigner antigo'
        self.assertFalse(printers.switch_driver(remote, 'PC-SIM', 'Zebra ZD421', 'zd421', self.root)['ok'])
        remote.reset_mock()
        for printer, ident in (('Zebra*', 'zd421'), ('Zebra ZD421', 'arbitrary')):
            with self.assertRaises(ValueError):
                printers.switch_driver(remote, 'PC-SIM', printer, ident, self.root)
        remote.assert_not_called()

    def test_malformed_responses_do_not_produce_success(self):
        for response in (None, {}, {'Restantes': 0}, {'Encontrados': True, 'Removidos': 0, 'Restantes': 0, 'Falhas': 0}):
            with self.subTest(response=response), self.assertRaises(RuntimeError):
                printers.clear_queue(Mock(return_value=response), 'PC-SIM', 'Laser')


if __name__ == '__main__':
    unittest.main()
