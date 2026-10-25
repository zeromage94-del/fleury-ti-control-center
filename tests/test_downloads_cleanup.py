"""Downloads manifests plus optional native execution in a disposable sandbox.

No corporate hosts, real user profiles or service administration are involved.
The native cases replace Get-CimInstance with a list of temporary profiles.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import maintenance


def entry(path=r'C:\Users\Ana\Downloads\old.pdf'):
    return {'path': path, 'root': r'C:\Users\Ana\Downloads',
            'profile': r'C:\Users\Ana', 'size': 123,
            'mtime_ticks': '638000000000000000',
            'creation_ticks': '637000000000000000'}


class DownloadsManifests(unittest.TestCase):
    def test_manifest_has_opaque_distinct_ids_and_relative_display_names(self):
        result = maintenance.normalize_downloads_preview({'Arquivos': [entry(),
            entry(r'C:\Users\Ana\Downloads\sub\old.zip')], 'Falhas': 0})
        files = result['Arquivos']
        self.assertEqual(files[0]['relative_name'], 'old.pdf')
        self.assertEqual(files[1]['relative_name'], r'sub\old.zip')
        self.assertEqual(files[0]['profile_name'], 'Ana')
        self.assertNotEqual(files[0]['id'], files[1]['id'])
        self.assertNotIn('Ana', files[0]['id'])
        selected = maintenance.select_downloads_files(result, [files[1]['id']])
        self.assertEqual(selected, [entry(r'C:\Users\Ana\Downloads\sub\old.zip')])
        self.assertNotIn('id', selected[0])

    def test_case_insensitive_windows_roots_and_custom_local_profiles(self):
        value = entry(r'd:\Profiles\Luiz\Downloads\old.exe')
        value.update(root=r'D:\Profiles\Luiz\Downloads', profile=r'D:\Profiles\Luiz')
        result = maintenance.normalize_downloads_preview({'Arquivos': [value]})
        self.assertEqual(result['Arquivos'][0]['relative_name'], 'old.exe')

    def test_invalid_and_duplicate_selection_never_yields_paths(self):
        preview = maintenance.normalize_downloads_preview({'Arquivos': [entry()]})
        ident = preview['Arquivos'][0]['id']
        for ids in (None, '', [], [None], [ident, ident], ['unknown'], [ident]*201,
                    [{'path': entry()['path']}], [entry()['path']]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                maintenance.select_downloads_files(preview, ids)

    def test_path_escape_devices_unc_ads_and_controls_are_rejected(self):
        bad_paths = [r'C:\Users\Ana\Documents\private.pdf',
            r'C:\Users\Ana\Downloads\..\private.pdf',
            r'C:\Users\Ana\Downloads-other\private.pdf',
            r'\\host\share\old.pdf', r'\\?\C:\Users\Ana\Downloads\old.pdf',
            r'C:\Users\Ana\Downloads\old.pdf:stream',
            'C:/Users/Ana/Downloads/old.pdf',
            'C:\\Users\\Ana\\Downloads\\bad\x00file', r'C:\Users\Ana\Downloads',
            r'D:\Users\Ana\Downloads\old.pdf']
        for path in bad_paths:
            with self.subTest(path=path), self.assertRaises(ValueError):
                maintenance.normalize_downloads_preview({'Arquivos': [entry(path)]})

    def test_unrelated_root_or_drive_root_profile_rejected(self):
        for changes in ({'root': r'C:\Users\Ana\Documents'},
                        {'profile': 'C:\\', 'root': r'C:\Downloads', 'path': r'C:\Downloads\x'},
                        {'profile': r'C:\Users\Other'}):
            value = entry()
            value.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                maintenance.normalize_downloads_preview({'Arquivos': [value]})

    def test_duplicate_paths_ignore_windows_case(self):
        with self.assertRaises(ValueError):
            maintenance.normalize_downloads_preview({'Arquivos': [entry(), entry(entry()['path'].upper())]})

    def test_malformed_identity_and_counts_fail_closed(self):
        for changes in ({'size': True}, {'size': -1}, {'size': 1.2},
                        {'size': 2**63}, {'mtime_ticks': 123},
                        {'mtime_ticks': ''}, {'mtime_ticks': '0'},
                        {'creation_ticks': '12;Remove-Item'}, {'creation_ticks': None}):
            value = entry()
            value.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                maintenance.normalize_downloads_preview({'Arquivos': [value]})
        for value in (None, [], {}, {'Arquivos': {}}, {'Arquivos': [None]},
                      {'Arquivos': [entry()]*201}):
            with self.subTest(value=type(value)), self.assertRaises(ValueError):
                maintenance.normalize_downloads_preview(value)

    def test_preview_metadata_is_not_mutated_and_ids_rotate(self):
        result = {'Arquivos': [entry()], 'Falhas': 0}
        before = deepcopy(result)
        first = maintenance.normalize_downloads_preview(result)
        second = maintenance.normalize_downloads_preview(result)
        self.assertEqual(result, before)
        self.assertNotEqual(first['Arquivos'][0]['id'], second['Arquivos'][0]['id'])
        with self.assertRaises(ValueError):
            maintenance.select_downloads_files(second, [first['Arquivos'][0]['id']])

    def test_empty_preview_is_valid_and_days_require_integer(self):
        self.assertEqual(maintenance.normalize_downloads_preview({'Arquivos': []})['Arquivos'], [])
        for value in (True, False, 7.1, 30.9, '7.2', 6, 366):
            with self.subTest(value=value), self.assertRaises(ValueError):
                maintenance.validate_days(value)
        for value in (7, '30', 365):
            self.assertEqual(maintenance.validate_days(value), int(value))


@unittest.skipUnless(os.name == 'nt', 'Native Downloads filesystem execution requires Windows')
class DownloadsNativeSandbox(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.profiles = [{'LocalPath': str(self.base/'Ana'), 'Special': False},
                         {'LocalPath': str(self.base/'Beto'), 'Special': False},
                         {'LocalPath': str(self.base/'System'), 'Special': True}]
        for profile in self.profiles:
            (Path(profile['LocalPath'])/'Downloads').mkdir(parents=True)
        self.profiles_path = self.base/'profiles.json'
        self.profiles_path.write_text(json.dumps(self.profiles), encoding='utf-8')
        self.script = self.base/'test-downloads.ps1'
        self.script.write_text('''param($ConfigPath,$ProfilesPath)
$script:SandboxProfiles=Get-Content -LiteralPath $ProfilesPath -Raw | ConvertFrom-Json
function Get-CimInstance {
 [CmdletBinding()]param([string]$ClassName)
 if($ClassName -ne 'Win32_UserProfile'){throw 'Unexpected CIM request'}
 $script:SandboxProfiles
}
& {
''' + maintenance.DOWNLOADS_PS + '''
} ([IO.File]::ReadAllText($ConfigPath)) | ConvertTo-Json -Depth 10
''', encoding='utf-8-sig')

    def file(self, relative, age=40, content=b'old-file'):
        path = self.base/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        stamp = time.time()-age*86400
        os.utime(path, (stamp, stamp))
        return path

    def run_script(self, config):
        config_path = self.base/'config.json'
        config_path.write_text(json.dumps(config), encoding='utf-8')
        quote = lambda path: "'" + str(path).replace("'", "''") + "'"
        command = '& {\n' + self.script.read_text('utf-8-sig') + '\n} ' + quote(config_path) + ' ' + quote(self.profiles_path)
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        return json.loads(result.stdout)

    def test_real_temp_files_across_profiles_preview_and_selected_removal(self):
        old = self.file('Ana/Downloads/report.pdf')
        other = self.file('Beto/Downloads/setup.exe')
        recent = self.file('Ana/Downloads/recent.pdf', age=1)
        special = self.file('System/Downloads/keep.zip')
        incomplete = self.file('Ana/Downloads/incomplete.crdownload')
        outside = self.file('Ana/Documents/keep.pdf')
        preview = maintenance.normalize_downloads_preview(self.run_script({'days': 30, 'commit': False}))
        self.assertEqual(preview['ArquivosElegiveis'], 2)
        self.assertTrue(old.exists())
        ident = next(x['id'] for x in preview['Arquivos'] if x['profile_name'] == 'Ana')
        result = self.run_script({'days': 30, 'commit': True,
            'files': maintenance.select_downloads_files(preview, [ident])})
        self.assertEqual(result['ArquivosRemovidos'], 1)
        self.assertEqual(result['Falhas'], 0)
        self.assertFalse(old.exists())
        self.assertTrue(all(x.exists() for x in (other, recent, special, incomplete, outside)))

    def test_changed_file_is_preserved_and_reported_as_failure(self):
        old = self.file('Ana/Downloads/changed.zip')
        preview = maintenance.normalize_downloads_preview(self.run_script({'days': 30, 'commit': False}))
        old.write_bytes(b'changed-after-preview')
        files = maintenance.select_downloads_files(preview, [preview['Arquivos'][0]['id']])
        result = self.run_script({'days': 30, 'commit': True, 'files': files})
        self.assertEqual(result['ArquivosRemovidos'], 0)
        self.assertEqual(result['Falhas'], 1)
        self.assertTrue(old.exists())

    def test_locked_file_is_preserved(self):
        old = self.file('Ana/Downloads/locked.zip')
        preview = maintenance.normalize_downloads_preview(self.run_script({'days': 30, 'commit': False}))
        files = maintenance.select_downloads_files(preview, [preview['Arquivos'][0]['id']])
        # Read-only flag makes the Windows ReadWrite/open or deletion fail closed.
        old.chmod(0o444)
        try:
            result = self.run_script({'days': 30, 'commit': True, 'files': files})
            self.assertEqual(result['ArquivosRemovidos'], 0)
            self.assertEqual(result['Falhas'], 1)
            self.assertTrue(old.exists())
        finally:
            old.chmod(0o666)


if __name__ == '__main__':
    unittest.main()
