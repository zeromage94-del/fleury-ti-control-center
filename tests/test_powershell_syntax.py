"""Parse native scripts on Windows without invoking administrative commands."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import maintenance
import software_catalog
import admin_scripts
import video_insights

@unittest.skipUnless(os.name == 'nt', 'Native PowerShell parser requires Windows runner')
class PowerShellSyntax(unittest.TestCase):
    def test_all_predefined_scripts_parse_without_execution(self):
        scripts={}
        for module in (maintenance,software_catalog):
            scripts.update({module.__name__+'.'+k:v for k,v in vars(module).items()
                            if k.endswith('_PS') and isinstance(v,str)})
        scripts.update({'admin.'+x['key']:admin_scripts.body(x['key']) for x in admin_scripts.catalog()})
        scripts.update({'console.'+k:v for k,v in video_insights.SAFE_QUERIES.items()})
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'scripts.json'
            source.write_text(json.dumps(scripts),encoding='utf-8')
            parser=Path(folder)/'parse.ps1'
            parser.write_text('''param($InputPath)
$scripts=Get-Content -LiteralPath $InputPath -Raw -Encoding UTF8 | ConvertFrom-Json
$failed=$false
foreach($property in $scripts.PSObject.Properties){
 $tokens=$null; $parseErrors=$null
 $null=[System.Management.Automation.Language.Parser]::ParseInput($property.Value,[ref]$tokens,[ref]$parseErrors)
 if($parseErrors.Count){$failed=$true; Write-Output $property.Name; $parseErrors | ForEach-Object {Write-Output $_.Message}}
}
if($failed){exit 1}
Write-Output ('Parsed '+$scripts.PSObject.Properties.Name.Count+' scripts without executing them.')
''',encoding='utf-8')
            result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(parser),str(source)],capture_output=True,text=True,timeout=40)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__': unittest.main()
