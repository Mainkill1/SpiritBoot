param(
    [Parameter(Mandatory=$true)][string]$LogPath,
    [string]$OutputDirectory = "research/kernel/hardware-results",
    [string]$Environment = ""
)
$ErrorActionPreference="Stop"
if(-not(Test-Path $LogPath)){throw"Log not found: $LogPath"}
New-Item -ItemType Directory -Force -Path $OutputDirectory|Out-Null
$lines=Get-Content $LogPath
$meta=[ordered]@{build="";submitter="";name="";kernel_version="";hardware_info="";pic_version=""}
foreach($line in $lines){
    if($line -match '^build:\s*(.*)$'){$meta.build=$Matches[1].Trim()}
    elseif($line -match '^submitter:\s*(.*)$'){$meta.submitter=$Matches[1].Trim()}
    elseif($line -match '^name:\s*(.*)$'){$meta.name=$Matches[1].Trim()}
    elseif($line -match '^kernel:\s*(.*)$'){$meta.kernel_version=$Matches[1].Trim()}
    elseif($line -match '^hardware info:\s*(.*)$'){$meta.hardware_info=$Matches[1].Trim()}
    elseif($line -match '^PIC version:\s*(.*)$'){$meta.pic_version=$Matches[1].Trim()}
}
if(-not $Environment){$Environment=if($meta.name){$meta.name}elseif($meta.pic_version){$meta.pic_version}else{"unknown"}}
$results=@{}
foreach($line in $lines){
    if($line -match '^(\d{3}) - ([^:]+): All tests PASSED$'){$o=[int]$Matches[1];$results[$o]=[ordered]@{ordinal=$o;name=$Matches[2];result="pass";reason="";duration_seconds=""}}
    elseif($line -match '^(\d{3}) - ([^:]+): One or more tests FAILED$'){$o=[int]$Matches[1];$results[$o]=[ordered]@{ordinal=$o;name=$Matches[2];result="fail";reason="";duration_seconds=""}}
    elseif($line -match '^(\d{3}) - ([^:]+): SKIPPED - (.*)$'){$o=[int]$Matches[1];$results[$o]=[ordered]@{ordinal=$o;name=$Matches[2];result="skipped";reason=$Matches[3];duration_seconds=""}}
    elseif($line -match '^(\d{3}) - ([^:]+): Test completed in ([0-9]+\.[0-9]+) seconds$'){$o=[int]$Matches[1];if($results.ContainsKey($o)){$results[$o].duration_seconds=$Matches[3]}}
}
$sourceHash=(Get-FileHash -Path $LogPath -Algorithm SHA256).Hash.ToLowerInvariant()
$sourceName=[IO.Path]::GetFileName($LogPath)
$stem=[IO.Path]::GetFileNameWithoutExtension($LogPath)-replace'[^A-Za-z0-9._-]','_'
$stamp=(Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$outPath=Join-Path $OutputDirectory "$stamp-$stem.csv"
$rows=foreach($o in $results.Keys|Sort-Object){$r=$results[$o];[pscustomobject]@{ordinal=$r.ordinal;name=$r.name;result=$r.result;reason=$r.reason;duration_seconds=$r.duration_seconds;environment=$Environment;kernel_version=$meta.kernel_version;test_revision=$meta.build;hardware_info=$meta.hardware_info;pic_version=$meta.pic_version;submitter=$meta.submitter;source_log=$sourceName;source_sha256=$sourceHash;imported_at=$stamp}}
$rows|Export-Csv $outPath -NoTypeInformation
Write-Host "Imported $($rows.Count) final API results to $outPath"
