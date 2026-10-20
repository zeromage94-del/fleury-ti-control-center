import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import integrations
import admin_scripts
import app


class IntegrationTests(unittest.TestCase):
    def test_service_url_policy(self):
        for value in ('https://printer.example', 'https://printer.example:8443', 'http://127.0.0.1:8000'):
            with patch.dict(os.environ, {'FLEURY_ZPL_REST_URL':value}):
                self.assertEqual(integrations.base_url('FLEURY_ZPL_REST_URL'), value)
        for value in ('http://10.0.0.5:8000','https://user:pass@printer.example','https://printer.example/rest','https://printer.example?secret=1','https://printer.example:bad'):
            with patch.dict(os.environ, {'FLEURY_ZPL_REST_URL':value}), self.assertRaises(ValueError):
                integrations.base_url('FLEURY_ZPL_REST_URL')

    def test_zebra_list_preserves_ids(self):
        with patch.object(integrations, 'api', return_value=[{'_id':'p1','name':'Zebra'}]):
            self.assertEqual(integrations.zpl_list('printer')[0]['id'],'p1')

    def test_print_requires_confirmation_before_network(self):
        with patch.object(integrations,'api') as api, self.assertRaises(ValueError):
            integrations.zpl_print({'printer':'p1','label':'l1'})
        api.assert_not_called()

    def test_print_validates_ids_and_rejects_zpl_injection(self):
        def listing(kind): return [{'id':'p1' if kind=='printer' else 'l1'}]
        with patch.object(integrations,'zpl_list',side_effect=listing), patch.object(integrations,'api') as api:
            for data in ({'text':'^XZ^JUS'}, {'text':'hello\nworld'}, [], {'x': {'nested':'bad'}}):
                with self.assertRaises(ValueError):
                    integrations.zpl_print({'confirm':True,'printer':'p1','label':'l1','data':data})
            with self.assertRaises(ValueError):
                integrations.zpl_print({'confirm':True,'printer':'other','label':'l1'})
            api.assert_not_called()
            api.return_value={'success':True}
            integrations.zpl_print({'confirm':True,'printer':'p1','label':'l1','data':{'text':'TESTE'}})
            self.assertEqual(api.call_args.args[1:3],('/rest/print','POST'))
            self.assertEqual(api.call_args.args[3]['data'],{'text':'TESTE'})

    def test_redirect_blocked(self):
        with self.assertRaises(RuntimeError):
            integrations.NoRedirect().redirect_request(None,None,302,'',{},'https://other.example')

    def test_winutil_hash_mismatch_does_not_launch(self):
        with patch.object(integrations.Path,'is_file',return_value=True), patch.object(integrations.Path,'read_bytes',return_value=b'changed'), patch.dict(os.environ,{'FLEURY_WINUTIL_PATH':'C:/TI/winutil.ps1','FLEURY_WINUTIL_SHA256':'0'*64}), patch.object(integrations.subprocess,'Popen') as launch:
            with self.assertRaises(ValueError): integrations.launch_winutil()
            launch.assert_not_called()

    def test_scripts_are_fixed_and_unknown_key_blocked(self):
        with self.assertRaises(ValueError): admin_scripts.body('accounts; Remove-Item')
        for item in admin_scripts.catalog():
            script=admin_scripts.body(item['key'])
            for forbidden in ('Remove-','Set-MpPreference','Set-NetFirewall','Invoke-Expression'):
                self.assertNotIn(forbidden,script)

    def test_http_errors_do_not_leak_token(self):
        from urllib.error import URLError
        opener=MagicMock();opener.open.side_effect=URLError('private-details')
        with patch.dict(os.environ,{'FLEURY_ZAMMAD_URL':'https://help.example','FLEURY_ZAMMAD_TOKEN':'secret-token'}), patch.object(integrations,'build_opener',return_value=opener):
            with self.assertRaises(RuntimeError) as err:
                integrations.api('FLEURY_ZAMMAD_URL','/api/v1/tickets',token_variable='FLEURY_ZAMMAD_TOKEN')
            self.assertNotIn('private-details',str(err.exception))
            self.assertNotIn('secret-token',str(err.exception))

    def test_routes_audit_success_and_failure_without_label_contents(self):
        handler=object.__new__(app.Handler)
        handler.send=MagicMock()
        body={'confirm':True,'printer':'p1','label':'l1','data':{'text':'PRIVATE'}}
        with patch.object(app.integrations,'zpl_print',return_value={'message':'sent'}), patch.object(app,'audit') as audit:
            handler.handle_post('/api/zebra/print',body)
            self.assertTrue(audit.call_args.args[2])
            self.assertNotIn('PRIVATE',str(audit.call_args))
        with patch.object(app.integrations,'zpl_print',side_effect=RuntimeError('failed')), patch.object(app,'audit') as audit:
            with self.assertRaises(RuntimeError):handler.handle_post('/api/zebra/print',body)
            self.assertFalse(audit.call_args.args[2])


if __name__=='__main__':unittest.main()
