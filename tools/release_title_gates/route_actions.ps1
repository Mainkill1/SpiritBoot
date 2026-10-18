# SPDX-License-Identifier: GPL-2.0-or-later
# Bounded input adapter for runner-attested xemu child processes.
function Resolve-ForzaButton([string]$Button) {
    $keys=@{A=@(0x1e,$false); B=@(0x30,$false); Start=@(0x1c,$false); Back=@(0x0e,$false); DPadUp=@(0x48,$true); DPadDown=@(0x50,$true); DPadLeft=@(0x4b,$true); DPadRight=@(0x4d,$true); LStickLeft=@(0x1f,$false); LStickRight=@(0x21,$false); LTrigger=@(0x11,$false); RTrigger=@(0x18,$false)}
    Assert-Pr248 ($keys.ContainsKey($Button)) 'Unsupported logical Xbox key'
    return ,$keys[$Button]
}
function Invoke-ForzaAction($Parameters) {
    $ErrorActionPreference='Stop'
    $result=[IO.Path]::GetFullPath($Parameters.result); $package=[IO.Path]::GetFullPath($Parameters.package)
    $record=@{schema_version=2;action=$Parameters.action;button=$Parameters.button;buttons=$Parameters.buttons;label=$Parameters.label;status='error';error=$null;started_utc=[DateTime]::UtcNow.ToString('o');input_sent=$false;input_attempted=$false;diagnostic_only=$true}
    try {
        Assert-Pr248 ($Parameters.action -cin @('context','press','chord','guided_route')) 'Unsupported action'
        if($Parameters.action -ceq 'press') {$key=Resolve-ForzaButton $Parameters.button}
        if($Parameters.action -ceq 'chord') {
            $names=@($Parameters.buttons -csplit ','); Assert-Pr248 ($names.Count -ge 1 -and $names.Count -le 4) 'Invalid chord button count'
            $resolved=@($names|ForEach-Object {Resolve-ForzaButton $_}); $scans=[int[]]@($resolved|ForEach-Object {$_[0]}); $extended=[bool[]]@($resolved|ForEach-Object {$_[1]})
        }
        $desktop=Get-Pr248DesktopContext; $desktop.station=[DoaOwnedInput]::Station(); $desktop.desktop=[DoaOwnedInput]::Desktop()
        Assert-Pr248 ($desktop.user_interactive -eq $true -and $desktop.session -gt 0 -and $desktop.user_name -ieq 'codex' -and $desktop.station -ceq 'WinSta0' -and $desktop.desktop -ceq 'Default') 'Live USER desktop is required'
        $guest=Read-Pr248Fields ([IO.Path]::Combine($result,'native-user-launch.txt')); $server=Read-Pr248Fields ([IO.Path]::Combine($result,'native-pipe-server.txt')); $client=Read-Pr248Fields ([IO.Path]::Combine($result,'native-pipe-client.txt'))
        foreach($row in @($guest,$server,$client)) {Assert-Pr248 ($row.identity -ceq $desktop.identity -and [int]$row.session -eq $desktop.session -and $row.window_station -ceq 'WinSta0' -and $row.desktop -ceq 'Default' -and $row.pipe_name -ceq $guest.pipe_name -and $row.server_pid -ceq $guest.server_pid) 'Protected pipe identity mismatch'}
        Assert-Pr248 ($guest.launch_transport -ceq 'named-pipe' -and $guest.owner_sid -ceq $desktop.owner_sid -and [int]$guest.xemu_session -eq $desktop.session -and $client.handshake_verified -ceq 'True' -and $client.operation -ceq 'RUN' -and $server.operation -ceq 'RUN' -and $server.owner_sid -ceq $desktop.owner_sid -and $server.acl_sddl -ceq ('D:P(A;;0x1f019f;;;'+$desktop.owner_sid+')')) 'Owned pipe handshake/ACL mismatch'
        $snapshot=Get-Pr248ProcessSnapshot ([int]$guest.xemu_pid); $exe=[IO.Path]::GetFullPath([IO.Path]::Combine($package,'xemu.exe'))
        Assert-Pr248 ([int]$Parameters.target_pid -eq $snapshot.pid -and $snapshot.owner_sid -ceq $desktop.owner_sid -and $snapshot.session -eq $desktop.session -and [StringComparer]::OrdinalIgnoreCase.Equals($snapshot.exe_path,$exe) -and [StringComparer]::OrdinalIgnoreCase.Equals($guest.xemu_exe,$exe) -and $snapshot.start_ticks -eq [long]$guest.xemu_start_ticks) 'Runner target and owned xemu receipt differ'
        $hashes=@{xemu=Get-Pr248Hash $exe;launcher=Get-Pr248Hash ([IO.Path]::Combine($package,'native-launch.exe'));flash=Get-Pr248Hash ([IO.Path]::Combine($package,'flash.bin'))}
        Assert-Pr248 ($hashes.xemu -ceq $Parameters.xemu_sha256 -and $hashes.launcher -ceq $Parameters.launcher_sha256 -and $hashes.flash -ceq $Parameters.flash_sha256) 'Pinned executable/BIOS mismatch'
        $anchorPath=[IO.Path]::Combine($result,'forza-owned-child-anchor.json')
        if([IO.File]::Exists($anchorPath)) {$anchor=Read-Pr248Json $anchorPath; foreach($field in @('pid','start_ticks','exe_path','owner_sid','session','parent_pid','command_line')) {Assert-Pr248 ($snapshot[$field] -ceq $anchor[$field]) 'Owned child changed since first context'}} else {[IO.File]::WriteAllText($anchorPath,($snapshot|ConvertTo-Json -Depth 5))}
        $record.desktop=$desktop; $record.process=$snapshot; $record.pipe_fields=@{guest=$guest;server=$server;client=$client}; $record.input_sha256=$hashes
        if($Parameters.action -cne 'context') {
            $hold=[int]$Parameters.hold_ms;if($hold -eq 0){$hold=100};$record.hold_ms=$hold;$record.input_attempted=$true;$record.input_sent=$null
            if($Parameters.action -ceq 'press') {$record.scan_codes=@($key[0]);[DoaOwnedInput]::Press($snapshot.pid,[long]$snapshot.start_ticks,$desktop.session,$exe,$key[0],$key[1],$hold)}
            if($Parameters.action -ceq 'chord') {$record.scan_codes=$scans;[DoaOwnedInput]::PressChord($snapshot.pid,[long]$snapshot.start_ticks,$desktop.session,$exe,$scans,$extended,$hold)}
            if($Parameters.action -ceq 'guided_route') {
                $shots=[IO.Path]::GetFullPath([IO.Path]::Combine($result,'screenshots'))
                Assert-Pr248 ($shots.StartsWith($result+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) 'Route screenshots escaped result directory'
                [DoaOwnedInput]::DriveGuided($snapshot.pid,[long]$snapshot.start_ticks,$desktop.session,$exe,$shots,$hold)
            }
            $record.input_sent=$true;$record.focus_checked_by_helper=$true
        }
        $record.status='complete'
    } catch {$record.error=$_.Exception.Message;throw}
    finally {$record.finished_utc=[DateTime]::UtcNow.ToString('o');$path=[IO.Path]::Combine($result,('forza-action-'+[Guid]::NewGuid().ToString('N')+'.json'));[IO.File]::WriteAllText($path,($record|ConvertTo-Json -Depth 15))}
}
