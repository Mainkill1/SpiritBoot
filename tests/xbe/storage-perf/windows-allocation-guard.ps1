# SPDX-License-Identifier: GPL-2.0-only
# Diagnostic only. Requires hash-loaded previously reviewed guard functions.
function Invoke-Pr248AllocationGuard($Parameters) {
    $ErrorActionPreference='Stop'
    $package=[IO.Path]::GetFullPath($Parameters['package']);$result=[IO.Path]::GetFullPath($Parameters['result'])
    $stage=$Parameters['stage'];$path=[IO.Path]::Combine($result,('allocation-'+$stage+'-guard.json'))
    $record=@{status='INCONCLUSIVE';error=$null;mode='DIAGNOSTIC_ONLY';performance_acceptance_eligible=$false;
        physical_peak_eligible=$false;observer_pid=$PID;started_utc=[DateTimeOffset]::UtcNow.ToString('o')}
    function Save-Pr248AllocationGuard { [IO.File]::WriteAllText($path,($record|ConvertTo-Json -Depth 40),[Text.UTF8Encoding]::new($false)) }
    Save-Pr248AllocationGuard
    try {
        Assert-Pr248 ($stage -cin @('before-gdb','capture')) 'Unknown diagnostic guard stage'
        Assert-Pr248 ($PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1) 'Requires actual Windows PowerShell5.1'
        $desktop=Get-Pr248DesktopContext;$record['desktop']=$desktop
        Assert-Pr248 ($desktop['user_name'] -ieq 'codex' -and $desktop['user_interactive'] -and $desktop['session'] -eq 1) 'Owned USER desktop unavailable'
        Assert-Pr248 ($package -ceq $Parameters['expected_package']) 'Actual package differs'
        $launch=Read-Pr248Json ([IO.Path]::Combine($result,'launch.json'))
        $manifest=Read-Pr248Json ([IO.Path]::Combine($result,'input-manifest.json'))
        $report=Read-Pr248Json ([IO.Path]::Combine($result,'diagnostics/run-state/report.json'))
        Assert-Pr248 ($launch['job'] -ceq $Parameters['expected_job'] -and $manifest['JobId'] -ceq $Parameters['expected_job'] -and
            $launch['runId'] -ceq [IO.Path]::GetFileName($result) -and $manifest['PackageDirectory'] -ceq $package -and
            $launch['startPaused'] -is [bool] -and $launch['startPaused']) 'Owned paused job/run differs'
        foreach($pair in @(@('xemu.exe','expected_xemu_sha256'),@('native-launch.exe','expected_launcher_sha256'),
            @('storage-perf.iso','expected_iso_sha256'),@('flash.bin','expected_flash_sha256'),@('xemu.toml','expected_config_sha256'))) {
            $rows=@($manifest['Inputs']|Where-Object {$_['Path'] -ceq $pair[0]})
            Assert-Pr248 ($rows.Count -eq 1 -and $rows[0]['Verified'] -is [bool] -and $rows[0]['Verified'] -and
                $rows[0]['Sha256'] -ceq $Parameters[$pair[1]] -and $rows[0]['ExpectedSha256'] -ceq $Parameters[$pair[1]]) 'Actual pinned input differs'
            $input=@{};[void](Get-Pr248PinnedInput $package $pair[0] $Parameters[$pair[1]] $input);$record[$pair[0]]=$input
        }
        $effective=[IO.Path]::GetFullPath([IO.Path]::Combine($result,'diagnostics','run-state','effective-live.toml'))
        Assert-Pr248 ($report['Status'] -cin @('prepared','complete') -and $report['ConfigSha256'] -ceq $Parameters['expected_config_sha256'] -and
            [IO.Path]::GetFullPath($report['EffectiveConfigPath']) -ceq $effective -and
            (Get-Pr248Hash $effective) -ceq $report['EffectiveConfigSha256']) 'Actual effective config differs'
        $fields=@{};foreach($name in @('native-user-launch.txt','native-pipe-server.txt','native-pipe-client.txt')) {
            $fields[$name]=Read-Pr248Fields ([IO.Path]::Combine($result,$name))
        }
        $guest=$fields['native-user-launch.txt'];$server=$fields['native-pipe-server.txt'];$client=$fields['native-pipe-client.txt']
        foreach($row in @($guest,$server,$client)) {
            Assert-Pr248 ($row['identity'] -ceq $desktop['identity'] -and $row['session'] -ceq '1' -and $row['window_station'] -ceq 'WinSta0' -and
                $row['desktop'] -ceq 'Default' -and $row['pipe_name'] -ceq $guest['pipe_name'] -and $row['server_pid'] -ceq $guest['server_pid']) 'Protected pipe context differs'
        }
        Assert-Pr248 ($guest['launch_transport'] -ceq 'named-pipe' -and $guest['xemu_session'] -ceq '1' -and
            $client['handshake_verified'] -ceq 'True' -and $client['operation'] -ceq 'RUN' -and $server['operation'] -ceq 'RUN' -and
            $server['owner_sid'] -ceq $desktop['owner_sid'] -and $server['acl_sddl'] -ceq ('D:P(A;;0x1f019f;;;'+$desktop['owner_sid']+')')) 'Protected pipe ACL/handshake differs'
        $snapshots=@{wrapper=Get-Pr248ProcessSnapshot ([int]$Parameters['wrapper_pid']);client=Get-Pr248ProcessSnapshot ([int]$client['client_pid']);
            server=Get-Pr248ProcessSnapshot ([int]$guest['server_pid']);guest=Get-Pr248ProcessSnapshot ([int]$guest['xemu_pid'])}
        foreach($snapshot in $snapshots.Values){Assert-Pr248 ($snapshot['owner_sid'] -ceq $desktop['owner_sid'] -and $snapshot['session'] -eq 1) 'Actual process desktop differs'}
        foreach($pair in @(@('client','wrapper'),@('server','client'),@('guest','server'))) {
            Assert-Pr248 ($snapshots[$pair[0]]['parent_pid'] -eq $snapshots[$pair[1]]['pid'] -and
                $snapshots[$pair[0]]['start_ticks'] -ge $snapshots[$pair[1]]['start_ticks']) 'Actual process ancestry differs'
        }
        $exe=[IO.Path]::Combine($package,'xemu.exe');$wrapper=[IO.Path]::Combine($package,'native-launch.exe')
        Assert-Pr248 ($snapshots['wrapper']['exe_path'] -ceq $wrapper -and (Get-Pr248Hash $wrapper) -ceq $Parameters['expected_launcher_sha256'] -and
            $manifest['ExecutableSha256'] -ceq $Parameters['expected_launcher_sha256'] -and $snapshots['guest']['exe_path'] -ceq $exe) 'Actual executable differs'
        $arguments=[Collections.Generic.List[string]]::new();$configs=[Collections.Generic.List[string]]::new()
        for($i=0;$i -lt $launch['arguments'].Count;$i++) {
            $word=$launch['arguments'][$i];if($word -ceq '-config_path'){$i++;$configs.Add($launch['arguments'][$i])}
            elseif($word.StartsWith('-config_path=')){$configs.Add($word.Substring(13))}else{$arguments.Add($word)}
        }
        Assert-Pr248 ($configs.Count -eq 1 -and [IO.Path]::GetFullPath($configs[0]) -ceq [IO.Path]::Combine($package,'xemu.toml')) 'Source config argv differs'
        $arguments.Add('-config_path');$arguments.Add($effective)
        Assert-Pr248 (@($arguments|Where-Object {$_ -match '[\s"]'}).Count -eq 0) 'Ambiguous diagnostic argv'
        $line=$arguments -join ' '
        Assert-Pr248 (@($arguments|Where-Object {$_ -ceq '-S'}).Count -eq 1 -and
            @($arguments|Where-Object {$_ -match '^-(gdb|monitor|icount|replay)(=|$)'}).Count -eq 0) 'Undeclared bootstrap/control override'
        Assert-Pr248 ($guest['arguments'] -ceq $line -and $snapshots['guest']['command_line'] -cin @(($exe+' '+$line),('"'+$exe+'" '+$line))) 'Actual xemu argv differs'
        $ports=@([regex]::Matches($line,'(?:^| )-qmp tcp:127\.0\.0\.1:(\d+),server=on,wait=off(?: |$)'))
        Assert-Pr248 ($ports.Count -eq 1) 'Actual managed QMP endpoint differs';$qmpPort=[int]$ports[0].Groups[1].Value
        $listeners=@(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $qmpPort -State Listen -ErrorAction Stop|
            ForEach-Object {@{pid=[int]$_.OwningProcess;address=$_.LocalAddress;port=[int]$_.LocalPort;state=[string]$_.State}})
        Test-Pr248Listener $listeners $snapshots['guest']['pid'] $qmpPort
        $query=Read-Pr248Recipe $result ('allocation-qmp-'+$stage+'-status') 'query-status' @{}
        Assert-Pr248 ($query['response']['running'] -is [bool] -and !$query['response']['running'] -and
            $query['response']['status'] -cin @('paused','prelaunch')) 'Actual managed sample is not stopped before attachment'
        $record['processes']=$snapshots;$record['pipe_fields']=$fields;$record['managed_status']=$query;$record['qmp_listener']=$listeners
        $gdbPort=[int]$Parameters['gdb_port']
        $gdb=@(Get-NetTCPConnection -State Listen -ErrorAction Stop|Where-Object {$_.LocalPort -eq $gdbPort}|
            ForEach-Object {@{pid=[int]$_.OwningProcess;address=$_.LocalAddress;port=[int]$_.LocalPort;state=[string]$_.State}})
        if($stage -ceq 'before-gdb') {
            Assert-Pr248 ($gdb.Count -eq 0) 'Declared GDB port is already occupied'
        } else {
            $prior=Read-Pr248Json ([IO.Path]::Combine($result,'allocation-before-gdb-guard.json'))
            Assert-Pr248 ($prior['status'] -ceq 'owned_paused_route_verified') 'Earlier ownership/absence guard missing'
            foreach($field in @('pid','parent_pid','owner_sid','session','exe_path','command_line','start_ticks')) {
                Assert-Pr248 ($snapshots['guest'][$field] -ceq $prior['processes']['guest'][$field]) 'Actual guest lifetime changed before attachment'
            }
            $open=Read-Pr248Recipe $result 'allocation-qmp-gdb-open' 'human-monitor-command' @{ 'command-line'=('gdbserver tcp:127.0.0.1:'+$gdbPort) }
            Test-Pr248Listener $gdb $snapshots['guest']['pid'] $gdbPort;$record['gdb_listener']=$gdb;$record['gdb_open_recipe']=$open
        }
        $record['status']='owned_paused_route_verified';$record['gdb_port']=$gdbPort
        $record['owned_xemu_pid']=$snapshots['guest']['pid'];$record['kernel_sha256']=$Parameters['kernel_sha256']
        $record['selected_case']='small-hdd-read.cold-ish';$record['finished_utc']=[DateTimeOffset]::UtcNow.ToString('o');Save-Pr248AllocationGuard
        if($stage -ceq 'capture') {
            # Root must resolve this actual interpreter through supported HTTP
            # readiness before freezing a dispatchable request. Never guess PATH.
            Assert-Pr248 ($Parameters['python_executable'] -is [string] -and [IO.Path]::IsPathRooted($Parameters['python_executable']) -and
                [IO.File]::Exists($Parameters['python_executable'])) 'Actual Windows Python prerequisite is unresolved'
            foreach($name in $Parameters['source_pins'].Keys) {
                Assert-Pr248 ((Get-Pr248Hash ([IO.Path]::Combine($package,$name))) -ceq $Parameters['source_pins'][$name]) 'Actual collector source/binding differs'
            }
            $record['python_executable']=$Parameters['python_executable'];$record['python_sha256']=Get-Pr248Hash $Parameters['python_executable'];Save-Pr248AllocationGuard
            & $Parameters['python_executable'] ([IO.Path]::Combine($package,'capture_owned_fixture.py')) --execute-diagnostic `
                --binding ([IO.Path]::Combine($package,'selected-binding.json')) --fixture ([IO.Path]::Combine($package,'fixture-binding.json')) `
                --context $path --transport ([IO.Path]::Combine($package,'rsp_transport.py')) --port $gdbPort --seconds 60 `
                --out ([IO.Path]::Combine($result,'allocation-trace'))
            Assert-Pr248 ($LASTEXITCODE -eq 0) 'Diagnostic capture failed/partial; inspect retained raw artifacts'
            $record['capture_exit_code']=$LASTEXITCODE;Save-Pr248AllocationGuard
        }
    } catch {$record['status']='INCONCLUSIVE';$record['error']=$_.Exception.Message;Save-Pr248AllocationGuard;throw}
}
