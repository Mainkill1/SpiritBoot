$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$s='C:\xemu-lab\incoming\full-xiso-comparison-20261013'
$bioses=@{complex='C:\xemu-lab\XEMU FILES\BIOS\Complex_4627v1.03.bin';candidate='C:\xemu-lab\incoming\doa-save-20261013\save-path-candidate64.bin'}
$port=59100
foreach($fixture in @('kernel-performance-portable','stream-timing','sync-cost')){
 for($pair=0;$pair -lt 7;$pair++){
  $order=if($pair%2 -eq 0){@('complex','candidate')}else{@('candidate','complex')}
  foreach($side in $order){
   $label='paired-'+$fixture+'-'+$pair+'-'+$side
   & ($s+'\run-one.ps1') -Profile $label -Bios $bioses[$side] -Fixture ($s+'\'+$fixture+'.iso') -Port $port
   $r=(Get-Content ($s+'\latest-probe-'+$label+'.txt')).Trim()
   $result=Get-Content ($r+'\result.json') -Raw|ConvertFrom-Json
   if(!$result.exited -or $result.exitCode -ne 0){throw ('Unfinished paired trial '+$label)}
   $port+=2
  }
 }
}
'complete'|Set-Content ($s+'\paired-complete.txt')
