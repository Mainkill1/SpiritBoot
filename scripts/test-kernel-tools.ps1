param(
    [string]$Fixture = "tests/host/kernel-test-log-sample.txt"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $Root
try {
    $temp = Join-Path ([IO.Path]::GetTempPath()) ("spiritboot-kernel-log-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $temp | Out-Null

    & ./scripts/import-kernel-test-log.ps1 -LogPath $Fixture -OutputDirectory $temp -Environment "Fixture Retail 1.6"

    $csv = Get-ChildItem $temp -Filter "*.csv" | Select-Object -First 1
    if (-not $csv) { throw "Importer produced no CSV" }

    $rows = @(Import-Csv $csv.FullName)
    if ($rows.Count -ne 3) { throw "Expected 3 rows, got $($rows.Count)" }

    $expected = @(
        @{ ordinal="1"; result="pass"; duration_seconds="0.001" },
        @{ ordinal="2"; result="fail"; duration_seconds="0.002" },
        @{ ordinal="3"; result="skipped"; duration_seconds="0.000" }
    )

    for ($i = 0; $i -lt $expected.Count; $i++) {
        foreach ($key in $expected[$i].Keys) {
            if ($rows[$i].$key -ne $expected[$i][$key]) {
                throw "Row $i field $key: expected '$($expected[$i][$key])', got '$($rows[$i].$key)'"
            }
        }
    }

    if ($rows[0].environment -ne "Fixture Retail 1.6") { throw "Environment not preserved" }
    if ($rows[0].test_revision -ne "fixture-deadbeef") { throw "Build ID not preserved" }
    if ($rows[0].source_log -ne "kernel-test-log-sample.txt") { throw "Source filename not normalized" }
    if ($rows[0].source_sha256 -notmatch '^[0-9a-f]{64}$') { throw "Source SHA256 missing/invalid" }

    Write-Host "Kernel log importer self-test PASSED"
}
finally {
    if ($temp -and (Test-Path $temp)) { Remove-Item -Recurse -Force $temp }
    Pop-Location
}
