"""Consultas de suporte inspiradas nas categorias do artigo Vicarius.
Implementação própria; não importa nem executa código de páginas externas.
"""
SCRIPTS = {
    'accounts': ('Contas locais', r"Get-LocalUser | Select-Object Name,Enabled,LastLogon,PasswordRequired"),
    'security': ('Proteções do Windows', r"Get-MpComputerStatus -ErrorAction Stop | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated"),
    'firewall': ('Perfis de firewall', r"Get-NetFirewallProfile -ErrorAction Stop | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction"),
    'events': ('Erros recentes do sistema', r"Get-WinEvent -FilterHashtable @{LogName='System';Level=2;StartTime=(Get-Date).AddDays(-2)} -MaxEvents 30 -ErrorAction Stop | Select-Object TimeCreated,ProviderName,Id,Message"),
    'backup': ('Histórico Windows Backup', r"Get-WinEvent -LogName 'Microsoft-Windows-Backup' -MaxEvents 15 -ErrorAction Stop | Select-Object TimeCreated,Id,LevelDisplayName,Message"),
    'reboot': ('Estado de reinicialização', r"$os=Get-CimInstance Win32_OperatingSystem; [PSCustomObject]@{UltimoBoot=$os.LastBootUpTime;ReinicioPendente=(Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending')}"),
}


def catalog():
    return [{'key': key, 'name': value[0], 'read_only': True} for key, value in SCRIPTS.items()]


def body(key):
    if not isinstance(key, str) or key not in SCRIPTS:
        raise ValueError('Script não permitido.')
    return "$ErrorActionPreference='Stop'; " + SCRIPTS[key][1]
