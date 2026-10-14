# SPDX-License-Identifier: GPL-2.0-or-later
# Read-only functions. The frozen runner recipe invokes Invoke-Pr248DvdGuard
# through an inline PowerShell command on the live Codex desktop. No QMP socket,
# process mutation, execution-policy change or assumed live CWD is used here.

function Assert-Pr248([bool]$Condition, [string]$Message) {
    if (!$Condition) { throw $Message }
}

function ConvertTo-Pr248Dictionary($Value) {
    if ($null -eq $Value) { return $null }
    if ($Value -is [Collections.IDictionary] -or $Value -is [pscustomobject]) {
        $result = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
        if ($Value -is [Collections.IDictionary]) {
            foreach ($key in $Value.Keys) { $result.Add([string]$key, (ConvertTo-Pr248Dictionary $Value[$key])) }
        } else {
            foreach ($property in $Value.PSObject.Properties) { $result.Add($property.Name, (ConvertTo-Pr248Dictionary $property.Value)) }
        }
        return ,$result
    }
    if ($Value -is [Array]) {
        $result = [Collections.Generic.List[object]]::new()
        foreach ($item in $Value) { $result.Add((ConvertTo-Pr248Dictionary $item)) }
        return ,$result.ToArray()
    }
    return $Value
}

function ConvertFrom-Pr248StrictJson([string]$Text) {
    # Check grammar and recursively reject duplicate decoded names before a
    # platform JSON decoder could overwrite an earlier failure or route field.
    Assert-Pr248 ($Text.Length -le 16777216) 'JSON evidence exceeds bounded size'
    $state = @{ text=$Text; offset=0 }
    function Skip-Pr248Space($s) {
        while ($s.offset -lt $s.text.Length -and " `t`r`n".Contains([string]$s.text[$s.offset])) { $s.offset++ }
    }
    function Read-Pr248String($s) {
        $match = [regex]::Match($s.text.Substring($s.offset), '^"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"')
        Assert-Pr248 $match.Success 'Invalid JSON string'
        $s.offset += $match.Length
        $decoded = ConvertFrom-Json -InputObject ('{"pr248_key":'+$match.Value+'}') -ErrorAction Stop
        return $decoded.pr248_key
    }
    function Scan-Pr248Value($s, [int]$Depth) {
        Assert-Pr248 ($Depth -le 128) 'JSON nesting exceeds bounded depth'
        Skip-Pr248Space $s
        Assert-Pr248 ($s.offset -lt $s.text.Length) 'Missing JSON value'
        $char = $s.text[$s.offset]
        if ($char -eq '"') { [void](Read-Pr248String $s); return }
        if ($char -eq '{' -or $char -eq '[') {
            $object = $char -eq '{'; $close = if ($object) { '}' } else { ']' }
            $keys = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
            $s.offset++; Skip-Pr248Space $s
            if ($s.offset -lt $s.text.Length -and $s.text[$s.offset] -eq $close) { $s.offset++; return }
            while ($true) {
                if ($object) {
                    $key = Read-Pr248String $s
                    Assert-Pr248 ($keys.Add($key)) ('Duplicate JSON field: '+$key)
                    Skip-Pr248Space $s
                    Assert-Pr248 ($s.offset -lt $s.text.Length -and $s.text[$s.offset] -eq ':') 'Missing JSON colon'
                    $s.offset++
                }
                Scan-Pr248Value $s ($Depth+1); Skip-Pr248Space $s
                Assert-Pr248 ($s.offset -lt $s.text.Length) 'Unclosed JSON container'
                if ($s.text[$s.offset] -eq $close) { $s.offset++; return }
                Assert-Pr248 ($s.text[$s.offset] -eq ',') 'Missing JSON separator'
                $s.offset++; Skip-Pr248Space $s
            }
        }
        $match = [regex]::Match($s.text.Substring($s.offset), '^(?:true|false|null|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)')
        Assert-Pr248 $match.Success 'Invalid JSON value'
        $s.offset += $match.Length
    }
    Scan-Pr248Value $state 0; Skip-Pr248Space $state
    Assert-Pr248 ($state.offset -eq $Text.Length) 'Trailing JSON content'
    # A property wrapper preserves a one-element top-level array on PS5.1,
    # whose pipeline decoder otherwise enumerates it into a single object.
    $decoded = ConvertFrom-Json -InputObject ('{"pr248_value":'+$Text+'}') -ErrorAction Stop
    return ,(ConvertTo-Pr248Dictionary $decoded.pr248_value)
}

function Read-Pr248Json([string]$Path) {
    return ,(ConvertFrom-Pr248StrictJson ([IO.File]::ReadAllText($Path)))
}

function Read-Pr248Fields([string]$Path) {
    $value = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        if (!$line) { continue }
        # Avoid PS5.1 binding the two arguments to StringSplitOptions(enum2).
        $delimiter = $line.IndexOf([char]'=')
        Assert-Pr248 ($delimiter -ge 0) 'Malformed/duplicate pipe receipt'
        $key = $line.Substring(0,$delimiter)
        Assert-Pr248 (!$value.ContainsKey($key)) 'Malformed/duplicate pipe receipt'
        $value.Add($key,$line.Substring($delimiter+1))
    }
    return ,$value
}

function Get-Pr248Hash([string]$Path) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}

function Test-Pr248DvdRoute($Blocks, [string]$Package, [string]$ExpectedFile, [string]$ExpectedDevice) {
    Assert-Pr248 ($Blocks -is [Array]) 'query-block is not a block array'
    $removable = @($Blocks | Where-Object { $_['removable'] -is [bool] -and $_['removable'] })
    Assert-Pr248 ($removable.Count -eq 1) 'Unique removable DVD route missing'
    Assert-Pr248 (@($Blocks | Where-Object { $_['device'] -ceq $ExpectedDevice }).Count -eq 1) 'Declared DVD device is not unique'
    $row = $removable[0]; $inserted = $row['inserted']
    Assert-Pr248 ($inserted -is [Collections.IDictionary] -and $inserted['file'] -is [string]) 'Inserted file missing'
    $actual = $inserted['file']
    Assert-Pr248 ([IO.Path]::IsPathRooted($actual)) 'Windows DVD method requires an observed absolute media path'
    $actual = [IO.Path]::GetFullPath($actual)
    Assert-Pr248 ($row['device'] -ceq $ExpectedDevice -and $row['locked'] -is [bool] -and !$row['locked'] -and
        [StringComparer]::OrdinalIgnoreCase.Equals($actual,[IO.Path]::GetFullPath($ExpectedFile)) -and
        [StringComparer]::OrdinalIgnoreCase.Equals([IO.Path]::GetDirectoryName($actual),[IO.Path]::GetFullPath($Package)) -and
        $inserted['ro'] -is [bool] -and $inserted['ro'] -and $inserted['drv'] -ceq 'raw') 'Actual DVD device/file/readonly/backend differs'
    return @{ device=$row['device']; actual_inserted_path=$actual; raw_block=$row }
}

function Test-Pr248ProcessIdentity($Actual, $Expected) {
    foreach ($field in @('pid','parent_pid','session','owner_sid','exe_path','command_line')) {
        Assert-Pr248 ($Actual[$field] -ceq $Expected[$field]) ('Actual owned process differs: '+$field)
    }
    Assert-Pr248 ($Actual['start_ticks'] -ge $Expected['parent_start_ticks'] -and
        $Actual['start_ticks'] -ge $Expected['minimum_start_ticks']) 'Owned process creation order differs'
}

function Test-Pr248Listener($Rows, [int]$TargetPid, [int]$Port) {
    Assert-Pr248 ($Rows.Count -eq 1) 'Unique owned QMP listener missing'
    $row = $Rows[0]
    Assert-Pr248 ($row['pid'] -eq $TargetPid -and $row['address'] -ceq '127.0.0.1' -and
        $row['port'] -eq $Port -and $row['state'] -ceq 'Listen') 'Actual owned QMP listener differs'
}

function Get-Pr248ProcessSnapshot([int]$ProcessId) {
    $process = [Diagnostics.Process]::GetProcessById($ProcessId)
    try {
        $first = $process.StartTime.ToUniversalTime().Ticks
        $rows = @(Get-CimInstance -ClassName Win32_Process -Filter ('ProcessId='+$ProcessId) -ErrorAction Stop)
        Assert-Pr248 ($rows.Count -eq 1) 'Exact owned process snapshot missing'
        $row = $rows[0]; $owner = Invoke-CimMethod -InputObject $row -MethodName GetOwnerSid -ErrorAction Stop
        Assert-Pr248 ($owner.ReturnValue -eq 0 -and $owner.Sid) 'Owned process SID unavailable'
        Assert-Pr248 (!$process.HasExited -and $process.StartTime.ToUniversalTime().Ticks -eq $first -and
            $row.ProcessId -eq $ProcessId -and $process.Path -ceq $row.ExecutablePath) 'Owned process lifetime/executable differs'
        return @{ pid=$ProcessId; parent_pid=[int]$row.ParentProcessId; session=$process.SessionId;
            owner_sid=$owner.Sid; exe_path=$process.Path; command_line=$row.CommandLine;
            start_ticks=$first; cim_creation_utc=$row.CreationDate.ToUniversalTime().ToString('o') }
    } finally { $process.Dispose() }
}

function Get-Pr248DesktopContext {
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    return @{identity=$identity.Name;owner_sid=$identity.User.Value;
        session=[Diagnostics.Process]::GetCurrentProcess().SessionId;
        user_interactive=[Environment]::UserInteractive;user_name=[Environment]::UserName}
}

function Get-Pr248PinnedInput([string]$Package, [string]$Name, [string]$ExpectedHash, $Observation) {
    Assert-Pr248 ($Name -ceq [IO.Path]::GetFileName($Name) -and $Name -notin @('','.','..')) 'Input must be one package filename'
    $path = [IO.Path]::Combine($Package,$Name); $Observation['path']=$path
    $before = Get-Item -LiteralPath $path -ErrorAction Stop
    Assert-Pr248 (!$before.PSIsContainer -and !($before.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'Input is not an ordinary file'
    $identity = @($before.Length,$before.CreationTimeUtc.Ticks,$before.LastWriteTimeUtc.Ticks)
    $hash = Get-Pr248Hash $path; $Observation['sha256']=$hash
    $after = Get-Item -LiteralPath $path -ErrorAction Stop
    $Observation['bytes']=$after.Length; $Observation['creation_ticks']=$after.CreationTimeUtc.Ticks
    $Observation['last_write_ticks']=$after.LastWriteTimeUtc.Ticks; $Observation['ntfs_file_id']=$null
    $Observation['identity_scope']='full path, size, timestamps and SHA256; NTFS file ID not observed'
    Assert-Pr248 ($hash -ceq $ExpectedHash -and $after.Length -eq $identity[0] -and
        $after.CreationTimeUtc.Ticks -eq $identity[1] -and $after.LastWriteTimeUtc.Ticks -eq $identity[2]) 'Actual input hash/metadata changed'
    return $Observation
}

function Test-Pr248FlatMap($Actual, $Expected) {
    Assert-Pr248 ($Actual -is [Collections.IDictionary] -and $Actual.Count -eq $Expected.Count) 'Actual typed arguments differ'
    foreach ($key in $Expected.Keys) {
        Assert-Pr248 ($Actual.ContainsKey($key) -and $Actual[$key] -ceq $Expected[$key]) ('Actual typed argument differs: '+$key)
    }
}

function Read-Pr248Recipe([string]$Result, [string]$Id, [string]$Command, $Arguments) {
    $matches = @([IO.Directory]::GetDirectories([IO.Path]::Combine($Result,'diagnostics')) |
        Where-Object { [IO.Path]::GetFileName($_).EndsWith('-'+$Id,[StringComparison]::Ordinal) })
    Assert-Pr248 ($matches.Count -eq 1) ('Missing/duplicate exact managed recipe: '+$Id)
    $directory=$matches[0]; $values=@{}; $hashes=@{}
    foreach ($name in @('request.json','result.json','qmp-result.json')) {
        $path=[IO.Path]::Combine($directory,$name); $values[$name]=Read-Pr248Json $path; $hashes[$name]=Get-Pr248Hash $path
    }
    $request=$values['request.json']; $outcome=$values['result.json']; $response=$values['qmp-result.json']
    Assert-Pr248 ($request['Id'] -ceq $Id -and $request['Type'] -ceq 'qmp' -and $request['QmpCommand'] -ceq $Command) 'Actual typed QMP request differs'
    Test-Pr248FlatMap $request['QmpArguments'] $Arguments
    foreach ($flag in @('PauseBefore','PauseAfter','ResumeDuring')) {
        Assert-Pr248 ($request[$flag] -is [bool] -and !$request[$flag]) 'Unexpected managed pause/resume flag'
    }
    Assert-Pr248 ($outcome['Id'] -ceq $Id -and $outcome['Type'] -ceq 'qmp' -and $outcome['Status'] -ceq 'completed' -and
        $outcome.ContainsKey('Detail') -and $null -eq $outcome['Detail'] -and $outcome['Artifacts'].Count -eq 1 -and
        $outcome['Artifacts'][0] -ceq 'qmp-result.json' -and [IO.Path]::GetFullPath($outcome['Directory']) -ceq $directory) 'Actual typed QMP result differs'
    $start=[DateTimeOffset]::Parse($outcome['StartedUtc']); $end=[DateTimeOffset]::Parse($outcome['EndedUtc'])
    Assert-Pr248 ($end -ge $start) 'Managed QMP timestamp order differs'
    return @{ identity=$Id; request=$request; result=$outcome; response=$response;
        relative_directory=('diagnostics/'+[IO.Path]::GetFileName($directory)); artifact_sha256=$hashes }
}

function Invoke-Pr248DvdGuard($Parameters) {
    $ErrorActionPreference='Stop'
    foreach ($name in @('stage','wrapper_pid','package','result','expected_job','expected_device',
        'expected_package','expected_xemu_sha256','expected_config_sha256','expected_recorder_sha256','expected_target_sha256')) {
        Assert-Pr248 ($Parameters.ContainsKey($name) -and $null -ne $Parameters[$name]) ('Missing frozen parameter: '+$name)
    }
    $stage=$Parameters['stage']; Assert-Pr248 ($stage -cin @('initial','final')) 'Invalid guard stage'
    $package=[IO.Path]::GetFullPath($Parameters['package']); $result=[IO.Path]::GetFullPath($Parameters['result'])
    $receipt=[IO.Path]::Combine($result,('native-dvd-'+$stage+'-guard.json'))
    $observed=@{schema_version=1;stage=$stage;purpose='owned_DVD_fixed_media_functional_method_only';fixed_media=$true;media_method='fixed-wrapper';exact_original_media_parity=$false;
        wrapper_pid=[int]$Parameters['wrapper_pid'];target_pid=$null;expected_device_hypothesis=$Parameters['expected_device'];
        performance_acceptance_eligible=$false;guard_complete=$false;error=$null;
        started_utc=[DateTime]::UtcNow.ToString('o');runtime_cwd=$null;settings_changed=$false}
    function Save-Pr248Guard { [IO.File]::WriteAllText($receipt,($observed|ConvertTo-Json -Depth 100)) }
    Save-Pr248Guard
    try {
        $desktop=Get-Pr248DesktopContext; $session=$desktop['session']
        Assert-Pr248 ($session -eq 1 -and $desktop['user_interactive'] -is [bool] -and
            $desktop['user_interactive'] -and $desktop['user_name'] -ieq 'Codex') 'Guard requires live Codex user desktop'
        Assert-Pr248 ($package -ceq [IO.Path]::GetFullPath($Parameters['expected_package'])) 'Actual package differs from frozen absolute target path'
        $launch=Read-Pr248Json ([IO.Path]::Combine($result,'launch.json'))
        $manifest=Read-Pr248Json ([IO.Path]::Combine($result,'input-manifest.json'))
        $report=Read-Pr248Json ([IO.Path]::Combine($result,'diagnostics/run-state/report.json'))
        Assert-Pr248 ($launch['job'] -ceq $Parameters['expected_job'] -and $manifest['JobId'] -ceq $Parameters['expected_job'] -and
            $launch['runId'] -ceq [IO.Path]::GetFileName($result) -and $manifest['PackageDirectory'] -ceq $package -and
            $launch['startPaused'] -is [bool] -and !$launch['startPaused']) 'Owned job/run/package/start policy differs'
        $observed['binding']=@{package=$package;result=$result;launch=$launch;manifest=$manifest;report=$report;
            identity=$desktop['identity'];owner_sid=$desktop['owner_sid'];session=$session;runtime_cwd=$null;
            launched_working_directory=$package;working_directory_scope='existing pinned desktop server construction; live CWD unobserved'}
        Save-Pr248Guard
        foreach ($name in @('xemu.exe','xemu.toml')) {
            $pin=if($name -ceq 'xemu.exe'){$Parameters['expected_xemu_sha256']}else{$Parameters['expected_config_sha256']}
            $rows=@($manifest['Inputs']|Where-Object {$_['Path'] -ceq $name})
            Assert-Pr248 ($rows.Count -eq 1 -and $rows[0]['Verified'] -is [bool] -and $rows[0]['Verified'] -and
                $rows[0]['Sha256'] -ceq $pin -and $rows[0]['ExpectedSha256'] -ceq $pin -and
                (Get-Pr248Hash ([IO.Path]::Combine($package,$name))) -ceq $pin) ('Actual pinned source input differs: '+$name)
        }
        $effective=[IO.Path]::GetFullPath([IO.Path]::Combine($result,'diagnostics/run-state/effective-live.toml'))
        Assert-Pr248 ($report['Status'] -cin @('prepared','complete') -and
            [IO.Path]::GetFullPath($report['ConfigSourcePath']) -ceq [IO.Path]::Combine($package,'xemu.toml') -and
            $report['ConfigSha256'] -ceq $Parameters['expected_config_sha256'] -and
            [IO.Path]::GetFullPath($report['EffectiveConfigPath']) -ceq $effective -and
            (Get-Pr248Hash $effective) -ceq $report['EffectiveConfigSha256']) 'Owned isolated effective config differs'
        $fields=@{}
        foreach ($name in @('native-user-launch.txt','native-pipe-server.txt','native-pipe-client.txt')) {
            $fields[$name]=Read-Pr248Fields ([IO.Path]::Combine($result,$name))
        }
        $guest=$fields['native-user-launch.txt'];$server=$fields['native-pipe-server.txt'];$client=$fields['native-pipe-client.txt']
        foreach ($row in @($guest,$server,$client)) {
            Assert-Pr248 ($row['identity'] -ceq $desktop['identity'] -and $row['session'] -ceq '1' -and
                $row['window_station'] -ceq 'WinSta0' -and $row['desktop'] -ceq 'Default' -and
                $row['pipe_name'] -ceq $guest['pipe_name'] -and $row['server_pid'] -ceq $guest['server_pid']) 'Actual protected pipe identity differs'
        }
        Assert-Pr248 ($guest['launch_transport'] -ceq 'named-pipe' -and $guest['xemu_session'] -ceq '1' -and
            $server['operation'] -ceq 'RUN' -and $client['operation'] -ceq 'RUN' -and
            $client['handshake_verified'] -ceq 'True' -and $server['owner_sid'] -ceq $desktop['owner_sid'] -and
            $server['acl_sddl'] -ceq ('D:P(A;;0x1f019f;;;'+$desktop['owner_sid']+')')) 'Actual pipe transport/ACL/handshake differs'
        $snapshots=@{}; $snapshots['wrapper']=Get-Pr248ProcessSnapshot ([int]$Parameters['wrapper_pid'])
        $snapshots['client']=Get-Pr248ProcessSnapshot ([int]$client['client_pid'])
        $snapshots['server']=Get-Pr248ProcessSnapshot ([int]$guest['server_pid'])
        $snapshots['guest']=Get-Pr248ProcessSnapshot ([int]$guest['xemu_pid'])
        $observed['target_pid']=$snapshots['guest']['pid'];$observed['binding']['processes']=$snapshots
        $observed['binding']['pipe_fields']=$fields; Save-Pr248Guard
        foreach ($name in @('wrapper','client','server','guest')) {
            Assert-Pr248 ($snapshots[$name]['owner_sid'] -ceq $desktop['owner_sid'] -and $snapshots[$name]['session'] -eq $session) 'Owned process user/session differs'
        }
        Assert-Pr248 ($snapshots['wrapper']['exe_path'] -ceq [IO.Path]::Combine($package,'native-launch.exe') -and
            (Get-Pr248Hash $snapshots['wrapper']['exe_path']) -ceq $manifest['ExecutableSha256']) 'Owned mapped wrapper differs'
        foreach ($pair in @(@('client','wrapper'),@('server','client'),@('guest','server'))) {
            Assert-Pr248 ($snapshots[$pair[0]]['parent_pid'] -eq $snapshots[$pair[1]]['pid'] -and
                $snapshots[$pair[0]]['start_ticks'] -ge $snapshots[$pair[1]]['start_ticks']) 'Owned process ancestry/lifetime differs'
        }
        $arguments=[Collections.Generic.List[string]]::new();$configs=[Collections.Generic.List[string]]::new()
        for($index=0;$index -lt $launch['arguments'].Count;$index++) {
            $word=$launch['arguments'][$index]
            if($word -ceq '-config_path'){$index++;$configs.Add($launch['arguments'][$index])}
            elseif($word.StartsWith('-config_path=')){$configs.Add($word.Substring(13))}
            else{$arguments.Add($word)}
        }
        Assert-Pr248 ($configs.Count -eq 1 -and [IO.Path]::GetFullPath($configs[0]) -ceq [IO.Path]::Combine($package,'xemu.toml')) 'Declared source config differs'
        $arguments.Add('-config_path');$arguments.Add($effective)
        Assert-Pr248 (@($arguments|Where-Object {$_ -match '[\s"]'}).Count -eq 0) 'This frozen Windows recipe requires unambiguous simple arguments'
        $expectedLine=$arguments -join ' ';$exe=[IO.Path]::Combine($package,'xemu.exe')
        Assert-Pr248 ($guest['arguments'] -ceq $expectedLine) 'Actual child argument receipt differs'
        $expectedCommand=$exe+' '+$expectedLine
        if($snapshots['guest']['command_line'] -ceq ('"'+$exe+'" '+$expectedLine)){$expectedCommand='"'+$exe+'" '+$expectedLine}
        Test-Pr248ProcessIdentity $snapshots['guest'] @{
            pid=[int]$guest['xemu_pid'];parent_pid=[int]$guest['server_pid'];session=$session;
            owner_sid=$desktop['owner_sid'];exe_path=$exe;command_line=$expectedCommand;
            parent_start_ticks=$snapshots['server']['start_ticks'];minimum_start_ticks=$snapshots['wrapper']['start_ticks']}
        $ports=@([regex]::Matches($expectedLine,'(?:^| )-qmp tcp:127\.0\.0\.1:(\d+),server=on,wait=off(?: |$)'))
        Assert-Pr248 ($ports.Count -eq 1) 'Unique runner-owned QMP endpoint missing'
        $port=[int]$ports[0].Groups[1].Value
        $listeners=@(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $port -State Listen -ErrorAction Stop |
            ForEach-Object {@{pid=[int]$_.OwningProcess;address=$_.LocalAddress;port=[int]$_.LocalPort;state=[string]$_.State}})
        $observed['binding']['qmp_listener']=$listeners;Save-Pr248Guard
        Test-Pr248Listener $listeners $snapshots['guest']['pid'] $port
        $observed['recorder']=@{};$observed['target']=@{};Save-Pr248Guard
        [void](Get-Pr248PinnedInput $package 'storage-perf.iso' $Parameters['expected_recorder_sha256'] $observed['recorder']);Save-Pr248Guard
        [void](Get-Pr248PinnedInput $package 'target.iso' $Parameters['expected_target_sha256'] $observed['target']);Save-Pr248Guard
        foreach($pair in @(@('storage-perf.iso','expected_recorder_sha256'),@('target.iso','expected_target_sha256'))) {
            $rows=@($manifest['Inputs']|Where-Object {$_['Path'] -ceq $pair[0]})
            Assert-Pr248 ($rows.Count -eq 1 -and $rows[0]['Verified'] -is [bool] -and $rows[0]['Verified'] -and
                $rows[0]['Sha256'] -ceq $Parameters[$pair[1]] -and $rows[0]['ExpectedSha256'] -ceq $Parameters[$pair[1]]) 'Actual media input manifest differs'
        }
        $query=Read-Pr248Recipe $result ('dvd-qmp-'+$stage) 'query-block' @{}
        $observed['managed_query']=$query;Save-Pr248Guard
        $file=[IO.Path]::Combine($package,'storage-perf.iso')
        $observed['actual_route']=Test-Pr248DvdRoute $query['response'] $package $file $Parameters['expected_device'];Save-Pr248Guard
        if($stage -ceq 'final') {
            $firstPath=[IO.Path]::Combine($result,'native-dvd-initial-guard.json');$first=Read-Pr248Json $firstPath
            $observed['initial_guard_sha256']=Get-Pr248Hash $firstPath
            Assert-Pr248 ($first['guard_complete'] -is [bool] -and $first['guard_complete'] -and $null -eq $first['error']) 'Initial guard failed'
            foreach($name in @('wrapper','client','server','guest')) {
                Test-Pr248FlatMap $snapshots[$name] $first['binding']['processes'][$name]
            }
            foreach($name in @('recorder','target')) {Test-Pr248FlatMap $observed[$name] $first[$name]}
            Assert-Pr248 ($first['actual_route']['device'] -ceq $observed['actual_route']['device']) 'Owned DVD route changed'
            Assert-Pr248 ($first['fixed_media'] -is [bool] -and $first['fixed_media'] -and $first['media_method'] -ceq 'fixed-wrapper' -and $first['exact_original_media_parity'] -is [bool] -and !$first['exact_original_media_parity'] -and !$first.ContainsKey('managed_change')) 'Initial fixed-media scope differs'
            $moments=@([DateTimeOffset]::Parse($first['managed_query']['result']['EndedUtc']),[DateTimeOffset]::Parse($query['result']['StartedUtc']))
            for($index=1;$index -lt $moments.Count;$index++){Assert-Pr248 ($moments[$index] -ge $moments[$index-1]) 'Managed media command order differs'}
        }
        $last=Get-Pr248ProcessSnapshot $snapshots['guest']['pid'];$observed['process_at_end']=$last
        Test-Pr248FlatMap $last $snapshots['guest']
        $observed['guard_complete']=$true;$observed['ended_utc']=[DateTime]::UtcNow.ToString('o');Save-Pr248Guard
    } catch {
        $observed['error']=$_.Exception.Message;$observed['ended_utc']=[DateTime]::UtcNow.ToString('o');Save-Pr248Guard
        throw
    }
}
