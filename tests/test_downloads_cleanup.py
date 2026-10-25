"""Executa limpeza integral em perfis temporários Windows, sem dados reais."""
import ctypes
from ctypes import wintypes
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


class TempAgeValidation(unittest.TestCase):
    def test_temp_days_still_require_integer_in_range(self):
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

    def file(self, relative, age=0, content=b'disposable data'):
        path = self.base/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        stamp = time.time()-age*86400
        os.utime(path, (stamp, stamp))
        return path

    def run_script(self):
        quote = lambda path: "'" + str(path).replace("'", "''") + "'"
        prefix = "$script:SandboxProfiles=Get-Content -LiteralPath " + quote(self.profiles_path) + r''' -Raw -Encoding UTF8 | ConvertFrom-Json
function Get-CimInstance {
 [CmdletBinding()]param([string]$ClassName)
 if($ClassName -ne 'Win32_UserProfile'){throw 'Unexpected CIM request'}
 $script:SandboxProfiles
}
'''
        command = prefix + '\n& {\n' + maintenance.DOWNLOADS_PS + "\n} '{}' | ConvertTo-Json -Depth 10"
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        return json.loads(result.stdout)

    def test_one_call_deletes_all_formats_ages_attributes_and_profiles(self):
        files = [self.file('Ana/Downloads/old.pdf', age=40),
                 self.file('Beto/Downloads/new.exe'),
                 self.file('Ana/Downloads/sub/recent.jpg'),
                 self.file('Ana/Downloads/incomplete.crdownload'),
                 self.file("Ana/Downloads/[1]O'Brien.txt"),
                 self.file('Beto/Downloads/readonly.doc'),
                 self.file('Ana/Downloads/hidden.bin')]
        files[-2].chmod(0o444)
        set_attributes = ctypes.windll.kernel32.SetFileAttributesW
        set_attributes.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
        set_attributes.restype = wintypes.BOOL
        self.assertTrue(set_attributes(str(files[-1]), 0x2 | 0x4))
        outside = self.file('Ana/Documents/keep.pdf')
        special = self.file('System/Downloads/keep.zip')
        self.profiles.append(self.profiles[0])
        self.profiles_path.write_text(json.dumps(self.profiles), encoding='utf-8')
        result = self.run_script()
        self.assertEqual(result['ArquivosEncontrados'], len(files))
        self.assertEqual(result['ArquivosRemovidos'], len(files))
        self.assertEqual(result['Falhas'], 0)
        self.assertEqual(result['PastasDownloads'], 2)
        self.assertEqual(result['BytesLiberados'], len(files)*len(b'disposable data'))
        self.assertTrue(all(not path.exists() for path in files))
        self.assertTrue(outside.exists() and special.exists())
        self.assertTrue((self.base/'Ana/Downloads').is_dir())
        self.assertTrue((self.base/'Beto/Downloads').is_dir())
        self.assertFalse((self.base/'Ana/Downloads/sub').exists())

    def test_more_than_200_files_and_deep_folders_are_cleared(self):
        files = [self.file('Ana/Downloads/file-'+str(i)+'.bin') for i in range(260)]
        files.append(self.file('Beto/Downloads/'+'deep/'*10+'file'))
        result = self.run_script()
        self.assertEqual(result['ArquivosRemovidos'], 261)
        self.assertEqual(result['Falhas'], 0)
        self.assertTrue(all(not path.exists() for path in files))
        repeated = self.run_script()
        self.assertEqual(repeated['ArquivosEncontrados'], 0)
        self.assertEqual(repeated['ArquivosRemovidos'], 0)

    def test_locked_file_is_reported_and_other_users_are_still_cleaned(self):
        locked = self.file('Ana/Downloads/locked.zip')
        other = self.file('Beto/Downloads/clear.pdf')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(locked), 0x80000000, 0, None, 3, 0x80, None)
        self.assertNotIn(handle, (None, ctypes.c_void_p(-1).value))
        try:
            result = self.run_script()
        finally:
            kernel.CloseHandle(handle)
        self.assertEqual(result['ArquivosRemovidos'], 1)
        self.assertEqual(result['Falhas'], 1)
        self.assertTrue(locked.exists())
        self.assertFalse(other.exists())

    def test_junctions_inside_downloads_and_at_root_do_not_escape(self):
        outside = self.file('Ana/Documents/keep.pdf')
        ordinary = self.file('Ana/Downloads/delete.pdf')
        (self.base/'Beto/Downloads').rmdir()
        for link in (self.base/'Ana/Downloads/linked', self.base/'Beto/Downloads'):
            result = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(outside.parent)],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        result = self.run_script()
        self.assertEqual(result['ArquivosRemovidos'], 1)
        self.assertGreaterEqual(result['Ignorados'], 2)
        self.assertEqual(result['PastasIgnoradas'], 1)
        self.assertTrue(outside.exists())
        self.assertFalse(ordinary.exists())

    def test_profiles_without_downloads_folder_are_not_failures(self):
        (self.base/'Ana/Downloads').rmdir()
        (self.base/'Beto/Downloads').rmdir()
        result = self.run_script()
        self.assertEqual(result['PastasDownloads'], 0)
        self.assertEqual(result['Falhas'], 0)
        self.assertEqual(result['ArquivosRemovidos'], 0)


if __name__ == '__main__':
    unittest.main()
