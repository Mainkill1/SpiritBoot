$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$session = [Diagnostics.Process]::GetCurrentProcess().SessionId
if ([Environment]::UserName -ne 'runnerinteractiveuser' -or $session -eq 0) {
    throw ('Native launch requires runnerinteractiveuser interactive session: ' + $identity + ' session=' + $session)
}
$evidence = $env:PR248_NATIVE_EVIDENCE
if (!$evidence) { throw 'PR248_NATIVE_EVIDENCE must name this owned result directory' }
@{utc=[DateTime]::UtcNow.ToString('o');identity=$identity;session=$session;pid=$PID;
  powershell=$PSVersionTable.PSVersion.ToString();arguments=$args;
  xemuSha256=(Get-FileHash (Join-Path $PSScriptRoot 'xemu.exe')).Hash;
  userInteractive=[Environment]::UserInteractive} | ConvertTo-Json -Depth 10 |
  Set-Content (Join-Path $evidence 'native-user-launch.json')
& (Join-Path $PSScriptRoot 'xemu.exe') @args
exit $LASTEXITCODE
