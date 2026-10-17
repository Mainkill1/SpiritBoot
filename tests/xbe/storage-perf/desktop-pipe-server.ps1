# SPDX-License-Identifier: GPL-2.0-or-later
# Compiled into the owned launcher as ordinary inline PowerShell commands.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$session = [Diagnostics.Process]::GetCurrentProcess().SessionId
if ($session -eq 0 -or ![Environment]::UserInteractive -or [Environment]::UserName -ne 'Codex' -or
    $env:PR248_NATIVE_WINDOW_STATION -ne 'WinSta0' -or $env:PR248_NATIVE_DESKTOP -ne 'Default') {
    throw 'Desktop pipe server requires the approved live Codex USER desktop'
}
$security = [IO.Pipes.PipeSecurity]::new()
$security.SetAccessRuleProtection($true, $false)
$security.SetAccessRule([IO.Pipes.PipeAccessRule]::new($identity.User,
    [IO.Pipes.PipeAccessRights]::FullControl, [Security.AccessControl.AccessControlType]::Allow))
$pipe = [IO.Pipes.NamedPipeServerStream]::new($env:PR248_NATIVE_PIPE_NAME,
    [IO.Pipes.PipeDirection]::InOut, 1, [IO.Pipes.PipeTransmissionMode]::Byte,
    [IO.Pipes.PipeOptions]::Asynchronous, 4096, 4096, $security)
$child = $null
$childStarted = $false
try {
    $connected = $pipe.BeginWaitForConnection($null, $null)
    if (!$connected.AsyncWaitHandle.WaitOne(15000)) { throw 'Owned pipe client connection timeout' }
    $pipe.EndWaitForConnection($connected)
    $reader = [IO.StreamReader]::new($pipe, [Text.UTF8Encoding]::new($false), $false, 4096, $true)
    $writer = [IO.StreamWriter]::new($pipe, [Text.UTF8Encoding]::new($false), 4096, $true)
    $writer.AutoFlush = $true
    $writer.WriteLine(('READY|'+$identity.Name+'|'+$session+'|'+$PID+'|WinSta0|Default'))
    $read = $reader.ReadLineAsync()
    if (!$read.Wait(10000)) { throw 'Owned pipe request timeout' }
    $request = $read.Result
    if ($request -ne ('PROVE|'+$env:PR248_NATIVE_PIPE_NONCE) -and
        $request -ne ('RUN|'+$env:PR248_NATIVE_PIPE_NONCE)) { throw 'Unexpected owned pipe request' }
    $operation = $request.Split('|')[0]
    [IO.File]::WriteAllLines([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE, 'native-pipe-server.txt'),
        [string[]]@(('utc='+[DateTime]::UtcNow.ToString('o')),('identity='+$identity.Name),
        ('session='+$session),('server_pid='+$PID),('owner_sid='+$identity.User.Value),
        ('acl_sddl='+$pipe.GetAccessControl().GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::Access)),
        ('pipe_name='+$env:PR248_NATIVE_PIPE_NAME),'window_station=WinSta0','desktop=Default',
        ('operation='+$operation),'launch_transport=named-pipe'))
    if ($operation -eq 'PROVE') { $writer.WriteLine('DONE|0|0'); exit 0 }
    # Read-only host storage/thermal metadata, outside all guest timing windows.
    $controls = [Collections.Generic.List[string]]::new()
    $controls.Add('utc='+[DateTime]::UtcNow.ToString('o'))
    $controls.Add('identity='+$identity.Name)
    $controls.Add('session='+$session)
    $controls.Add('settings_changed=False')
    try {
        [void][Reflection.Assembly]::LoadWithPartialName('System.Management')
        foreach ($query in @('SELECT Model,InterfaceType,Size,BytesPerSector,FirmwareRevision,DeviceID FROM Win32_DiskDrive',
            'SELECT Antecedent,Dependent FROM Win32_LogicalDiskToPartition',
            'SELECT Antecedent,Dependent FROM Win32_DiskDriveToDiskPartition')) {
            $search = [System.Management.ManagementObjectSearcher]::new($query)
            $search.Options.Timeout = [TimeSpan]::FromSeconds(3)
            $items = $search.Get()
            $controls.Add('query='+$query)
            foreach ($item in $items) {
                foreach ($property in $item.Properties) { $controls.Add($property.Name+'='+[string]$property.Value) }
                $controls.Add('record_end=True')
            }
            $items.Dispose(); $search.Dispose()
        }
    } catch { $controls.Add('storage_query_error='+$_.Exception.Message) }
    try {
        $thermal = [System.Management.ManagementObjectSearcher]::new('root\WMI','SELECT InstanceName,CurrentTemperature FROM MSAcpi_ThermalZoneTemperature')
        $thermal.Options.Timeout = [TimeSpan]::FromSeconds(3)
        $zones=$thermal.Get(); $controls.Add('thermal_zones='+$zones.Count)
        foreach($zone in $zones){$controls.Add('thermal_instance='+$zone.InstanceName);$controls.Add('thermal_tenths_kelvin='+$zone.CurrentTemperature)}
        $zones.Dispose();$thermal.Dispose()
    } catch { $controls.Add('thermal_query_error='+$_.Exception.Message) }
    [IO.File]::WriteAllLines([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE,'native-host-controls.txt'),$controls)
    # No command, executable or path is accepted from the pipe. It authorizes the
    # single immutable guest command already provided by this owned runner job.
    $child = [Diagnostics.Process]::new()
    $child.StartInfo.FileName = [IO.Path]::Combine($env:PR248_NATIVE_PACKAGE, 'xemu.exe')
    $child.StartInfo.Arguments = $env:PR248_NATIVE_ARGUMENT_LINE
    $child.StartInfo.WorkingDirectory = $env:PR248_NATIVE_PACKAGE
    $child.StartInfo.UseShellExecute = $false
    $child.StartInfo.RedirectStandardOutput = $true
    $child.StartInfo.RedirectStandardError = $true
    if (!$child.Start()) { throw 'Owned graphical xemu did not start' }
    $childStarted = $true
    if ($child.SessionId -ne $session) { throw 'Owned child is outside the desktop server session' }
    [IO.File]::WriteAllLines([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE,'native-user-launch.txt'),
        [string[]]@(('utc='+[DateTime]::UtcNow.ToString('o')),('identity='+$identity.Name),
        ('session='+$session),('server_pid='+$PID),('xemu_pid='+$child.Id),('xemu_session='+$child.SessionId),
        ('powershell='+$PSVersionTable.PSVersion.ToString()),('userInteractive='+[Environment]::UserInteractive),
        ('arguments='+$env:PR248_NATIVE_ARGUMENT_LINE),'launch_transport=named-pipe',
        ('pipe_name='+$env:PR248_NATIVE_PIPE_NAME),'window_station=WinSta0','desktop=Default'))
    $stdout = $child.StandardOutput.ReadToEndAsync()
    $stderr = $child.StandardError.ReadToEndAsync()
    if (!$child.WaitForExit(120000)) { throw 'Owned graphical child deadline exceeded' }
    if (!$stdout.Wait(3000) -or !$stderr.Wait(3000)) { throw 'Owned child output drain timeout' }
    [IO.File]::WriteAllText([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE,'native-child-stdout.log'),$stdout.Result)
    [IO.File]::WriteAllText([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE,'native-child-stderr.log'),$stderr.Result)
    $writer.WriteLine(('DONE|'+$child.ExitCode+'|'+$child.Id))
    exit $child.ExitCode
} finally {
    # The exact Process object retains ownership; no process-name/PID sweep.
    $cleanup = [Collections.Generic.List[string]]::new()
    $cleanup.Add('version=2'); $cleanup.Add('server_pid='+$PID)
    $cleanup.Add('child_started='+$childStarted)
    if ($childStarted) {
        $cleanup.Add('child_pid='+$child.Id)
        try {
            if (!$child.HasExited) { $child.Kill(); $cleanup.Add('owned_child_kill_requested=True') }
            $stopped = $child.WaitForExit(5000)
            $cleanup.Add('owned_child_exit_confirmed='+$stopped)
        } catch { $cleanup.Add('owned_child_cleanup_error='+$_.Exception.Message) }
        $child.Dispose()
    }
    try { [IO.File]::WriteAllLines([IO.Path]::Combine($env:PR248_NATIVE_EVIDENCE,'native-pipe-server-lifetime.txt'),$cleanup) } catch {}
    $pipe.Dispose()
}
