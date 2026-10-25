"""Executa scripts PowerShell reais com cmdlets de impressão substituídos.

Somente no runner Windows descartável; não acessa impressoras, rede ou Spooler real.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import printer_support as printers


PREFIX = r'''
$script:lab=Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json
function Get-Printer {
 [CmdletBinding()]param($Name)
 $p=@($script:lab.printers | Where-Object {$_.Name -eq $Name})
 if($p.Count -ne 1){throw 'SIM printer not found'}
 $p[0]
}
function Get-PrintJob {
 [CmdletBinding()]param($PrinterName)
 $p=Get-Printer -Name $PrinterName
 @($p.jobs | ForEach-Object {[PSCustomObject]@{ID=$_;JobStatus='Error'}})
}
function Remove-PrintJob {
 [CmdletBinding(SupportsShouldProcess=$true)]param($PrinterName,$ID)
 if(-not $PSBoundParameters.ContainsKey('Confirm') -or [bool]$PSBoundParameters['Confirm']){throw 'SIM: confirmation suppression missing'}
 $p=Get-Printer -Name $PrinterName
 if($script:lab.blocked -eq $ID){throw 'SIM locked job'}
 $p.jobs=@($p.jobs | Where-Object {$_ -ne $ID})
}
function Get-Service {
 [CmdletBinding()]param($Name)
 if($Name -ne 'Spooler'){throw 'Unexpected service'}
 [PSCustomObject]@{Status=$script:lab.spooler}
}
function Get-PrinterPort {
 [CmdletBinding()]param($Name)
 [PSCustomObject]@{PrinterHostAddress='';PortNumber=0}
}
function Get-CimInstance {
 [CmdletBinding()]param($ClassName)
 if($ClassName -ne 'Win32_Printer'){throw 'Unexpected CIM request'}
 @($script:lab.printers | ForEach-Object {
  [PSCustomObject]@{Name=$_.Name;WorkOffline=$false;DetectedErrorState=$_.error}
 })
}
function Get-PrinterDriver {
 [CmdletBinding()]param($Name)
 if($Name -notin $script:lab.drivers){throw 'SIM driver not installed'}
 [PSCustomObject]@{Name=$Name}
}
function Set-Printer {
 [CmdletBinding(SupportsShouldProcess=$true)]param($Name,$DriverName)
 if(-not $PSBoundParameters.ContainsKey('Confirm') -or [bool]$PSBoundParameters['Confirm']){throw 'SIM: confirmation suppression missing'}
 $p=Get-Printer -Name $Name
 if(-not $script:lab.reject_change){$p.DriverName=$DriverName}
}
'''


@unittest.skipUnless(os.name == 'nt', 'Native printer simulation requires Windows PowerShell')
class NativePrinterSimulation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = dict(spooler='Running', blocked=-1, reject_change=False,
                          drivers=['ZDesigner ZD421-203dpi ZPL'], printers=[
            dict(Name='Laser', DriverName='Universal PCL6', PortName='USB001', PrinterStatus='Error', error=8, jobs=[1, 2]),
            dict(Name='Zebra ZD421', DriverName='ZDesigner antigo', PortName='USB002', PrinterStatus='Error', error=4, jobs=[7, 8])])

    def execute(self, script, config, fail=False):
        state = self.root / 'state.json'
        args = self.root / 'args.json'
        state.write_text(json.dumps(self.state), encoding='utf-8')
        args.write_text(json.dumps(config), encoding='utf-8')
        quote = lambda p: "'" + str(p).replace("'", "''") + "'"
        command = ('$StatePath=' + quote(state) + ';$ConfigPath=' + quote(args) + ';' + PREFIX
                   + '\n& {\n' + script + '\n} ([IO.File]::ReadAllText($ConfigPath)) | ConvertTo-Json -Depth 10')
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                                capture_output=True, text=True, timeout=30)
        if fail:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_actual_queue_script_only_removes_selected_jobs_and_reports_locked_job(self):
        self.state['blocked'] = 8
        result = self.execute(printers.CLEAR_QUEUE_PS, {'printer': 'Zebra ZD421'})
        self.assertEqual((result['Encontrados'], result['Removidos'], result['Restantes'], result['Falhas']), (2, 1, 1, 1))
        self.assertEqual(result['Impressora'], 'Zebra ZD421')
        self.state['blocked'] = -1
        result = self.execute(printers.CLEAR_QUEUE_PS, {'printer': 'Laser'})
        self.assertEqual((result['Removidos'], result['Restantes']), (2, 0))

    def test_actual_diagnostics_observe_paper_jam_and_missing_zebra_media(self):
        for name, code in (('Laser', 'paper_jam'), ('Zebra ZD421', 'paper_out')):
            with self.subTest(name=name):
                result = printers.assess_diagnostics(self.execute(printers.DIAGNOSTICS_PS, {'printer': name}))
                self.assertIn(code, [issue['code'] for issue in result['issues']])
                self.assertFalse(result['healthy'])

    def test_actual_driver_script_enforces_queue_model_and_installed_driver(self):
        config = dict(printer='Zebra ZD421', driver_name='ZDesigner ZD421-203dpi ZPL', models=['ZD421'])
        self.execute(printers.SWITCH_DRIVER_PS, config, fail=True)
        self.state['printers'][1]['jobs'] = []
        self.execute(printers.SWITCH_DRIVER_PS, {**config, 'models': ['ZT411']}, fail=True)
        self.execute(printers.SWITCH_DRIVER_PS, {**config, 'driver_name': 'ZDesigner missing'}, fail=True)
        result = self.execute(printers.SWITCH_DRIVER_PS, config)
        self.assertEqual(result['DriverAtual'], config['driver_name'])
        self.assertEqual(result['DriverAnterior'], 'ZDesigner antigo')


if __name__ == '__main__':
    unittest.main()
