"""Consultas exclusivamente de leitura inspiradas no fluxo de suporte dos vídeos.
Sem execução de comandos arbitrários, remoção de software ou leitura de segredos.
"""
LABELS = {
    'apps': 'Aplicativos instalados (HKLM)',
    'processes': 'Processos e memória',
    'drives': 'Discos e unidades de rede',
    'startup': 'Programas de inicialização',
}
SAFE_QUERIES = {
 'apps': r'''
$paths=@('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*')
$apps=@(Get-ItemProperty -Path $paths -ErrorAction SilentlyContinue |
 Where-Object {$_.DisplayName -and $_.DisplayName.Length -lt 170} |
 Select-Object DisplayName,DisplayVersion,Publisher |
 Sort-Object DisplayName -Unique | Select-Object -First 250)
[pscustomobject]@{Tipo='Aplicativos instalados';Observacao='Mostra instalações por máquina. Apps por perfil e MSIX podem não aparecer.';Total=$apps.Count;Itens=$apps}
''',
 'processes': r'''
$ps=@(Get-Process -ErrorAction SilentlyContinue |
 Sort-Object WorkingSet64 -Descending |
 Select-Object -First 30 Name,Id,@{n='MemoriaMB';e={[math]::Round($_.WorkingSet64/1MB,1)}},CPU)
[pscustomobject]@{Tipo='Processos';Observacao='Fotografia do uso de memória. CPU corresponde ao tempo acumulado, não à porcentagem instantânea.';Itens=$ps}
''',
 'drives': r'''
$vols=@(Get-CimInstance Win32_LogicalDisk -ErrorAction Stop |
 Select-Object DeviceID,@{n='Tipo';e={switch($_.DriveType){3 {'Disco local'} 4 {'Unidade de rede'} default {'Outro'}}}},ProviderName,@{n='LivreGB';e={if($_.Size){[math]::Round($_.FreeSpace/1GB,1)}else{$null}}},@{n='TotalGB';e={if($_.Size){[math]::Round($_.Size/1GB,1)}else{$null}}})
[pscustomobject]@{Tipo='Volumes e unidades';Observacao='As unidades mapeadas de outros usuários podem não aparecer numa sessão WinRM administrativa.';Itens=$vols}
''',
 'startup': r'''
$items=@(Get-CimInstance Win32_StartupCommand -ErrorAction SilentlyContinue |
 Select-Object Name,Location,User | Sort-Object Name -Unique | Select-Object -First 100)
[pscustomobject]@{Tipo='Inicialização';Observacao='Consulta somente leitura; não desabilita entradas, serviços ou aplicativos.';Itens=$items}
''',
}
