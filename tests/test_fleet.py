import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
import device_discovery
import software_catalog
import software_jobs


class DiscoveryTests(unittest.TestCase):
    def test_types_need_service_evidence(self):
        self.assertEqual(device_discovery.classify([9100])[0],'printer')
        self.assertEqual(device_discovery.classify([631])[0],'printer')
        self.assertEqual(device_discovery.classify([5985,9100])[0],'computer')
        self.assertEqual(device_discovery.classify([443])[0],'unknown')

    def test_network_scope_and_deduplication(self):
        self.assertEqual(device_discovery.validate_segments(['192.168.1.2/24','192.168.1.0/24']),['192.168.1.0/24'])
        for values in ([],['8.8.8.0/24'],['10.0.0.0/16'],['::1/128'],['bad'],['10.0.0.0/24']*9):
            with self.assertRaises(ValueError):device_discovery.validate_segments(values)

    def test_detection_does_not_depend_on_ping(self):
        ping=MagicMock(return_value=False)
        def connect(address,timeout):
            if address[1]==9100:return MagicMock()
            raise OSError('filtered')
        with patch.object(device_discovery.socket,'create_connection',side_effect=connect):
            info=device_discovery.probe('192.168.1.9',ping)
        self.assertTrue(info['alive']);self.assertEqual(info['device_type'],'printer')
        ping.assert_not_called()

    def test_real_interface_mask_and_larger_network(self):
        with patch.object(app,'ps_json',return_value=[{'IPAddress':'192.168.2.9','PrefixLength':23}]):
            self.assertEqual(app.local_segments(),['192.168.2.0/23'])
        self.assertEqual(device_discovery.validate_segments(['10.0.0.0/20','10.0.1.0/24']),['10.0.0.0/20'])
        with self.assertRaises(ValueError):
            device_discovery.validate_segments(['10.0.0.0/20','10.0.16.0/20'])
        with patch.object(app,'ps_json',return_value=[{'IPAddress':'10.0.0.9','PrefixLength':16}]):
            with self.assertRaises(ValueError):app.local_segments()

    def test_package_scripts_require_machine_scope_without_fallback(self):
        for body in (software_catalog.INSTALL_PS,software_catalog.UNINSTALL_PS):
            self.assertIn('--scope machine',body)
            self.assertIn('--silent',body)
            self.assertIn('--disable-interactivity',body)
            self.assertNotIn('--scope user',body)
            self.assertNotIn('ExecutionPolicy',body)
            self.assertNotIn('Start-Process',body)


class JobTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'.test-temp'
        base.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base)
        self.previous=app.DB
        app.DB=Path(self.temp.name)/'test.db'
        app.initialize()
        self.managers=[]

    def tearDown(self):
        for manager in self.managers: manager.pool.shutdown(wait=True)
        app.DB=self.previous
        self.temp.cleanup()

    def manager(self,execute):
        result=software_jobs.Manager(app.db,app.audit,app.now,execute)
        self.managers.append(result)
        return result

    def test_old_databases_default_to_unknown_and_printers_are_blocked(self):
        app.save_machine('PC-TEST')
        with self.assertRaises(ValueError):app.require_computer('PC-TEST')
        with app.db() as c:c.execute("UPDATE machines SET device_type='printer' WHERE target='PC-TEST'")
        with self.assertRaises(ValueError):app.require_computer('PC-TEST')
        with app.db() as c:c.execute("UPDATE machines SET device_type='computer' WHERE target='PC-TEST'")
        app.require_computer('PC-TEST')

    def test_manual_classification_survives_new_probe(self):
        app.save_machine('PRN-TEST')
        with app.db() as c:c.execute("UPDATE machines SET device_type='printer',type_source='manual' WHERE target='PRN-TEST'")
        app.record_device('PRN-TEST',{'alive':True,'device_type':'computer','evidence':'port'})
        self.assertEqual(app.rows('SELECT device_type FROM machines')[0]['device_type'],'printer')

    def test_neighbor_scan_deduplicates_ip_even_if_mac_changes(self):
        neighbors=[('192.168.1.2','00-00-00-00-00-01'),
                   ('192.168.1.2','00-00-00-00-00-02')]
        response={'alive':True,'device_type':'computer','evidence':'WinRM simulated'}
        with patch.object(app,'discover_neighbors',return_value=neighbors), \
             patch.object(device_discovery,'probe',return_value=response) as probe:
            result=app.scan_neighbors()
        self.assertEqual(result['found'],1)
        self.assertEqual(result['online'],1)
        probe.assert_called_once()
        machine=app.rows('SELECT target,mac FROM machines WHERE target=?',('192.168.1.2',))[0]
        self.assertEqual(machine['mac'],'00-00-00-00-00-02')

    def test_filtered_neighbor_is_not_lost_after_scan(self):
        with patch.object(app,'scan_targets',return_value={'found':0,'online':0,'scanned':2,'unresponsive':2,'errors':[]}),patch.object(app,'discover_neighbors',return_value=[('192.168.1.2','aa-bb-cc-dd-ee-ff'),('192.168.2.2','other')]):
            result=app.scan_segments(['192.168.1.0/30'])
        self.assertEqual(result['neighbors_added'],1)
        self.assertEqual(result['tested'],2)
        self.assertEqual(app.rows('SELECT target FROM machines'),[{'target':'192.168.1.2'}])

    def test_async_job_deduplicates_and_records_actual_failure(self):
        entered,release=threading.Event(),threading.Event()
        def execute(target,operation,ids):
            entered.set();release.wait(3)
            return {'Escopo':'machine','Instalacoes':[{'Pacote':ids[0],'CodigoSaida':1,'Escopo':'machine'}]}
        manager=self.manager(execute)
        first=manager.submit('PC-TEST','install',['firefox'],['Mozilla.Firefox'])
        self.assertTrue(entered.wait(2))
        duplicate=manager.submit('PC-TEST','install',['firefox'],['Mozilla.Firefox'])
        self.assertEqual(first['job_id'],duplicate['job_id']);self.assertTrue(duplicate['duplicate'])
        release.set();manager.pool.shutdown(wait=True)
        self.assertEqual(manager.list()[0]['state'],'failed')
        self.assertEqual(manager.list()[0]['result']['Instalacoes'][0]['CodigoSaida'],1)

    def test_success_and_interrupted_recovery(self):
        manager=self.manager(lambda *args:{'Escopo':'machine','Desinstalacoes':[{'Pacote':'7zip.7zip','CodigoSaida':0,'Escopo':'machine'}]})
        manager.submit('PC-TEST','uninstall',['7zip'],['7zip.7zip'])
        manager.pool.shutdown(wait=True)
        self.assertEqual(manager.list()[0]['state'],'succeeded')
        with app.db() as c:c.execute("UPDATE software_jobs SET state='running'")
        manager.recover()
        self.assertEqual(manager.list()[0]['state'],'interrupted')

    def test_software_click_queues_without_confirm_or_remote_execution(self):
        handler=object.__new__(app.Handler);handler.send=MagicMock()
        with patch.object(app,'require_computer'),patch.object(app,'WIN',True),patch.object(app.SOFTWARE_MANAGER,'submit',return_value={'job_id':'j1'}) as submit,patch.object(app,'remote_script') as remote:
            handler.handle_post('/api/software/install',{'target':'PC-TEST','packages':['firefox']})
            submit.assert_called_once_with('PC-TEST','install',['firefox'],['Mozilla.Firefox'])
            remote.assert_not_called()
            self.assertEqual(handler.send.call_args.args[0],202)


if __name__=='__main__':unittest.main()
