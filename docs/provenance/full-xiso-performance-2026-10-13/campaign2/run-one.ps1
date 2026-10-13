param([string]$Profile,[string]$Bios,[string]$Fixture,[int]$Port=59000)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$stage='C:\xemu-lab\incoming\full-xiso-comparison-repeat-20261013'
$baseRun='C:\xemu-lab\incoming\forza-api-native-20261013\doa-human-20261013-163331'
$exe='C:\xemu-lab\incoming\xemu-pr356-f3c528ee-release-20261013\xemu.exe'
$run=Join-Path $stage ('probe-'+$Profile+'-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss'))
New-Item $run -ItemType Directory | Out-Null
$run | Set-Content ($stage+'\latest-probe-'+$Profile+'.txt')
& 'C:\xemu-lab\tools\qemu-img.exe' create -f qcow2 -F qcow2 -b ($baseRun+'\hdd.qcow2') ($run+'\hdd.qcow2') | Out-Null
if($LASTEXITCODE){throw 'overlay failed'}
Copy-Item ($baseRun+'\eeprom.bin') ($run+'\eeprom.bin')
$config=Get-Content ($baseRun+'\xemu.toml') -Raw
foreach($pair in @(@('flashrom_path',$Bios),@('eeprom_path',($run+'\eeprom.bin')),@('hdd_path',($run+'\hdd.qcow2')),@('dvd_path',$Fixture))){
$config=[regex]::Replace($config,('(?m)^'+$pair[0]+' = .*$'),($pair[0]+' = '+(ConvertTo-Json -InputObject $pair[1] -Compress)))
}
$config | Set-Content ($run+'\xemu.toml')
$env:DISABLE_RTSS_LAYER='1';$env:DISABLE_VULKAN_OBS_CAPTURE='1'
$args=@('-m','64','-qmp',('tcp:127.0.0.1:'+$Port+',server=on,wait=off'),'-config_path',($run+'\xemu.toml'),'-device','lpc47m157','-serial',('file:'+($run+'\serial.log')))
$started=[DateTime]::UtcNow
$p=Start-Process $exe -ArgumentList $args -WorkingDirectory $run -PassThru -RedirectStandardOutput ($run+'\stdout.log') -RedirectStandardError ($run+'\stderr.log')
@{pid=$p.Id;session=(Get-Process -Id $PID).SessionId;bios=$Bios;biosSha256=(Get-FileHash $Bios).Hash;probeSha256=(Get-FileHash $Fixture).Hash;exeSha256=(Get-FileHash $exe).Hash}|ConvertTo-Json | Set-Content ($run+'\launch.json')
$done=$p.WaitForExit(180000)
if(!$done){
 & 'C:\Program Files\Python312\python.exe' ($stage+'\qmp.py') $Port stop | Set-Content ($run+'\timeout-stop.json')
}
$p.Refresh();@{exited=$done;exitCode=if($done){$p.ExitCode}else{$null};elapsedSeconds=([DateTime]::UtcNow-$started).TotalSeconds;utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content ($run+'\result.json')
