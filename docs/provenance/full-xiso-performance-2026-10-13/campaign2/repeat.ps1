$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$s='C:\xemu-lab\incoming\full-xiso-comparison-repeat-20261013'
& ($s+'\paired.ps1')
& ($s+'\leaf-paired.ps1')
'complete'|Set-Content ($s+'\repeat-complete.txt')
