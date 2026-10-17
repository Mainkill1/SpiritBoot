# SPDX-License-Identifier: GPL-2.0-or-later
# Diagnostic context only. Reuses the hash-loaded committed Windows guard helpers.
function Test-Pr248ClockSample($Sample) {
    foreach($flag in @('qpf_success','qpc_before_success','qpc_after_success')) {
        Assert-Pr248 ($Sample.ContainsKey($flag) -and $Sample[$flag] -is [bool] -and $Sample[$flag]) 'Windows clock API failure/missing outcome'
    }
    $numbers=@{}
    foreach($name in @('qpf_frequency_dec','qpc_before_dec','qpc_after_dec')) {
        Assert-Pr248 ($Sample[$name] -is [string] -and $Sample[$name] -cmatch '^[0-9]+$') 'Missing exact clock integer'
        $numbers[$name]=[long]::Parse($Sample[$name],[Globalization.CultureInfo]::InvariantCulture)
        Assert-Pr248 ($numbers[$name] -gt 0) 'Clock integer is not positive'
    }
    Assert-Pr248 ($numbers['qpc_after_dec'] -ge $numbers['qpc_before_dec']) 'Observed host QPC rollback'
    $begin=[DateTimeOffset]::Parse($Sample['utc_begin']);$end=[DateTimeOffset]::Parse($Sample['utc_end'])
    Assert-Pr248 ($begin.Offset -eq [TimeSpan]::Zero -and $end.Offset -eq [TimeSpan]::Zero -and $end -ge $begin) 'Clock sample timestamp rollback/non-UTC'
    $frequency=$numbers['qpf_frequency_dec'];$scale='0'
    if(([long]1000000000 % $frequency) -eq 0) {
        $scale=([long]([decimal]1000000000/[decimal]$frequency)).ToString([Globalization.CultureInfo]::InvariantCulture)
    }
    return @{frequency_dec=$Sample['qpf_frequency_dec'];count_quantum_seconds=@{numerator=1;denominator_dec=$Sample['qpf_frequency_dec']};
        compiled_route_supported=($frequency -le [uint32]::MaxValue);constructor_derived_ns_per_tick_dec=$scale;
        actual_xemu_internal_scale_observed=$false;provider_precision_proved=$false;performance_acceptance_eligible=$false}
}

function Read-Pr248WindowsClockSample {
    if(!$script:Pr248ClockApiReady) {
        Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public static class Pr248ClockContextApi {
 [DllImport("kernel32.dll", ExactSpelling=true)]
 [return: MarshalAs(UnmanagedType.Bool)] public static extern bool QueryPerformanceFrequency(out long frequency);
 [DllImport("kernel32.dll", ExactSpelling=true)]
 [return: MarshalAs(UnmanagedType.Bool)] public static extern bool QueryPerformanceCounter(out long counter);
}
'@ -ErrorAction Stop
        $script:Pr248ClockApiReady=$true
    }
    [long]$frequency=0;[long]$before=0;[long]$after=0
    $sample=@{utc_begin=[DateTimeOffset]::UtcNow.ToString('o')}
    $sample['qpc_before_success']=[Pr248ClockContextApi]::QueryPerformanceCounter([ref]$before)
    $sample['qpf_success']=[Pr248ClockContextApi]::QueryPerformanceFrequency([ref]$frequency)
    $sample['qpc_after_success']=[Pr248ClockContextApi]::QueryPerformanceCounter([ref]$after)
    $sample['qpf_frequency_dec']=$frequency.ToString([Globalization.CultureInfo]::InvariantCulture)
    $sample['qpc_before_dec']=$before.ToString([Globalization.CultureInfo]::InvariantCulture)
    $sample['qpc_after_dec']=$after.ToString([Globalization.CultureInfo]::InvariantCulture)
    $sample['utc_end']=[DateTimeOffset]::UtcNow.ToString('o')
    return $sample
}

function Invoke-Pr248WindowsClockContext($Parameters) {
    $result=[IO.Path]::GetFullPath($Parameters['result']);$package=[IO.Path]::GetFullPath($Parameters['package'])
    $receipt=[IO.Path]::Combine($result,'native-windows-clock-context.json')
    $observed=@{schema_version=1;purpose='windows_clock_context_diagnostic';status='incomplete';error=$null;
        performance_acceptance_eligible=$false;normative_clock_qualified=$false;storage_operations=0;
        continuous_vm_state_exclusion_proved=$false;provider_resolution_observed=$false;provider_precision_proved=$false;
        same_host_qpf_startup_relation='construction assumption; xemu internal frequency/scale not read';
        serial_observation_scope='complete END detection only; no causal-delivery/rate bound';binding=@{};
        observer_pid=$PID;observer_powershell_version=$PSVersionTable.PSVersion.ToString();
        observation_started_utc=[DateTimeOffset]::UtcNow.ToString('o');frozen_parameters=$Parameters}
    function Save-Pr248ClockContext { [IO.File]::WriteAllText($receipt,($observed|ConvertTo-Json -Depth 40),[Text.UTF8Encoding]::new($false)) }
    Save-Pr248ClockContext
    try {
        Assert-Pr248 ($PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -eq 1) 'Native pilot requires Windows PowerShell5.1'
        $desktop=Get-Pr248DesktopContext;$observed['desktop']=$desktop
        Assert-Pr248 ($desktop['user_name'] -ieq 'Codex' -and $desktop['user_interactive'] -and $desktop['session'] -eq 1) 'Owned live desktop unavailable'
        Assert-Pr248 ($package -ceq $Parameters['expected_package']) 'Frozen package differs'
        $launch=Read-Pr248Json ([IO.Path]::Combine($result,'launch.json'))
        $manifest=Read-Pr248Json ([IO.Path]::Combine($result,'input-manifest.json'))
        $report=Read-Pr248Json ([IO.Path]::Combine($result,'diagnostics/run-state/report.json'))
        $observed['binding']=@{launch=$launch;manifest=$manifest;report=$report};Save-Pr248ClockContext
        Assert-Pr248 ($launch['job'] -ceq $Parameters['expected_job'] -and $manifest['JobId'] -ceq $Parameters['expected_job'] -and
            $launch['runId'] -ceq [IO.Path]::GetFileName($result) -and $manifest['PackageDirectory'] -ceq $package -and
            $launch['startPaused'] -is [bool] -and !$launch['startPaused']) 'Owned job/run differs'
        foreach($pair in @(@('xemu.exe','expected_xemu_sha256'),@('xemu.toml','expected_config_sha256'),
            @('storage-perf.iso','expected_iso_sha256'),@('flash.bin','expected_flash_sha256'))) {
            $rows=@($manifest['Inputs']|Where-Object {$_['Path'] -ceq $pair[0]})
            Assert-Pr248 ($rows.Count -eq 1 -and $rows[0]['Verified'] -is [bool] -and $rows[0]['Verified'] -and
                $rows[0]['Sha256'] -ceq $Parameters[$pair[1]] -and $rows[0]['ExpectedSha256'] -ceq $Parameters[$pair[1]]) 'Pinned actual input differs'
            $input=@{};[void](Get-Pr248PinnedInput $package $pair[0] $Parameters[$pair[1]] $input);$observed['binding'][$pair[0]]=$input
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
        Assert-Pr248 ($manifest['ExecutableSha256'] -ceq $Parameters['expected_launcher_sha256'] -and
            $snapshots['wrapper']['exe_path'] -ceq [IO.Path]::Combine($package,'native-launch.exe') -and
            (Get-Pr248Hash $snapshots['wrapper']['exe_path']) -ceq $manifest['ExecutableSha256']) 'Mapped owned launcher differs'
        $arguments=[Collections.Generic.List[string]]::new();$configs=[Collections.Generic.List[string]]::new()
        for($i=0;$i -lt $launch['arguments'].Count;$i++) {
            $word=$launch['arguments'][$i];if($word -ceq '-config_path'){$i++;$configs.Add($launch['arguments'][$i])}
            elseif($word.StartsWith('-config_path=')){$configs.Add($word.Substring(13))}else{$arguments.Add($word)}
        }
        Assert-Pr248 ($configs.Count -eq 1 -and [IO.Path]::GetFullPath($configs[0]) -ceq [IO.Path]::Combine($package,'xemu.toml')) 'Source config argv differs'
        Assert-Pr248 (@($arguments|Where-Object {$_ -match '^-(icount|replay|rtc|cpu)(=|$)'}).Count -eq 0) 'Undeclared clock/CPU override'
        $arguments.Add('-config_path');$arguments.Add($effective)
        Assert-Pr248 (@($arguments|Where-Object {$_ -match '[\s"]'}).Count -eq 0) 'Frozen simple argv differs'
        $line=$arguments -join ' ';$exe=[IO.Path]::Combine($package,'xemu.exe')
        Assert-Pr248 ($guest['arguments'] -ceq $line -and $snapshots['guest']['exe_path'] -ceq $exe -and
            $snapshots['guest']['command_line'] -cin @(($exe+' '+$line),('"'+$exe+'" '+$line))) 'Actual xemu command differs'
        $ports=@([regex]::Matches($line,'(?:^| )-qmp tcp:127\.0\.0\.1:(\d+),server=on,wait=off(?: |$)'))
        Assert-Pr248 ($ports.Count -eq 1) 'Owned managed QMP endpoint differs';$port=[int]$ports[0].Groups[1].Value
        $listeners=@(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $port -State Listen -ErrorAction Stop|
            ForEach-Object {@{pid=[int]$_.OwningProcess;address=$_.LocalAddress;port=[int]$_.LocalPort;state=[string]$_.State}})
        Test-Pr248Listener $listeners $snapshots['guest']['pid'] $port
        $initial=Read-Pr248Recipe $result 'clock-qmp-initial-status' 'query-status' @{}
        Assert-Pr248 ($initial['response']['running'] -is [bool] -and $initial['response']['running'] -and $initial['response']['status'] -ceq 'running') 'Initial sampled VM is not running'
        $observed['binding']['processes']=$snapshots;$observed['binding']['pipe_fields']=$fields
        $observed['binding']['qmp_listener']=$listeners;$observed['initial_managed_status']=$initial
        $observed['initial_clock']=Read-Pr248WindowsClockSample;Save-Pr248ClockContext
        $observed['initial_clock_analysis']=Test-Pr248ClockSample $observed['initial_clock'];Save-Pr248ClockContext
        $deadline=[DateTimeOffset]::UtcNow.AddSeconds(100);$serial=[IO.Path]::Combine($result,'native-serial.log');$complete=$false
        while([DateTimeOffset]::UtcNow -lt $deadline) {
            if([IO.File]::Exists($serial)) {
                $stream=[IO.File]::Open($serial,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
                try{$reader=[IO.StreamReader]::new($stream);try{$text=$reader.ReadToEnd()}finally{$reader.Dispose()}}finally{$stream.Dispose()}
                if($text -match '(?m)^# STORAGE-CAUSAL-END samples=50 markers=100 storage_operations=0\r?$'){$complete=$true;break}
            }
            Start-Sleep -Milliseconds 100
        }
        Assert-Pr248 $complete 'Complete clock diagnostic END missing/deadline'
        $observed['end_observation_utc']=[DateTimeOffset]::UtcNow.ToString('o')
        $observed['final_clock']=Read-Pr248WindowsClockSample;Save-Pr248ClockContext
        $observed['final_clock_analysis']=Test-Pr248ClockSample $observed['final_clock']
        Assert-Pr248 ($observed['initial_clock']['qpf_frequency_dec'] -ceq $observed['final_clock']['qpf_frequency_dec']) 'Observed QPF changed'
        $final=Get-Pr248ProcessSnapshot $snapshots['guest']['pid'];$observed['final_process']=$final
        foreach($field in @('pid','parent_pid','session','owner_sid','exe_path','command_line','start_ticks')) {
            Assert-Pr248 ($final[$field] -ceq $snapshots['guest'][$field]) 'Actual target lifetime changed'
        }
        Assert-Pr248 ((Get-Pr248Hash $exe) -ceq $Parameters['expected_xemu_sha256']) 'Final executable file differs'
        $observed['final_managed_status']='separate following managed recipe; not available inside observer'
        $observed['status']='complete_context_observations';$observed['observation_finished_utc']=[DateTimeOffset]::UtcNow.ToString('o');Save-Pr248ClockContext
    } catch {
        $observed['status']='INCONCLUSIVE';$observed['error']=$_.Exception.Message;Save-Pr248ClockContext;throw
    }
}
