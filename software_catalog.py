"""Catálogo fechado Winget: nenhuma URL, comando ou script é aceito do cliente.
As permissões efetivas e bloqueios corporativos do Windows são respeitados.
"""
import re

CATALOG = (
    ('7zip', '7-Zip', '7zip.7zip', 'Arquivos e PDF', 'Arquivos compactados'),
    ('notepadpp', 'Notepad++', 'Notepad++.Notepad++', 'Produtividade', 'Editor de texto'),
    ('firefox', 'Mozilla Firefox', 'Mozilla.Firefox', 'Navegadores', 'Navegador'),
    ('chrome', 'Google Chrome', 'Google.Chrome', 'Navegadores', 'Navegador'),
    ('vscode', 'Visual Studio Code', 'Microsoft.VisualStudioCode', 'TI e desenvolvimento', 'Editor de código'),
    ('git', 'Git for Windows', 'Git.Git', 'TI e desenvolvimento', 'Controle de versão'),
    ('powertoys', 'Microsoft PowerToys', 'Microsoft.PowerToys', 'Utilitários', 'Ferramentas Microsoft'),
    ('sumatra', 'Sumatra PDF', 'SumatraPDF.SumatraPDF', 'Arquivos e PDF', 'Leitor de PDF'),
    ('vlc', 'VLC Media Player', 'VideoLAN.VLC', 'Produtividade', 'Reprodutor de mídia'),
    ('terminal', 'Windows Terminal', 'Microsoft.WindowsTerminal', 'TI e desenvolvimento', 'Terminal Microsoft'),
    ('libreoffice', 'LibreOffice', 'TheDocumentFoundation.LibreOffice', 'Produtividade', 'Suíte de escritório'),
    ('keepass', 'KeePass', 'DominikReichl.KeePass', 'Utilitários', 'Cofre local de senhas'),
    ('brave', 'Brave', 'Brave.Brave', 'Navegadores', 'Navegador'),
    ('edge', 'Microsoft Edge', 'Microsoft.Edge', 'Navegadores', 'Navegador Microsoft'),
    ('firefoxesr', 'Firefox ESR', 'Mozilla.Firefox.ESR', 'Navegadores', 'Versão de suporte estendido'),
    ('vivaldi', 'Vivaldi', 'Vivaldi.Vivaldi', 'Navegadores', 'Navegador'),
    ('opera', 'Opera', 'Opera.Opera', 'Navegadores', 'Navegador'),
    ('chromium', 'Chromium', 'Hibbiki.Chromium', 'Navegadores', 'Navegador livre'),
    ('teams', 'Microsoft Teams', 'Microsoft.Teams', 'Comunicação', 'Comunicação corporativa'),
    ('zoom', 'Zoom', 'Zoom.Zoom', 'Comunicação', 'Videoconferência'),
    ('discord', 'Discord', 'Discord.Discord', 'Comunicação', 'Mensagens e chamadas'),
    ('slack', 'Slack', 'SlackTechnologies.Slack', 'Comunicação', 'Mensageria corporativa'),
    ('thunderbird', 'Thunderbird', 'Mozilla.Thunderbird', 'Comunicação', 'E-mail desktop'),
    ('telegram', 'Telegram Desktop', 'Telegram.TelegramDesktop', 'Comunicação', 'Mensageria'),
    ('python', 'Python 3', 'Python.Python.3.13', 'Desenvolvimento', 'Ambiente Python'),
    ('node', 'Node.js LTS', 'OpenJS.NodeJS.LTS', 'Desenvolvimento', 'JavaScript'),
    ('githubdesktop', 'GitHub Desktop', 'GitHub.GitHubDesktop', 'Desenvolvimento', 'Cliente Git'),
    ('githubcli', 'GitHub CLI', 'GitHub.cli', 'Desenvolvimento', 'CLI GitHub'),
    ('docker', 'Docker Desktop', 'Docker.DockerDesktop', 'Desenvolvimento', 'Contêineres'),
    ('postman', 'Postman', 'Postman.Postman', 'Desenvolvimento', 'Cliente API'),
    ('powershell', 'PowerShell 7', 'Microsoft.PowerShell', 'Desenvolvimento', 'Shell moderna'),
    ('cmake', 'CMake', 'Kitware.CMake', 'Desenvolvimento', 'Ferramentas de build'),
    ('neovim', 'Neovim', 'Neovim.Neovim', 'Desenvolvimento', 'Editor terminal'),
    ('obsidian', 'Obsidian', 'Obsidian.Obsidian', 'Documentos', 'Notas locais'),
    ('acrobat', 'Adobe Acrobat Reader', 'Adobe.Acrobat.Reader.64-bit', 'Documentos', 'Leitor PDF'),
    ('foxit', 'Foxit PDF Reader', 'Foxit.FoxitReader', 'Documentos', 'Leitor PDF'),
    ('pdf24', 'PDF24 Creator', 'geeksoftwareGmbH.PDF24Creator', 'Documentos', 'Ferramentas PDF'),
    ('joplin', 'Joplin', 'Joplin.Joplin', 'Documentos', 'Notas'),
    ('everything', 'Everything Search', 'voidtools.Everything', 'Ferramentas Microsoft e TI', 'Localizar arquivos'),
    ('process-explorer', 'Process Explorer', 'Microsoft.Sysinternals.ProcessExplorer', 'Ferramentas Microsoft e TI', 'Análise de processos'),
    ('autoruns', 'Autoruns', 'Microsoft.Sysinternals.Autoruns', 'Ferramentas Microsoft e TI', 'Itens de inicialização'),
    ('procmon', 'Process Monitor', 'Microsoft.Sysinternals.ProcessMonitor', 'Ferramentas Microsoft e TI', 'Diagnóstico avançado'),
    ('winscp', 'WinSCP', 'WinSCP.WinSCP', 'Ferramentas Microsoft e TI', 'Transferência segura'),
    ('putty', 'PuTTY', 'PuTTY.PuTTY', 'Ferramentas Microsoft e TI', 'Cliente SSH'),
    ('wireshark', 'Wireshark', 'WiresharkFoundation.Wireshark', 'Ferramentas Microsoft e TI', 'Analisador de rede'),
    ('audacity', 'Audacity', 'Audacity.Audacity', 'Multimídia', 'Editor de áudio'),
    ('obs', 'OBS Studio', 'OBSProject.OBSStudio', 'Multimídia', 'Captura e gravação'),

)
_BY_KEY = {x[0]: x for x in CATALOG}


def catalog():
    return [dict(key=key, name=name, winget_id=app_id, category=cat, description=desc)
            for key, name, app_id, cat, desc in CATALOG]


def validate_packages(items):
    if not isinstance(items, list) or not 1 <= len(items) <= 5:
        raise ValueError('Selecione de 1 a 5 programas por vez.')
    if any(not isinstance(x, str) or not re.fullmatch(r'[a-z0-9_-]{1,40}', x) for x in items):
        raise ValueError('Identificador de programa inválido.')
    if len(set(items)) != len(items) or any(k not in _BY_KEY for k in items):
        raise ValueError('Um ou mais programas não pertencem ao catálogo autorizado.')
    return [_BY_KEY[x][2] for x in items]


# Processo não interativo no computador gerenciado; sem janela do PowerShell na sessão do usuário.
# WinGet NÃO funciona em todos os contextos WinRM; falha explícita, nunca usa download/iex alternativo.
INSTALL_PS = r'''param($json)
$ErrorActionPreference='Stop'
$cfg=$json | ConvertFrom-Json
$packages=@($cfg.packages)
if($packages.Count -lt 1 -or $packages.Count -gt 5){ throw 'Quantidade não permitida.' }
$w=Get-Command winget.exe -ErrorAction SilentlyContinue
if(-not $w){ throw 'winget.exe indisponível nesta sessão WinRM. Use o gerenciador corporativo de software ou execute em contexto compatível.' }
$done=@()
foreach($id in $packages){
 if([string]$id -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]{2,100}$'){ throw 'ID de pacote inválido.' }
 $lines=@(& $w.Source install --id ([string]$id) --exact --source winget --silent --disable-interactivity --accept-source-agreements --accept-package-agreements 2>&1 | Out-String)
 $code=$LASTEXITCODE
 $done+= [PSCustomObject]@{ Pacote=[string]$id; CodigoSaida=$code; Resultado=([string]($lines -join '')).Trim().Substring(0,[Math]::Min(450,([string]($lines -join '')).Trim().Length)) }
}
[PSCustomObject]@{ Computador=$env:COMPUTERNAME; Instalacoes=$done; Observacao='Execute somente pacotes permitidos pela política de TI. Código de saída não zero indica falha ou necessidade de intervenção.' }
'''

# Leitura técnica baseada em dados: nunca desabilita SysMain, Search, antivírus ou Update.
DISK_GUIDED_PS = r'''param($json)
$ErrorActionPreference='Stop'
$os=Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
$vol=Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$env:SystemDrive'" -ErrorAction Stop
$drives=@(Get-PhysicalDisk -ErrorAction SilentlyContinue | Select-Object FriendlyName,MediaType,HealthStatus,OperationalStatus)
$measure=@(Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk -ErrorAction SilentlyContinue | Where-Object {$_.Name -ne '_Total'} | Select-Object -First 6 Name,PercentIdleTime,AvgDiskQueueLength,DiskBytesPersec)
$errors=@(Get-WinEvent -FilterHashtable @{LogName='System';Level=2;StartTime=(Get-Date).AddDays(-3)} -MaxEvents 100 -ErrorAction SilentlyContinue | Where-Object {$_.ProviderName -match 'disk|stor|nvme|ntfs|volmgr'} | Select-Object -First 8 TimeCreated,ProviderName,Id,Message)
$recommend=New-Object 'System.Collections.Generic.List[string]'
$free=[math]::Round(([double]$vol.FreeSpace/[double]$vol.Size)*100,1)
if($free -lt 12){ $recommend.Add('Espaço livre baixo: limpar TEMP antigo e investigar capacidade; não apagar dados do laboratório.') }
if(@($drives | Where-Object {$_.HealthStatus -and $_.HealthStatus -ne 'Healthy'}).Count -gt 0 -or $errors.Count -gt 0){$recommend.Add('Possível problema físico ou de I/O: abrir chamado de hardware e garantir backup antes de reparos.')}
if(@($drives | Where-Object {$_.MediaType -eq 'HDD'}).Count -gt 0){$recommend.Add('Disco mecânico identificado: avaliar migração para SSD conforme política da TI.')}
if($recommend.Count -eq 0){$recommend.Add('Correlacionar os processos e o monitor de recursos com o horário da lentidão; evite alterar serviços sem evidências.')}
[PSCustomObject]@{Computador=$env:COMPUTERNAME; SO=$os.Caption; EspacoLivrePorcento=$free; Armazenamento=$drives; Amostras=$measure; EventosDisco=$errors; Recomendacoes=$recommend; Nota='Diagnóstico somente leitura; não é reparo universal para disco 100%.'}
'''


# Desinstala SOMENTE os IDs do catálogo, sem --purge, sem remoção extra de dados,
# e sem interferir na manutenção/otimização Windows.
UNINSTALL_PS = r'''param($json)
$ErrorActionPreference='Stop'
$cfg=$json | ConvertFrom-Json
$packages=@($cfg.packages)
if($packages.Count -lt 1 -or $packages.Count -gt 5){ throw 'Quantidade não permitida.' }
$w=Get-Command winget.exe -ErrorAction SilentlyContinue
if(-not $w){ throw 'WinGet indisponível nesta sessão remota. Contate o gestor de implantação corporativa.' }
$done=@()
foreach($id in $packages){
 if([string]$id -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]{2,100}$'){ throw 'ID de pacote inválido.' }
 $msg=(& $w.Source uninstall --id ([string]$id) --exact --silent --disable-interactivity --accept-source-agreements 2>&1 | Out-String)
 $code=$LASTEXITCODE
 $done+= [PSCustomObject]@{ Pacote=[string]$id; CodigoSaida=$code; Resultado=([string]$msg).Trim().Substring(0,[Math]::Min(450,([string]$msg).Trim().Length)) }
}
[PSCustomObject]@{ Computador=$env:COMPUTERNAME; Desinstalacoes=$done; Observacao='Somente os apps explicitamente selecionados; configurações e dados de aplicativos não são apagados pelo utilitário.' }
'''
