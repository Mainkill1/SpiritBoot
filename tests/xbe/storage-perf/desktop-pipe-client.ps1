# SPDX-License-Identifier: GPL-2.0-or-later
# This client starts a per-job USER desktop server; it never invokes a service.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$session = [Diagnostics.Process]::GetCurrentProcess().SessionId
if ($session -eq 0 -or ![Environment]::UserInteractive -or [Environment]::UserName -ne 'Codex') {
    throw 'Owned pipe client requires the live Codex USER desktop'
}
try {
    $existing = [IO.Directory]::GetFiles('\\.\pipe\') | Where-Object { $_ -match 'desktop|powershell|pshost|xemu|codex' }
    [IO.File]::WriteAllLines([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE,'existing-desktop-pipes.txt'), [string[]]$existing)
} catch {
    [IO.File]::WriteAllText([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE,'existing-desktop-pipes.txt'), 'read-only enumeration unavailable: '+$_.Exception.Message)
}
$env:PR248_NATIVE_PIPE_NAME = 'pr248-owned-'+$PID+'-'+[Guid]::NewGuid().ToString('N')
$env:PR248_NATIVE_PIPE_NONCE = [Guid]::NewGuid().ToString('N')
$server = [Diagnostics.Process]::new()
$server.StartInfo.FileName = [IO.Path]::Combine($env:SystemRoot,'System32\WindowsPowerShell\v1.0\powershell.exe')
$server.StartInfo.Arguments = '-NoProfile -NonInteractive -EncodedCommand '+$env:PR248_NATIVE_SERVER_COMMAND
$server.StartInfo.WorkingDirectory = $env:PR248_NATIVE_PACKAGE
$server.StartInfo.UseShellExecute = $false
$server.StartInfo.RedirectStandardOutput = $true
$server.StartInfo.RedirectStandardError = $true
$serverStarted = $false
$pipe = $null
$serverOut = $null
$serverErr = $null
try {
if (!$server.Start()) { throw 'Owned desktop pipe server did not start' }
$serverStarted = $true
$serverOut = $server.StandardOutput.ReadToEndAsync()
$serverErr = $server.StandardError.ReadToEndAsync()
$pipe = [IO.Pipes.NamedPipeClientStream]::new('.', $env:PR248_NATIVE_PIPE_NAME,
    [IO.Pipes.PipeDirection]::InOut, [IO.Pipes.PipeOptions]::Asynchronous)
    $pipe.Connect(15000)
    $reader = [IO.StreamReader]::new($pipe,[Text.UTF8Encoding]::new($false),$false,4096,$true)
    $writer = [IO.StreamWriter]::new($pipe,[Text.UTF8Encoding]::new($false),4096,$true)
    $writer.AutoFlush = $true
    $ready = $reader.ReadLineAsync()
    if (!$ready.Wait(10000)) { throw 'Desktop pipe handshake timeout' }
    $parts = $ready.Result.Split('|')
    if ($parts.Count -ne 6 -or $parts[0] -ne 'READY' -or $parts[1] -ne $identity -or
        [int]$parts[2] -ne $session -or [int]$parts[3] -ne $server.Id -or
        $parts[4] -ne 'WinSta0' -or $parts[5] -ne 'Default') { throw 'Desktop pipe handshake identity mismatch' }
    $operation = if ($env:PR248_NATIVE_PIPE_PROOF_ONLY -eq '1') { 'PROVE' } else { 'RUN' }
    [IO.File]::WriteAllLines([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE,'native-pipe-client.txt'),
        [string[]]@(('utc='+[DateTime]::UtcNow.ToString('o')),('identity='+$identity),('session='+$session),
        ('client_pid='+$PID),('server_pid='+$server.Id),('pipe_name='+$env:PR248_NATIVE_PIPE_NAME),
        'window_station=WinSta0','desktop=Default','handshake_verified=True',('operation='+$operation)))
    $writer.WriteLine(($operation+'|'+$env:PR248_NATIVE_PIPE_NONCE))
    $done = $reader.ReadLineAsync()
    if (!$done.Wait(145000)) { throw 'Owned graphical guest completion timeout' }
    # EOF can arrive from the server's finally block before PowerShell writes
    # its terminating error. Preserve that exact error before interpreting DONE
    # or entering cleanup, which would otherwise kill the unwinding server.
    if (!$server.WaitForExit(5000)) { throw 'Owned pipe server exit timeout' }
    if (!$serverOut.Wait(3000) -or !$serverErr.Wait(3000)) { throw 'Owned server output drain timeout' }
    [IO.File]::WriteAllText([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE,'native-pipe-server-stdout.log'),$serverOut.Result)
    [IO.File]::WriteAllText([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE,'native-pipe-server-stderr.log'),$serverErr.Result)
    if ($null -eq $done.Result) { throw 'Owned desktop pipe server ended without DONE; see preserved server error' }
    $status = $done.Result.Split('|')
    if ($status.Count -ne 3 -or $status[0] -ne 'DONE') { throw 'Unexpected desktop pipe completion' }
    if ([int]$status[1] -ne $server.ExitCode) { throw 'Pipe/server completion mismatch' }
    exit $server.ExitCode
} finally {
    if ($null -ne $pipe) { $pipe.Dispose() }
    $cleanup = [Collections.Generic.List[string]]::new()
    $cleanup.Add('version=2'); $cleanup.Add('client_pid='+$PID)
    $cleanup.Add('server_started='+$serverStarted)
    if ($serverStarted) {
        $cleanup.Add('server_pid='+$server.Id)
        try {
            if (!$server.HasExited) { $server.Kill(); $cleanup.Add('owned_server_kill_requested=True') }
            $stopped = $server.WaitForExit(5000)
            $cleanup.Add('owned_server_exit_confirmed='+$stopped)
        } catch { $cleanup.Add('owned_server_cleanup_error='+$_.Exception.Message) }
        # The wrapper's anonymous job also owns the child if a forcibly stopped
        # server could not run its finally block. Parent exit is not proof alone.
        foreach ($output in @(@('native-pipe-server-stdout.log',$serverOut),@('native-pipe-server-stderr.log',$serverErr))) {
            try { if ($null -ne $output[1] -and $output[1].Wait(3000)) { [IO.File]::WriteAllText([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE,$output[0]),$output[1].Result) } } catch {}
        }
        $server.Dispose()
    }
    try { [IO.File]::WriteAllLines([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE,'native-pipe-client-lifetime.txt'),$cleanup) } catch {}
}
