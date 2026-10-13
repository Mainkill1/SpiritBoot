$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$s='C:\xemu-lab\incoming\full-xiso-comparison-repeat-20261013'
$bioses=@{complex='C:\xemu-lab\XEMU FILES\BIOS\Complex_4627v1.03.bin';candidate='C:\xemu-lab\incoming\doa-save-20261013\save-path-candidate64.bin'}
$port=59700
for($pair=0;$pair -lt 8;$pair++){
 $order=if($pair%2 -eq 0){@('complex','candidate')}else{@('candidate','complex')}
 foreach($side in $order){
  $label='leaf-'+$pair+'-'+$side
  & ($s+'\run-one.ps1') -Profile $label -Bios $bioses[$side] -Fixture ($s+'\api-leaf-performance.iso') -Port $port
  $r=(Get-Content ($s+'\latest-probe-'+$label+'.txt')).Trim()
  $result=Get-Content ($r+'\result.json') -Raw|ConvertFrom-Json
  $log=Get-Content ($r+'\serial.log') -Raw
  if(!$result.exited -or $result.exitCode -ne 0 -or ([regex]::Matches($log,'# LEAF name=')).Count -ne 634){throw ('Unfinished leaf trial '+$label)}
  $port+=2
 }
}
'complete'|Set-Content ($s+'\leaf-paired-complete.txt')
