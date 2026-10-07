param(
    [string]$RoswellPath = (Join-Path (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)) ".reference/roswell"),
    [string]$CxbxPath = (Join-Path (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)) ".reference/cxbx-reloaded"),
    [string]$OutputPath = (Join-Path (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)) "research/kernel/exports.csv")
)

$ErrorActionPreference = "Stop"
$DefPath = Join-Path $RoswellPath "ntoskrnl/xb/xboxkrnl.exe.def"
$MapPath = Join-Path $RoswellPath "ntoskrnl/xb/ordinals.map"
$ThunkPath = Join-Path $CxbxPath "src/core/kernel/exports/KernelThunk.cpp"

foreach ($path in @($DefPath, $MapPath, $ThunkPath)) {
    if (-not (Test-Path $path)) { throw "Missing $path. Run scripts/fetch-references.ps1 first." }
}

$cxbx = @{}
foreach ($raw in Get-Content $ThunkPath) {
    if ($raw -notmatch "//\s*0x[0-9A-Fa-f]+\s+\((\d+)") { continue }
    $ordinal = [int]$Matches[1]
    $name = ""
    if ($raw -match "KRNL\(([^)]+)\)") { $name = $Matches[1] }
    elseif ($raw -match "(?:&)?xbox::([A-Za-z_][A-Za-z0-9_]*)") { $name = $Matches[1] }
    if ($ordinal -eq 0) { $name = "Undefined" }
    $kind = if ($ordinal -eq 0) { "reserved" } elseif ($raw -match "\bVARIABLE\(") { "data" } else { "function" }
    $cxbx[$ordinal] = @{ Name = $name; Kind = $kind }
}

$def = @{}
foreach ($raw in Get-Content $DefPath) {
    $line = $raw.Trim()
    if (-not $line -or $line.StartsWith(";") -or $line -eq "EXPORTS" -or $line.StartsWith("LIBRARY")) { continue }
    if ($line -notmatch "\s@\s*(\d+)\s+NONAME") { continue }

    $ordinal = [int]$Matches[1]
    $matchText = $Matches[0]
    $left = $line.Substring(0, $line.IndexOf($matchText)).Trim()
    $isData = $line -match "\sDATA\s*$"
    $abiStyle = if ($isData) { "data" } elseif ($left.StartsWith("@")) { "fastcall" } else { "function" }
    $name = $left.TrimStart("@")
    $stack = ""
    if (-not $isData -and $name -match "^([A-Za-z0-9_]+)(?:@(\d+))?$") {
        $name = $Matches[1]
        $stack = $Matches[2]
    } else {
        $name = $name -replace "@\d+$", ""
    }
    $def[$ordinal] = @{ Name = $name; Kind = if ($isData) { "data" } else { "function" }; Stack = $stack; Abi = $abiStyle }
}

$map = @{}
foreach ($raw in Get-Content $MapPath) {
    $line = ($raw -split "#", 2)[0].Trim()
    if (-not $line -or $line -notmatch "^(\d+)(?:\s+(.*))?$") { continue }

    $ordinal = [int]$Matches[1]
    $rest = if ($Matches.ContainsKey(2) -and $null -ne $Matches[2]) { $Matches[2].Trim() } else { "" }
    if (-not $rest) {
        $map[$ordinal] = @{ State = "stub"; Symbol = "" }
    } elseif ($rest.StartsWith("=")) {
        $map[$ordinal] = @{ State = "data-scaffold"; Symbol = $rest }
    } else {
        $parts = $rest -split "\s+"
        $map[$ordinal] = @{ State = "mapped"; Symbol = if ($parts.Count -gt 1) { $parts[-1] } else { $parts[0] } }
    }
}

$rows = foreach ($ordinal in 0..378) {
    $cx = if ($cxbx.ContainsKey($ordinal)) { $cxbx[$ordinal] } else { @{ Name = "Ordinal$ordinal"; Kind = "unknown" } }
    $di = if ($def.ContainsKey($ordinal)) { $def[$ordinal] } else { $null }
    $mi = if ($map.ContainsKey($ordinal)) { $map[$ordinal] } else { $null }

    $state = if ($ordinal -eq 0) { "reserved" }
             elseif (-not $di) { "missing-export" }
             elseif (-not $mi -or $mi.State -eq "stub") { "stub" }
             else { $mi.State }

    [pscustomobject]@{
        ordinal = $ordinal
        name = if ($di) { $di.Name } else { $cx.Name }
        kind = if ($di) { $di.Kind } else { $cx.Kind }
        stack_bytes = if ($di) { $di.Stack } else { "" }
        abi_style = if ($di) { $di.Abi } elseif ($ordinal -eq 0) { "reserved" } else { "unknown" }
        roswell_state = $state
        roswell_symbol = if ($mi) { $mi.Symbol } else { "" }
        hardware_test = "unknown"
        hardware_status = "unknown"
        cxbx_reference = if ($cxbx.ContainsKey($ordinal)) { "yes" } else { "unknown" }
        confidence = "unknown"
        complexity = "unknown"
        notes = ""
    }
}

$rows | Export-Csv -Path $OutputPath -NoTypeInformation
Write-Host "Wrote $OutputPath"
