"""Rede determinística sem sondagens a equipamentos corporativos."""
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import device_discovery as discovery


class CorporateDiscoveryTests(unittest.TestCase):
    def test_slow_tcp_computer_and_two_printer_protocols_without_ping(self):
        inventory = {'10.77.1.1': {5985}, '10.77.1.2': {631}, '10.77.1.3': {9100}}
        seen = []
        def connect(address, timeout):
            host, port = address
            seen.append(address)
            if timeout < 0.4 or port not in inventory[host]:
                raise TimeoutError('SIM: 400ms or filtered')
            return MagicMock()
        ping = Mock(return_value=False)
        with patch.object(discovery.socket, 'create_connection', side_effect=connect):
            for host, kind in zip(inventory, ('computer', 'printer', 'printer')):
                info = discovery.probe(host, ping)
                self.assertTrue(info['alive'])
                self.assertEqual(info['device_type'], kind)
        ping.assert_not_called()
        self.assertEqual(len(seen), 3 * len(discovery.PORTS))

    def test_filtered_host_is_unknown_and_timeouts_are_counted(self):
        with patch.object(discovery.socket, 'create_connection', side_effect=TimeoutError('SIM')):
            info = discovery.probe('10.77.1.9', lambda target: False)
        self.assertFalse(info['alive'])
        self.assertEqual(info['device_type'], 'unknown')
        self.assertEqual(info['timed_out_ports'], len(discovery.PORTS))

    def test_input_validation_and_deduplication_cover_larger_private_networks(self):
        self.assertEqual(discovery.validate_segments(['10.0.0.0/20', '10.0.1.0/24']), ['10.0.0.0/20'])
        for invalid in (None, [], [True], [123], [''], ['8.8.8.0/24'], ['::1/128'],
                        ['10.0.0.0/19'], ['10.0.0.0/20', '10.0.16.0/20']):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                discovery.validate_segments(invalid)

    def test_single_host_error_keeps_other_results_and_updates_stale_status(self):
        with ExitStack() as stack:
            root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            stack.enter_context(patch.object(app, 'DB', root / 'test.db'))
            app.initialize()
            app.save_machine('10.77.1.2', status='Online')
            def probe(target, ping):
                if target.endswith('.2'):
                    raise OSError('SIM: host failed')
                return dict(alive=True, device_type='computer', evidence='SIM TCP')
            stack.enter_context(patch.object(discovery, 'probe', side_effect=probe))
            result = app.scan_targets(['10.77.1.1', '10.77.1.2', '10.77.1.1'])
            self.assertEqual(result['found'], 1)
            self.assertEqual(result['scanned'], 2)
            self.assertEqual(result['unresponsive'], 1)
            self.assertEqual(len(result['errors']), 1)
            self.assertEqual(app.rows("SELECT status FROM machines WHERE target='10.77.1.2'")[0]['status'], 'Sem resposta')


if __name__ == '__main__':
    unittest.main()
