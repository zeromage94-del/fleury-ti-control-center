"""Operações Windows de diagnóstico e remediação controlada via WinRM.

Usa a identidade Windows do técnico; não armazena senha, não altera proteção
antifraude de pagamentos e não apaga perfis. A ação Downloads remove os arquivos
pessoais dessa pasta quando o técnico clica na limpeza integral.
"""
import json
import re

# Um argumento JSON é entregue ao ScriptBlock, sem interpolar conteúdo remoto em código.
def call(remote_script, target, body, config=None, timeout=70):
    return remote_script(target, body, timeout, json.dumps(config or {}, ensure_ascii=False))

PERFORMANCE_PS = r'''param($json)
$ErrorActionPreference = 'Stop'
$os=Get-CimInstance Win32_OperatingSystem
$disk=@(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | Select-Object DeviceID, @{N='LivreGB';E={[math]::Round($_.FreeSpace/1GB,1)}}, @{N='TotalGB';E={[math]::Round($_.Size/1GB,1)}})
$processes=@(Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 8 @{N='Nome';E={$_.ProcessName}}, @{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,0)}})
$profiles=@(Get-CimInstance Win32_UserProfile -ErrorAction SilentlyContinue | Where-Object {
    -not $_.Special -and $_.LocalPath -match '^[a-zA-Z]:\\Users\\[^\\]+$'
})
$lastBoot=$os.LastBootUpTime
[PSCustomObject]@{
 Host=$env:COMPUTERNAME; Sistema=$os.Caption
 MemoriaLivreGB=[math]::Round([double]$os.FreePhysicalMemory/1MB,2)
 MemoriaTotalGB=[math]::Round([double]$os.TotalVisibleMemorySize/1MB,2)
 UptimeDias=[math]::Round(((Get-Date)-$lastBoot).TotalDays,1)
 Discos=$disk; Processos=$processes; PerfisLocais=$profiles.Count
 Spooler=[string](Get-Service Spooler -ErrorAction SilentlyContinue).Status
 Nota='RAM em uso e pouco espaço em disco podem indicar gargalos; limpeza de temporários não corrige problemas de hardware.'
}'''

# Somente arquivos antigos em C:\Windows\Temp e AppData\Local\Temp de cada perfil.
# Ignora reparse points/symlinks e não remove pastas ou arquivos em uso.
CLEANUP_PS = r'''param($json)
$ErrorActionPreference='Stop'
$cfg=$json | ConvertFrom-Json
$days=[int]$cfg.days
if($days -lt 7 -or $days -gt 365){ throw 'A idade deve estar entre 7 e 365 dias.' }
$commit=($cfg.commit -eq $true)
$cutoff=(Get-Date).AddDays(-$days)
$profiles=@(Get-CimInstance Win32_UserProfile -ErrorAction Stop | Where-Object {
    -not $_.Special -and $_.LocalPath -match '^[a-zA-Z]:\\Users\\[^\\]+$'
})
$roots=New-Object System.Collections.Generic.List[string]
$windowsTemp=Join-Path $env:windir 'Temp'
$roots.Add($windowsTemp)
foreach($p in $profiles){ $roots.Add((Join-Path $p.LocalPath 'AppData\Local\Temp')) }
$found=0; $bytes=[long]0; $deleted=0; $freed=[long]0; $failures=0; $skipped=0
$limit=12000; $visited=0; $capped=$false
foreach($root in $roots){
 if($capped){ break }
 if(-not [IO.Directory]::Exists($root)){ continue }
 # Verify every ancestor too: a junction at the TEMP root must not be followed.
 try{
  $full=[IO.Path]::GetFullPath($root)
  $ancestor=[IO.Path]::GetPathRoot($full)
  foreach($part in $full.Substring($ancestor.Length).Split([char]'\')){
   if($part){$ancestor=Join-Path $ancestor $part}
   if(([IO.File]::GetAttributes($ancestor) -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'TEMP redirecionado preservado.'}
  }
 }catch{$failures++;continue}
 $queue=New-Object 'System.Collections.Generic.Queue[object]'
 $queue.Enqueue(@{Path=$root;Depth=0})
 while($queue.Count -gt 0){
  $entry=$queue.Dequeue()
  try{ $items=[IO.Directory]::EnumerateFileSystemEntries([string]$entry.Path) } catch { $failures++; continue }
  foreach($item in $items){
   $visited++
   if($visited -gt $limit){ $capped=$true; break }
   try{
    $attrs=[IO.File]::GetAttributes($item)
    if(($attrs -band [IO.FileAttributes]::ReparsePoint) -ne 0){ $skipped++; continue }
    if(($attrs -band [IO.FileAttributes]::Directory) -ne 0){
     if([int]$entry.Depth -lt 5){ $queue.Enqueue(@{Path=$item;Depth=([int]$entry.Depth+1)}) }
     else{$capped=$true}
     continue
    }
    $fi=New-Object IO.FileInfo($item)
    if($fi.LastWriteTime -ge $cutoff){ $skipped++; continue }
    # Somente .tmp e .temp antigos; nunca fotos, documentos, logs, dados ZPL/TEF,
    # exportações de laboratório, instaladores ou arquivos sem extensão.
    if($fi.Extension.ToLowerInvariant() -notin @('.tmp','.temp')){ $skipped++; continue }
    $found++; $bytes += [long]$fi.Length
    if($commit){
     try{
      $len=[long]$fi.Length
      [IO.File]::Delete($item)
      $deleted++; $freed+=$len
     }catch{ $failures++ }
    }
   } catch { $failures++ }
  }
  if($capped){ break }
 }
}
[PSCustomObject]@{
 Modo=$(if($commit){'Limpeza executada'}else{'Simulação; nada foi apagado'})
 IdadeMinimaDias=$days; PerfisInspecionados=$profiles.Count; PastasTemporarias=$roots.Count
 ArquivosElegiveis=$found; PotencialMB=[math]::Round($bytes/1MB,1)
 ArquivosRemovidos=$deleted; LiberadosMB=[math]::Round($freed/1MB,1)
 Falhas=$failures; Ignorados=$skipped; ItensInspecionados=$visited
 LimiteAtingido=$capped
 Aviso='Somente arquivos .tmp/.temp antigos em TEMP. Preserva logs, imagens, documentos, etiquetas e demais formatos. Arquivos em uso são ignorados.'
}'''

# Downloads: exclusão integral autorizada pelo clique, separada de TEMP.
DOWNLOADS_PS = r'''param($json)
$ErrorActionPreference='Stop'
# Scope comes exclusively from the target's local user profiles, never HTTP paths.
$profiles=@(Get-CimInstance Win32_UserProfile -ErrorAction Stop | Where-Object {
 -not $_.Special -and $_.LocalPath -match '^[A-Za-z]:\\.+'})
$seen=@{}; $roots=0; $ignoredRoots=0; $found=0; $deleted=0; $removedDirs=0
$failures=0; $skipped=0; $visited=0; $freed=[long]0
function Assert-OrdinaryDirectory([string]$path){
 $full=[IO.Path]::GetFullPath($path)
 if($full -notmatch '^[A-Za-z]:\\'){throw 'Somente pastas locais.'}
 $part=[IO.Path]::GetPathRoot($full)
 foreach($name in $full.Substring($part.Length).Split([char]'\')){
  if($name){$part=Join-Path $part $name}
  $attrs=[IO.File]::GetAttributes($part)
  if(($attrs -band [IO.FileAttributes]::ReparsePoint) -ne 0){throw 'Pasta redirecionada ignorada.'}
  if(($attrs -band [IO.FileAttributes]::Directory) -eq 0){throw 'Pasta inválida.'}
 }
}
foreach($profile in $profiles){
 try{
  $p=[IO.Path]::GetFullPath([string]$profile.LocalPath).TrimEnd([char]'\')
  if($p -eq [IO.Path]::GetPathRoot($p).TrimEnd([char]'\')){$ignoredRoots++;continue}
  $root=Join-Path $p 'Downloads'
  if($seen.ContainsKey($root)){continue};$seen[$root]=$true
  # An absent Downloads folder is normal; access failures must remain visible.
  try{$rootAttrs=[IO.File]::GetAttributes($root)}
  catch [IO.FileNotFoundException]{continue}
  catch [IO.DirectoryNotFoundException]{continue}
  try{Assert-OrdinaryDirectory $root}catch{$ignoredRoots++;$skipped++;continue}
  $roots++
 }catch{$failures++;$ignoredRoots++;continue}
 $queue=New-Object 'System.Collections.Generic.Queue[string]'
 $dirs=New-Object 'System.Collections.Generic.List[string]'
 $queue.Enqueue($root)
 while($queue.Count -gt 0){
  $dir=$queue.Dequeue()
  try{
   Assert-OrdinaryDirectory $dir
   $items=[IO.Directory]::GetFileSystemEntries($dir)
   $dirs.Add($dir)
  }catch{$failures++;continue}
  foreach($item in $items){
   $visited++; $attrs=$null; $changedAttrs=$false
   try{
    Assert-OrdinaryDirectory ([IO.Path]::GetDirectoryName($item))
    $attrs=[IO.File]::GetAttributes($item)
    if(($attrs -band [IO.FileAttributes]::ReparsePoint) -ne 0){$skipped++;continue}
    if(($attrs -band [IO.FileAttributes]::Directory) -ne 0){$queue.Enqueue($item);continue}
    $found++
    # No age, extension, selection, depth or candidate-count filters.
    $handle=[IO.File]::Open($item,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None)
    try{$length=[long]$handle.Length}finally{$handle.Dispose()}
    Assert-OrdinaryDirectory ([IO.Path]::GetDirectoryName($item))
    $attrs=[IO.File]::GetAttributes($item)
    if(($attrs -band ([IO.FileAttributes]::ReparsePoint -bor [IO.FileAttributes]::Directory)) -ne 0){$skipped++;continue}
    if(($attrs -band [IO.FileAttributes]::ReadOnly) -ne 0){
     [IO.File]::SetAttributes($item,($attrs -band (-bnot [IO.FileAttributes]::ReadOnly)))
     $changedAttrs=$true
    }
    [IO.File]::Delete($item)
    $deleted++;$freed+=$length
   }catch{
    $failures++
    if($changedAttrs -and [IO.File]::Exists($item)){
     try{[IO.File]::SetAttributes($item,$attrs)}catch{}
    }
   }
  }
 }
 # Empty subfolders are removed bottom-up; preserve each user's Downloads root.
 for($i=$dirs.Count-1;$i -ge 0;$i--){
  $dir=$dirs[$i]
  if([string]::Equals($dir,$root,[StringComparison]::OrdinalIgnoreCase)){continue}
  try{
   Assert-OrdinaryDirectory $dir
   if([IO.Directory]::GetFileSystemEntries($dir).Length -eq 0){
    [IO.Directory]::Delete($dir,$false);$removedDirs++
   }
  }catch{$failures++}
 }
}
[PSCustomObject]@{
 Modo='Downloads: exclusão integral executada'
 PerfisInspecionados=$profiles.Count;PastasDownloads=$roots;PastasIgnoradas=$ignoredRoots
 ArquivosEncontrados=$found;ArquivosRemovidos=$deleted;PastasRemovidas=$removedDirs
 BytesLiberados=$freed;LiberadosMB=[math]::Round($freed/1MB,1)
 Falhas=$failures;Ignorados=$skipped;ItensInspecionados=$visited
 Aviso='Exclusão definitiva de todos os arquivos das pastas Downloads padrão dos perfis locais, incluindo subpastas, arquivos recentes e todos os formatos. Links e pastas redirecionadas não são seguidos. Arquivos em uso ou sem permissão são contabilizados no resultado.'
}'''

# Otimização expressa = apenas a limpeza conservadora de TEMP + medição de espaço.
# Não muda inicialização, antivírus, indexação, registro, GPO ou aplicativos.
QUICK_OPTIMIZE_PS = r'''param($json)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetPathRoot($env:windir)
$drive=[System.IO.DriveInfo]::new($root)
$before=[math]::Round($drive.AvailableFreeSpace/1GB,2)
$cleanup = & {
''' + CLEANUP_PS.replace('param($json)\n','',1) + r'''
}
$drive=[System.IO.DriveInfo]::new($root)
$after=[math]::Round($drive.AvailableFreeSpace/1GB,2)
[PSCustomObject]@{
 Computador=$env:COMPUTERNAME
 Perfil='Otimização rápida conservadora'
 EspacoLivreAntesGB=$before
 EspacoLivreDepoisGB=$after
 Limpeza=$cleanup
 ProgramasRemovidos=0
 SegurancaWindowsAlterada=$false
 Mensagem='Somente TEMP antigo. Sem remoção de aplicativos, sem tweaks de registro, sem parar serviços, sem desabilitar proteção.'
 Aviso='Melhora de desempenho não é garantida. Disco 100% requer diagnóstico de I/O, eventos e integridade física.'
}
'''

ZEBRA_PS = r'''param($json)
$ErrorActionPreference='Stop'
$cfg=$json | ConvertFrom-Json
$name=[string]$cfg.printer
$p=Get-Printer -Name $name -ErrorAction Stop
if(($p.Name -notmatch 'Zebra|ZT\d|ZD\d|GK\d|GX\d|GC\d') -and ($p.DriverName -notmatch 'Zebra|ZDesigner')){
 throw 'A impressora selecionada não foi reconhecida como Zebra. Confira o nome e o driver.'
}
$port=Get-PrinterPort -Name $p.PortName -ErrorAction SilentlyContinue
$jobs=@(Get-PrintJob -PrinterName $p.Name -ErrorAction SilentlyContinue)
# Metadados do driver: somente leitura; nem todo driver Zebra implementa estes cmdlets.
$printCfg=$null
try{
 $pc=Get-PrintConfiguration -PrinterName $p.Name -ErrorAction Stop
 $printCfg=[PSCustomObject]@{TamanhoPapel=[string]$pc.PaperSize;
  Orientacao=[string]$pc.Orientation; Colorido=[string]$pc.Color;
  Duplex=[string]$pc.DuplexingMode}
}catch{}
$driverProperties=@()
try{
 $driverProperties=@(Get-PrinterProperty -PrinterName $p.Name -ErrorAction Stop |
  Where-Object { $_.PropertyName -match 'label|media|paper|dpi|darkness|speed|zpl|width|height' } |
  Select-Object -First 16 PropertyName,@{N='Valor';E={[string]$_.Value}})
}catch{}
$addr=[string]$port.PrinterHostAddress
$portNumber=9100
if($port.PortNumber -and [int]$port.PortNumber -gt 0){$portNumber=[int]$port.PortNumber}
$tcp='Não aplicável: USB/porta local ou IP ausente'
# Somente conectividade TCP; nunca enviar ZPL ou comandos de calibração automaticamente.
if($addr -and $addr -notmatch '^0\.0\.0\.0$' -and $portNumber -ge 1 -and $portNumber -le 65535){
 $client=New-Object System.Net.Sockets.TcpClient
 try{
  $pending=$client.BeginConnect($addr,$portNumber,$null,$null)
  if($pending.AsyncWaitHandle.WaitOne(1700,$false)){
    try{$client.EndConnect($pending);$tcp='Conexão TCP estabelecida'}catch{$tcp='Porta indisponível'}
  }else{$tcp='Tempo limite TCP'}
 }catch{$tcp='Falha no teste TCP'}finally{$client.Close()}
}
[PSCustomObject]@{
 Nome=$p.Name; Driver=$p.DriverName; Porta=$p.PortName
 StatusWindows=[string]$p.PrinterStatus; TrabalhosNaFila=$jobs.Count
 EnderecoIP=$addr; NumeroPorta=$portNumber; TesteTCP=$tcp
 ConfiguracaoWindows=$printCfg; PropriedadesDriver=$driverProperties
 Compartilhada=[bool]$p.Shared; Spooler=[string](Get-Service Spooler).Status
 Orientacoes=@('Se a mídia avança fora do ponto, conferir tipo gap/marca preta/contínua, DPI e tamanho da etiqueta no driver.',
 'Calibração deve seguir o manual do modelo (ZD/ZT/GK); não enviar comandos ZPL automaticamente.',
 'Para impressão ausente: conferir cabo/rede, porta Windows, modo de linguagem ZPL/EPL e fila travada.')
}'''

PINPAD_PS = r'''param($json)
$ErrorActionPreference='Stop'
# Somente inventário PnP e serviços Windows. Nenhum comando é enviado ao PINPAD.
$entities=@(Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object {
 $_.Name -match 'PIN\s*PAD|PINPAD|Ingenico|Verifone|Gertec|PAX|Stone|USB Serial|Serial Port|COM[0-9]+|Elgin'
} | Select-Object -First 35 @{N='Dispositivo';E={$_.Name}},Manufacturer,Status,Service)
$ports=@(Get-CimInstance Win32_SerialPort -ErrorAction SilentlyContinue |
 Select-Object -First 30 DeviceID,Name,Status,ProviderType)
$services=@(Get-Service -ErrorAction Stop | Where-Object {
 $_.Name -match 'TEF|SiTef|PayGo|PinPad|CliSiTef|VSPague|V-Pague|Cielo|Gertec|Stone' -or
 $_.DisplayName -match 'TEF|SiTef|PayGo|PinPad|CliSiTef|VSPague|V-Pague|Cielo|Gertec|Stone'
} | Select-Object -First 25 Name,DisplayName,@{N='Status';E={$_.Status.ToString()}})
[PSCustomObject]@{
 Computador=$env:COMPUTERNAME; Dispositivos=$entities; PortasCOM=$ports
 ServicosTEF=$services; ReinicioPendente='Não verificado'
 Orientacoes=@('Verifique a conexão USB/serial, alimentação e a porta COM configurada no aplicativo TEF.',
 'Confirme que não há transação em andamento antes de reiniciar qualquer serviço.',
 'Erros de host, credenciadora ou criptografia devem ser avaliados com o fornecedor do TEF/PINPAD.')
}'''

TEF_SERVICE_PS = r'''param($json)
$ErrorActionPreference='Stop'
$cfg=$json | ConvertFrom-Json
$name=[string]$cfg.service
if($name -notmatch '^[a-zA-Z0-9_.-]{1,120}$'){ throw 'Nome de serviço inválido.' }
$s=Get-Service -Name $name -ErrorAction Stop
if(($s.Name -notmatch 'TEF|SiTef|PayGo|PinPad|CliSiTef|VSPague|V-Pague|Cielo|Gertec|Stone') -and
   ($s.DisplayName -notmatch 'TEF|SiTef|PayGo|PinPad|CliSiTef|VSPague|V-Pague|Cielo|Gertec|Stone')){
 throw 'Serviço não identificado como middleware de pagamentos; ação bloqueada.'
}
if($s.Status -eq 'Running'){
 Restart-Service -InputObject $s -ErrorAction Stop
}else{
 Start-Service -InputObject $s -ErrorAction Stop
}
$s.Refresh()
[PSCustomObject]@{Servico=$s.Name; Descricao=$s.DisplayName; StatusFinal=$s.Status.ToString(); Mensagem='Operação concluída. Validar comunicação e pagamento de teste com procedimento autorizado.'}'''


def validate_days(days):
    if isinstance(days, bool) or not isinstance(days, (str, int)):
        raise ValueError('Informe idade mínima inteira para os arquivos.')
    try:
        days = int(days)
    except (TypeError, ValueError):
        raise ValueError('Informe idade mínima válida para temporários.')
    if not 7 <= days <= 365:
        raise ValueError('Idade mínima de 7 a 365 dias.')
    return days


def validate_printer(printer):
    if not isinstance(printer, str) or not 1 <= len(printer.strip()) <= 150:
        raise ValueError('Selecione uma impressora.')
    return printer.strip()


def validate_service(service):
    if not isinstance(service, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', service):
        raise ValueError('Nome de serviço inválido.')
    return service

# Diagnóstico de '100% do disco' em Windows 10/11. As medições são uma amostra,
# não um diagnóstico definitivo do HD/SSD; eventos de storage merecem backup.
DISK_100_PS = r'''param($json)
$ErrorActionPreference='Stop'
$drive=$env:SystemDrive
$volume=Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$drive'" -ErrorAction Stop
$devices=@(Get-CimInstance Win32_DiskDrive -ErrorAction SilentlyContinue |
 Select-Object -First 8 Model,MediaType,InterfaceType,Status,Size,DeviceID)
$physical=@(Get-PhysicalDisk -ErrorAction SilentlyContinue |
 Select-Object -First 12 FriendlyName,MediaType,HealthStatus,OperationalStatus)
$sample=@(Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk -ErrorAction SilentlyContinue |
 Where-Object {$_.Name -ne '_Total'} | Select-Object -First 12 Name,PercentIdleTime,
 AvgDiskQueueLength,DiskBytesPersec,AvgDisksecPerTransfer)
$util=@(foreach($s in $sample){
 $busy=$null
 if($null -ne $s.PercentIdleTime){
  $busy=[math]::Round([math]::Max(0,[math]::Min(100,100-[double]$s.PercentIdleTime)),1)
 }
 [PSCustomObject]@{Unidade=$s.Name; OcupacaoEstimadaPct=$busy;
 FilaMedia=[math]::Round([double]$s.AvgDiskQueueLength,2);
 TaxaMBs=[math]::Round([double]$s.DiskBytesPersec/1MB,2);
 LatenciaAproxMs=[math]::Round([double]$s.AvgDisksecPerTransfer*1000,2)}
})
$before=@{}
try{
 Get-CimInstance Win32_Process -ErrorAction Stop | ForEach-Object {
  $before[[string]$_.ProcessId]=[long]$_.ReadTransferCount+[long]$_.WriteTransferCount
 }
 Start-Sleep -Seconds 2
 $io=@(Get-CimInstance Win32_Process -ErrorAction Stop | ForEach-Object {
  $id=[string]$_.ProcessId
  if($before.ContainsKey($id)){
   $delta=[math]::Max(0,[long]$_.ReadTransferCount+[long]$_.WriteTransferCount-$before[$id]);
   [PSCustomObject]@{Processo=$_.Name;PID=$_.ProcessId;MBem2s=[math]::Round($delta/1MB,2)}
  }
 } | Sort-Object MBem2s -Descending | Select-Object -First 8)
}catch{$io=@()}
$events=@()
try{
 $events=@(Get-WinEvent -FilterHashtable @{
  LogName='System'; Id=@(7,51,55,129,153,157); StartTime=(Get-Date).AddDays(-7)
 } -MaxEvents 80 -ErrorAction Stop | Where-Object {
  $_.ProviderName -match 'disk|stor|iaStor|nvme|ntfs|volmgr'
 } | Select-Object -First 25 @{N='ID';E={$_.Id}},
  @{N='Origem';E={$_.ProviderName}},@{N='Quando';E={[string]$_.TimeCreated}})
}catch{}
$services=@(foreach($n in @('SysMain','WSearch')){
 $s=Get-Service -Name $n -ErrorAction SilentlyContinue
 if($s){[PSCustomObject]@{Nome=$n;Status=$s.Status.ToString();Inicio=$s.StartType.ToString()}}
})
$freeGB=[math]::Round([double]$volume.FreeSpace/1GB,1)
$percentFree=if([double]$volume.Size -gt 0){[math]::Round(100*[double]$volume.FreeSpace/[double]$volume.Size,1)}else{0}
$alerts=New-Object System.Collections.Generic.List[string]
if($percentFree -lt 15){$alerts.Add('Pouco espaço na unidade do sistema. Verifique limpeza de temporários e consumo real antes de agir.')}
if($events.Count -gt 0){$alerts.Add('Foram encontrados eventos de armazenamento/NTFS: priorize backup e diagnóstico do hardware; não faça reparos pesados às cegas.')}
if(@($physical | Where-Object {$_.HealthStatus -and $_.HealthStatus -ne 'Healthy'}).Count -gt 0){
 $alerts.Add('O subsistema de armazenamento indicou estado diferente de Healthy. Encaminhe para avaliação e backup.')
}
if(@($util | Where-Object {$_.OcupacaoEstimadaPct -ge 95}).Count -gt 0){
 $alerts.Add('Alta ocupação do disco detectada nesta amostra; identifique a causa antes de reiniciar serviços.')
}
[PSCustomObject]@{
 Computador=$env:COMPUTERNAME; UnidadeSistema=$drive; LivreGB=$freeGB;
 TotalGB=[math]::Round([double]$volume.Size/1GB,1); LivrePct=$percentFree
 Discos=$devices; DiscosFisicos=$physical; AtividadeDiscos=$util
 ProcessosIO=$io; EventosDisco=$events; Servicos=$services
 Alertas=@($alerts.ToArray())
 Recomendações=@(
 'Primeiro: verificar backup, saúde SMART/firmware e eventos 7/51/55/129/153/157 antes de forçar reparos.',
 'Baixo espaço: limpar somente temporários antigos dos perfis, sem tocar em Downloads e dados de trabalho.',
 'I/O elevado: avaliar processo causador, antivírus, atualização em curso, arquivo de paginação e aplicativos de início.',
 'Windows Search/SysMain: reinicialização pontual de serviço pode testar hipótese; não desabilitar permanentemente sem evidência e GPO.',
 'Se HDD mecânico saturar frequentemente: avaliar substituição por SSD, RAM e plano de migração com TI.',
 'SFC e DISM são para corrupção do Windows, não para recuperar disco com defeito físico.')
 Nota='Amostra aproximada de contadores e I/O por 2 segundos; status saudável não substitui diagnóstico SMART do fabricante.'
}'''

DISK_SERVICE_PS = r'''param($json)
$ErrorActionPreference='Stop'
$cfg=$json | ConvertFrom-Json
$service=[string]$cfg.service
if($service -cnotin @('SysMain','WSearch')){throw 'Serviço não permitido.'}
$s=Get-Service -Name $service -ErrorAction Stop
$before=$s.Status.ToString()
if($s.Status -eq 'Running'){
 Restart-Service -Name $service -ErrorAction Stop
 $action='Serviço reiniciado; inicialização original preservada'
}else{
 $action='Nenhuma alteração: o serviço não estava em execução'
}
$s=Get-Service -Name $service -ErrorAction Stop
[PSCustomObject]@{Servico=$service;Antes=$before;Depois=$s.Status.ToString();Acao=$action;
 Aviso='Teste pontual apenas; se o disco continuar em 100%, investigue processos, armazenamento e eventos.'}'''

DISM_CHECK_PS = r'''param($json)
$ErrorActionPreference='Stop'
$lines=@(& dism.exe /Online /Cleanup-Image /CheckHealth 2>&1 | Out-String)
$exit=$LASTEXITCODE
[PSCustomObject]@{Ferramenta='DISM CheckHealth';Codigo=$exit;
 Resumo=($lines -join "`n").Trim().Substring(0,[math]::Min(2200,(($lines -join "`n").Trim()).Length));
 Aviso='CheckHealth é diagnóstico rápido; não executa RestoreHealth. Se houver corrupção, aplicar reparação por mudança aprovada.'}'''

DISK_SCAN_PS = r'''param($json)
$ErrorActionPreference='Stop'
$vol=$env:SystemDrive
# /scan é uma verificação online, sem marcar uma correção offline forçada.
$out=(& chkdsk.exe $vol /scan 2>&1 | Out-String)
$code=$LASTEXITCODE
[PSCustomObject]@{Unidade=$vol;Codigo=$code;
 Resumo=$out.Trim().Substring(0,[math]::Min(2600,$out.Trim().Length));
 Aviso='A verificação pode elevar muito o I/O. Não executar em unidade com sinais de falha física sem backup e avaliação.'}'''

SFC_SCAN_PS = r'''param($json)
$ErrorActionPreference='Stop'
$out=(& sfc.exe /scannow 2>&1 | Out-String)
$code=$LASTEXITCODE
[PSCustomObject]@{Ferramenta='SFC scannow';Codigo=$code;
 Resumo=$out.Trim().Substring(0,[math]::Min(2600,$out.Trim().Length));
 Aviso='Verificação e reparo de arquivos de sistema; aguarde término e reavalie desempenho. Não conserta defeito físico.'}'''


def validate_disk_service(service):
    if service not in ('SysMain', 'WSearch'):
        raise ValueError('Somente SysMain e WSearch são permitidos.')
    return service

# Gestão de pontos de restauração. O controle ocorre na máquina de destino e
# depende da Proteção do Sistema, privilégios concedidos e políticas de TI.
# Não habilita proteção, não altera frequência e não toca nas cópias VSS de backup.
RESTORE_LIST_PS = r'''param($json)
$ErrorActionPreference='Stop'
function ReadPoints {
  $items=@(Get-ComputerRestorePoint -ErrorAction Stop | Sort-Object SequenceNumber -Descending)
  return @($items | Select-Object -First 100 | ForEach-Object {
    $stamp=$null
    try{ $stamp=[Management.ManagementDateTimeConverter]::ToDateTime([string]$_.CreationTime) }
    catch{try{$stamp=[datetime]$_.CreationTime}catch{}}
    [PSCustomObject]@{Numero=[int64]$_.SequenceNumber;Descricao=[string]$_.Description;
      CriadoEm=$(if($stamp){$stamp.ToString('yyyy-MM-dd HH:mm:ss')}else{'Data indisponível'});
      IdadeDias=$(if($stamp){[math]::Floor(((Get-Date)-$stamp).TotalDays)}else{$null});
      MaisRecente=($items[0].SequenceNumber -eq $_.SequenceNumber)}
  })
}
$items=@(ReadPoints)
[PSCustomObject]@{Computador=$env:COMPUTERNAME;Quantidade=$items.Count;
 Pontos=$items;Nota='Pontos do Windows; não inclui nem apaga snapshots de backup VSS. A criação requer Proteção do Sistema habilitada.'}'''

RESTORE_CREATE_PS = r'''param($json)
$ErrorActionPreference='Stop'
$cfg=$json | ConvertFrom-Json
$description=[string]$cfg.description
if($description.Length -lt 5 -or $description.Length -gt 100){throw 'Descrição entre 5 e 100 caracteres.'}
$old=@(Get-ComputerRestorePoint -ErrorAction SilentlyContinue | Sort-Object SequenceNumber -Descending)
# Não mexer na política de frequência do Windows. Apresentar motivo claramente.
if($old.Count -gt 0){
 try{$latest=[Management.ManagementDateTimeConverter]::ToDateTime([string]$old[0].CreationTime)}
 catch{$latest=$null}
 if($latest -and $latest -gt (Get-Date).AddHours(-24)){
  throw 'Já existe ponto de restauração das últimas 24 horas. Aguarde o intervalo normal do Windows; nenhuma alteração foi feita.'
 }
}
Checkpoint-Computer -Description $description -RestorePointType MODIFY_SETTINGS -ErrorAction Stop
$points=@(Get-ComputerRestorePoint -ErrorAction Stop | Sort-Object SequenceNumber -Descending)
if($points.Count -eq 0){throw 'Windows não retornou ponto depois da criação; verifique a Proteção do Sistema.'}
[PSCustomObject]@{Criado=$true;Descricao=[string]$points[0].Description;
 Numero=[int64]$points[0].SequenceNumber;Computador=$env:COMPUTERNAME;
 Nota='Criado conforme as políticas do Windows. Isto não substitui backup de arquivos de trabalho.'}'''

RESTORE_DELETE_PS = r'''param($json)
$ErrorActionPreference='Stop'
$cfg=$json | ConvertFrom-Json
$number=[uint32]$cfg.sequence
if($number -eq 0){throw 'Número do ponto inválido.'}
$all=@(Get-ComputerRestorePoint -ErrorAction Stop | Sort-Object SequenceNumber -Descending)
if($all.Count -lt 2){throw 'É necessário preservar ao menos um ponto de restauração.'}
if([uint32]$all[0].SequenceNumber -eq $number){throw 'O ponto de restauração mais recente está protegido.'}
$selected=@($all | Where-Object {[uint32]$_.SequenceNumber -eq $number})
if($selected.Count -ne 1){throw 'Ponto solicitado não está disponível.'}
try{$date=[Management.ManagementDateTimeConverter]::ToDateTime([string]$selected[0].CreationTime)}
catch{throw 'Data inválida: exclusão bloqueada.'}
try{$latestDate=[Management.ManagementDateTimeConverter]::ToDateTime([string]$all[0].CreationTime)}
catch{throw 'Data do ponto mais recente indisponível: exclusão bloqueada.'}
if($date -gt (Get-Date).AddDays(-14)){throw 'Só é permitida a exclusão de pontos com pelo menos 14 dias.'}
if($latestDate -lt (Get-Date).AddDays(-7)){throw 'Não há ponto recente nos últimos 7 dias. Crie um ponto novo antes de excluir o antigo.'}
# API oficial, remoção por número de sequência. Não usar vssadmin delete shadows.
$code=@'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class FleuryRestorePointAPI {
  [UnmanagedFunctionPointer(CallingConvention.Winapi)]
  private delegate uint RemoveDelegate(uint number);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  private static extern IntPtr LoadLibrary(string path);
  [DllImport("kernel32.dll", CharSet=CharSet.Ansi, SetLastError=true)]
  private static extern IntPtr GetProcAddress(IntPtr module, string name);
  [DllImport("kernel32.dll", SetLastError=true)]
  private static extern bool FreeLibrary(IntPtr module);
  public static uint Remove(uint number) {
    IntPtr lib=LoadLibrary("SrClient.dll");
    if (lib==IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
    try {
      IntPtr address=GetProcAddress(lib,"SRRemoveRestorePoint");
      if (address==IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
      var remove=(RemoveDelegate)Marshal.GetDelegateForFunctionPointer(address,typeof(RemoveDelegate));
      return remove(number);
    } finally { FreeLibrary(lib); }
  }
}
'@
if(-not ('FleuryRestorePointAPI' -as [type])){ Add-Type -TypeDefinition $code -ErrorAction Stop }
$result=[FleuryRestorePointAPI]::Remove($number)
if($result -ne 0){throw ('Windows não removeu o ponto. Código: ' + $result)}
$remaining=@(Get-ComputerRestorePoint -ErrorAction Stop | Where-Object {[uint32]$_.SequenceNumber -eq $number})
if($remaining.Count){throw 'O Windows retornou sucesso, mas o ponto ainda aparece listado. Confira localmente.'}
[PSCustomObject]@{Removido=$true;Numero=$number;Descricao=[string]$selected[0].Description;
 Computador=$env:COMPUTERNAME;Nota='Removido somente o ponto selecionado. O ponto mais recente foi preservado.'}'''


def validate_restore_desc(value):
    if not isinstance(value, str):
        raise ValueError('Informe uma descrição para o ponto.')
    value = value.strip()
    if not 5 <= len(value) <= 100 or any(ord(ch) < 32 for ch in value):
        raise ValueError('Descrição entre 5 e 100 caracteres, sem caracteres de controle.')
    return value


def validate_restore_sequence(value):
    try:
        n = int(value)
    except (ValueError, TypeError):
        raise ValueError('Número do ponto inválido.')
    if isinstance(value, bool) or n < 1 or n > 0xFFFFFFFF or str(value) != str(n):
        raise ValueError('Número do ponto inválido.')
    return n


# Rotinas de referência a utilitários de manutenção: diagnósticos e reparos pontuais.
# Não importa nem executa automaticamente scripts externos WinUtil/Vicarius.
UPDATE_STATUS_PS = r'''param($json)
$ErrorActionPreference='Stop'
$os=Get-CimInstance Win32_OperatingSystem
$last=@(Get-HotFix -ErrorAction SilentlyContinue | Sort-Object InstalledOn -Descending |
 Select-Object -First 12 HotFixID,Description,InstalledOn)
$pending = [PSCustomObject]@{
 CBS = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
 Update = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
}
[PSCustomObject]@{Computador=$env:COMPUTERNAME;Versao=$os.Caption;Build=$os.BuildNumber
 UltimasAtualizacoes=$last;ReinicioPendente=$pending
 Aviso='Leitura apenas. Instalação de patches deve seguir janelas e políticas do laboratório.'}'''

SERVICE_STATUS_PS = r'''param($json)
$ErrorActionPreference='Stop'
$names=@('Winmgmt','WSearch','SysMain','Spooler','wuauserv','BITS','EventLog')
$services=@(foreach($n in $names){
 $s=Get-CimInstance Win32_Service -Filter "Name='$n'" -ErrorAction SilentlyContinue
 if($s){[PSCustomObject]@{Nome=$s.Name;Estado=$s.State;Inicializacao=$s.StartMode}}
})
[PSCustomObject]@{Computador=$env:COMPUTERNAME;Servicos=$services;Modo='Somente leitura'
 Aviso='Serviços desativados por GPO podem estar configurados intencionalmente.'}'''

NETWORK_DIAG_PS = r'''param($json)
$ErrorActionPreference='Stop'
$nic=@(Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object { $_.IPv4Address } |
 Select-Object -First 12 InterfaceAlias,@{N='IPv4';E={@($_.IPv4Address.IPAddress)}},
 @{N='Gateway';E={@($_.IPv4DefaultGateway.NextHop)}},
 @{N='DNS';E={@($_.DNSServer.ServerAddresses)}})
$tcp=@(Get-NetAdapter -ErrorAction SilentlyContinue | Select-Object -First 20 Name,Status,LinkSpeed)
[PSCustomObject]@{Computador=$env:COMPUTERNAME;Rede=$nic;Adaptadores=$tcp
 Aviso='Diagnóstico de leitura. Não redefine TCP/IP, não altera DNS, proxy, VPN ou drivers.'}'''

FLUSH_DNS_PS = r'''param($json)
$ErrorActionPreference='Stop'
Clear-DnsClientCache -ErrorAction Stop
[PSCustomObject]@{Computador=$env:COMPUTERNAME;CacheDNS='Limpo'
 Aviso='Apenas cache resolvedor DNS. Nenhuma configuração de IP, servidores DNS ou VPN alterada.'}'''

DISM_REPAIR_PS = r'''param($json)
$ErrorActionPreference='Stop'
$out=(& dism.exe /Online /Cleanup-Image /RestoreHealth 2>&1 | Out-String)
$code=$LASTEXITCODE
[PSCustomObject]@{Ferramenta='DISM RestoreHealth';Codigo=$code;
 Resumo=$out.Trim().Substring(0,[math]::Min(2600,$out.Trim().Length));
 Aviso='Reparo dos componentes do Windows. Pode consumir CPU/I-O e depender de fonte corporativa de atualização; executar apenas em janela aprovada.'}'''
