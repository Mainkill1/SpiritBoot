param(
    [string]$Root = ".reference",
    [string]$InventoryPath = "research/kernel/exports.csv",
    [string]$OutputPath = "research/kernel/correlation.csv",
    [string]$SummaryPath = "research/kernel/CORRELATION.md",
    [string]$HardwareResultsPath = "research/kernel/hardware-results"
)

$ErrorActionPreference = "Stop"
$RoswellPath = Join-Path $Root "roswell"
$CxbxPath = Join-Path $Root "cxbx-reloaded"
$TestsPath = Join-Path $Root "kernel-tests"
foreach ($path in @($RoswellPath,$CxbxPath,$TestsPath,$InventoryPath)) {
    if (-not (Test-Path $path)) { throw "Missing required path: $path. Run scripts/fetch-references.ps1 first." }
}
function Invoke-GitGrepPaths {
    param([string]$Repo,[string]$Needle,[string]$Prefix="")
    $result=@(& git -C $Repo grep -l -F -- $Needle 2>$null)
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) { throw "git grep failed in $Repo for $Needle" }
    if ($Prefix) { $result=@($result | Where-Object { $_ -like "$Prefix*" }) }
    return $result
}
function Get-TestBody {
    param([string]$Content,[string]$TestName)
    $escaped=[regex]::Escape($TestName)
    $pattern="TEST_FUNC\($escaped\)\s*\{(?<body>.*?)(?=\r?\nTEST_FUNC\(|\z)"
    $m=[regex]::Match($Content,$pattern,[Text.RegularExpressions.RegexOptions]::Singleline)
    if ($m.Success) { return $m.Groups["body"].Value }
    return ""
}
function Get-Subsystem([string]$Name,[int]$Ordinal) {
    if ($Ordinal -eq 0) { return "Reserved" }
    switch -Regex ($Name) {
        '^Av' {return"Av"} '^Dbg' {return"Dbg"} '^(Exf|Ex)' {return"Ex"} '^Fsc' {return"Fsc"} '^Hal' {return"Hal"}
        '^Interlocked' {return"Interlocked"} '^Iof' {return"Iof"} '^Io' {return"Io"} '^Kd' {return"Kd"} '^Ke' {return"Ke"} '^Kf' {return"Kf"} '^Ki' {return"Ki"}
        '^Mm' {return"Mm"} '^Nt' {return"Nt"} '^Obf' {return"Obf"} '^Obp' {return"Obp"} '^Ob' {return"Ob"} '^Phy' {return"Phy"} '^Ps' {return"Ps"} '^Rtl' {return"Rtl"}
        '^Xbox' {return"Xbox"} '^Xc' {return"Xc"} '^Xe' {return"Xe"} '^Irt' {return"Irt"} '^XProfp' {return"XProfp"} '^(READ|WRITE)_PORT' {return"PortIO"} '^UnknownAPI' {return"Unknown"} default {return"Misc"}
    }
}
function Get-Complexity([string]$Name,[string]$Subsystem,[string]$Kind) {
    if ($Kind -eq "reserved") {return"none"}
    if ($Name -like "MmDbg*" -or $Subsystem -in @("Dbg","Kd","XProfp","Irt","Unknown","Interlocked","PortIO")) {return"low"}
    if ($Subsystem -eq "Rtl") {if ($Name -match "Raise|Unwind|CriticalSection|Capture"){return"medium"};return"low"}
    if ($Subsystem -eq "Xc") {return"medium"}
    if ($Subsystem -in @("Mm","Io","Iof","Ob","Obp","Obf","Ps","Fsc","Nt")) {return"high"}
    if ($Subsystem -in @("Ke","Kf","Ki")) {if ($Name -match "Wait|Timer|Apc|Dpc|Thread|Irql|Interrupt|Queue|Event|Mutant|Semaphore|Synchronize|Delay|Stall"){return"high"};return"medium"}
    if ($Subsystem -eq "Hal") {if ($Name -match "Interrupt|SMBus|PCI|Firmware|Shutdown|Scratch|Tray"){return"high"};return"medium"}
    if ($Subsystem -eq "Ex") {return"medium"}
    if ($Subsystem -eq "Xe" -and $Name -match "LoadSection|UnloadSection") {return"high"}
    return"medium"
}
function Get-RetailRelevance([string]$Name,[string]$Subsystem) {
    if ($Name -like "MmDbg*" -or $Subsystem -in @("Dbg","Kd","XProfp","Irt")) {return"low"}
    if ($Subsystem -eq "Unknown") {return"unknown"}
    if ($Subsystem -in @("Ke","Kf","Ki","Mm","Nt","Io","Iof","Ob","Obp","Obf","Ps","Interlocked","Fsc","Hal","Xe")) {return"high"}
    return"medium"
}
function Get-Dependencies([string]$Name,[string]$Subsystem) {
    if ($Subsystem -in @("Ke","Kf","Ki")) {
        if ($Name -match "Timer|Time|Performance|Stall|Delay"){return"dispatcher;clock;timers"}
        if ($Name -match "Apc"){return"dispatcher;thread-state;APC"}
        if ($Name -match "Dpc"){return"dispatcher;DPC;IRQL"}
        if ($Name -match "Interrupt|Irql|Synchronize"){return"IRQL;interrupt-controller;dispatcher"}
        if ($Name -match "Wait|Event|Mutant|Semaphore|Queue|Thread"){return"dispatcher;thread-state;object-layout"}
        return"kernel-core"
    }
    $map=@{Mm="PTE/PFN;physical allocator;TLB;GPU-visible memory";Nt="object manager;I/O;VM;dispatcher adapters";Io="I/O manager;IRP;device objects";Iof="I/O manager;IRP;drivers";Ob="object manager;handle table;namespaces";Obf="object manager;reference counting";Obp="object manager;handle table";Ps="threads;object manager;scheduler";Hal="chipset;interrupts;SMBus/PCI";Ex="executive;pool;locks";Fsc="filesystem cache;storage";Rtl="runtime;strings;exceptions";Xc="crypto primitives";Xe="XBE sections;memory manager";Xbox="kernel globals;keys;hardware info";Interlocked="atomic primitives;CPU semantics";PortIO="x86 I/O-port semantics";Av="video initialization;NV2A/encoder";Phy="network PHY";Dbg="debugger-only";Kd="debugger state";XProfp="profiling-only";Irt="profiling-only";Unknown="unknown"}
    if ($map.ContainsKey($Subsystem)){return $map[$Subsystem]}
    return"misc"
}
function Get-PriorityScore($Row) {
    $score=@{high=5;medium=3;low=0;unknown=1}[$Row.retail_relevance]+@{high=2;medium=1;low=0;none=0}[$Row.complexity]
    if ($Row.test_state -in @("stub","disabled","unregistered")){$score+=4}
    if ($Row.roswell_state -in @("stub","missing-export")){$score+=4}
    if ($Row.roswell_state -eq "data-scaffold"){$score+=1}
    if ($Row.name -like "MmDbg*"){$score-=5}
    if ($Row.subsystem -in @("Dbg","Kd","XProfp","Irt")){$score-=3}
    if ($Row.subsystem -eq "Unknown"){$score-=2}
    return[Math]::Max(0,$score)
}
$apiNames=@{}
foreach($line in Get-Content (Join-Path $TestsPath "src/include/api_tests.h")){if($line -match 'GEN_API_TEST\(([^)]+)\).*?\((\d+)\)'){$apiNames[[int]$Matches[2]]=$Matches[1]}}
$hardware=@{}
if(Test-Path $HardwareResultsPath){foreach($file in Get-ChildItem $HardwareResultsPath -Filter "*.csv"|Sort-Object Name){foreach($row in Import-Csv $file.FullName){if($row.ordinal -match '^\d+$'){$hardware[[int]$row.ordinal]=$row}}}}
$rows=@()
foreach($base in Import-Csv $InventoryPath){
    $ordinal=[int]$base.ordinal
    $testName=if($apiNames.ContainsKey($ordinal)){$apiNames[$ordinal]}else{""}
    $testSources=@()
    $testState=if($ordinal -eq 0){"none"}elseif(-not $testName){"unregistered"}else{"substantive"}
    if($testName){
        $needle="TEST_FUNC($testName)"
        $testSources=@(Invoke-GitGrepPaths -Repo $TestsPath -Needle $needle -Prefix "src/tests/")
        $body=""
        foreach($source in $testSources){$body += [Environment]::NewLine + (Get-TestBody -Content (Get-Content (Join-Path $TestsPath $source) -Raw) -TestName $testName)}
        if($body -match 'FIXME:\s*This is a stub!'){$testState="stub"}elseif($body -match 'FIXME:\s*FATAL' -and $body -match '\breturn;'){$testState="disabled"}
    }
    $subsystem=Get-Subsystem $base.name $ordinal
    $complexity=Get-Complexity $base.name $subsystem $base.kind
    $relevance=Get-RetailRelevance $base.name $subsystem
    $cxbx=@()
    if($ordinal -gt 0){$cxbx=@(Invoke-GitGrepPaths -Repo $CxbxPath -Needle $base.name -Prefix "src/core/kernel/exports/");$cxbx=@($cxbx|Where-Object{$_ -match '\.(c|cc|cpp|S|s)$' -and $_ -notlike '*KernelThunk.cpp'})}
    $roswell=@()
    if($base.roswell_symbol){$roswell=@(Invoke-GitGrepPaths -Repo $RoswellPath -Needle $base.roswell_symbol);$roswell=@($roswell|Where-Object{$_ -match '\.(c|cc|cpp|S|s)$'}|Sort-Object{if($_ -like 'ntoskrnl/xb/*' -or $_ -like 'hal/halx86/xbox/*'){0}else{1}}, {$_}|Select-Object -Unique)}
    $hw=if($hardware.ContainsKey($ordinal)){$hardware[$ordinal]}else{$null}
    $hardwareStatus=if($hw){$hw.result}else{"not-ingested"}
    $evidence=if($base.roswell_state -in @("stub","missing-export")){"implementation-gap"}elseif($testState -eq "stub"){"behavior-test-stub"}elseif($testState -eq "disabled"){"behavior-test-disabled"}elseif($hw -and $hw.result -eq "pass"){"hardware-backed-pass"}elseif($hw){"hardware-result-ingested"}elseif($testState -eq "substantive"){"test-available-no-hardware-log"}else{"unverified"}
    $row=[ordered]@{ordinal=$ordinal;name=$base.name;subsystem=$subsystem;kind=$base.kind;stack_bytes=$base.stack_bytes;abi_style=$base.abi_style;roswell_state=$base.roswell_state;roswell_symbol=$base.roswell_symbol;roswell_source_candidates=($roswell -join ";");cxbx_source_candidates=($cxbx -join ";");test_name=$testName;test_registered=if($testName){"yes"}else{"no"};test_source=($testSources -join ";");test_state=$testState;hardware_status=$hardwareStatus;hardware_environment=if($hw){$hw.environment}else{""};hardware_source=if($hw){$hw.source_log}else{""};evidence_level=$evidence;complexity=$complexity;retail_relevance=$relevance;priority_score=0;dependencies=(Get-Dependencies $base.name $subsystem);notes=""}
    $row.priority_score=Get-PriorityScore $row
    $rows+=[pscustomobject]$row
}
$rows|Export-Csv $OutputPath -NoTypeInformation
$subStats=$rows|Group-Object subsystem|ForEach-Object{$g=$_.Group;[pscustomobject]@{subsystem=$_.Name;total=$g.Count;mapped=@($g|Where-Object roswell_state -eq "mapped").Count;roswell_gap=@($g|Where-Object{$_.roswell_state -in @("stub","missing-export")}).Count;substantive=@($g|Where-Object test_state -eq "substantive").Count;test_gap=@($g|Where-Object{$_.test_state -in @("stub","disabled","unregistered")}).Count}}
$top=$rows|Where-Object{$_.ordinal -gt 0 -and $_.retail_relevance -ne "low" -and ($_.test_state -ne "substantive" -or $_.roswell_state -in @("stub","missing-export"))}|Sort-Object @{Expression="priority_score";Descending=$true},ordinal|Select-Object -First 24
$md=@("# Kernel correlation status","","Generated locally from the revisions in .reference/.versions.tsv.","","## Test coverage","","| State | Count |","| --- | ---: |","| Substantive | $(@($rows|Where-Object test_state -eq 'substantive').Count) |","| Stub | $(@($rows|Where-Object test_state -eq 'stub').Count) |","| Disabled | $(@($rows|Where-Object test_state -eq 'disabled').Count) |","","## Subsystems","","| Subsystem | Slots | Roswell mapped | Roswell gaps | Substantive tests | Test gaps |","| --- | ---: | ---: | ---: | ---: | ---: |")
foreach($s in $subStats|Sort-Object subsystem){$md+="| $($s.subsystem) | $($s.total) | $($s.mapped) | $($s.roswell_gap) | $($s.substantive) | $($s.test_gap) |"}
$md+=@("","## Highest-priority unresolved rows","","| Ord | API | Roswell | Test | Score | Dependencies |","| ---: | --- | --- | --- | ---: | --- |")
foreach($r in $top){$md+="| $($r.ordinal) | $($r.name) | $($r.roswell_state) | $($r.test_state) | $($r.priority_score) | $($r.dependencies) |"}
$md|Set-Content $SummaryPath
Write-Host "Wrote $OutputPath"
Write-Host "Wrote $SummaryPath"
