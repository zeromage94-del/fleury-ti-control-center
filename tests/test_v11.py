"""Testes estáticos não destrutivos da versão 1.1."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import software_catalog
import maintenance

ROOT=Path(__file__).resolve().parents[1]
class V11Tests(unittest.TestCase):
    def test_catalog_has_apps_and_no_games(self):
        items=software_catalog.catalog()
        self.assertGreaterEqual(len(items),35)
        self.assertFalse(any('game' in x['category'].lower() or 'jogo' in x['category'].lower() for x in items))
        self.assertEqual(len({x['key'] for x in items}),len(items))
        self.assertEqual(len({x['winget_id'] for x in items}),len(items))
        self.assertEqual(software_catalog.validate_packages(['7zip','firefox']),['7zip.7zip','Mozilla.Firefox'])
    def test_bad_catalog_values_blocked(self):
        for vals in [[],['script-internet'],['7zip']*2,['7zip']*6,['7zip;shutdown']]:
            with self.assertRaises(ValueError):software_catalog.validate_packages(vals)
    def test_global_picker_and_scripts_are_not_placeholders(self):
        h=(ROOT/'static/index.html').read_text(encoding='utf8')
        js=(ROOT/'static/upgrade.js').read_text(encoding='utf8')
        self.assertIn('id="global-machine-picker"',h)
        self.assertIn('data-act="cleanup-run"',js)
        self.assertIn('data-act="quick-optimize"',js)
        self.assertIn('data-act="restore-create"',js)
        self.assertIn('data-act="restore-list"',js)
        self.assertIn('data-act="software-page"',js)
        self.assertIn('winutil-copy',js)
        self.assertIn('Criado por Ana Tazinaffo',js)
    def test_temp_script_does_not_remove_other_files(self):
        s=maintenance.CLEANUP_PS
        self.assertIn("'.tmp','.temp'",s)
        self.assertIn('Get-CimInstance Win32_UserProfile',s)
        for bad in ('Remove-Item -Recurse','*.jpg','*.pdf','Uninstall-', 'Set-MpPreference'):
            self.assertNotIn(bad,s)
if __name__=='__main__':unittest.main()
