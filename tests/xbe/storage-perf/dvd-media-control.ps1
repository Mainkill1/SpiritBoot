# Inline -Command under the approved Codex USER session; no script execution or policy override.
# Prefixed variables are supplied by the immutable owned diagnostic definition.
$ErrorActionPreference='Stop'
$identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$session=[Diagnostics.Process]::GetCurrentProcess().SessionId
if($session -ne 1 -or [Environment]::UserName -ne 'Codex' -or ![Environment]::UserInteractive){throw 'DVD control requires approved live Codex USER session'}
[void][Reflection.Assembly]::LoadWithPartialName('System.Web.Extensions')
$serializer=[Web.Script.Serialization.JavaScriptSerializer]::new()
$audit=@{schema_version=1;identity=$identity;session=$session;transport='runner-owned-local-qmp';target=$Pr248TargetPath;operations=[Collections.Generic.List[object]]::new()}
try {
 $launch=@{}
 foreach($line in [IO.File]::ReadAllLines([IO.Path]::Combine($Pr248ResultDir,'native-user-launch.txt'))){$parts=$line.Split(@('='),2);if($parts.Length -eq 2){$launch[$parts[0]]=$parts[1]}}
 if($launch['launch_transport'] -ne 'named-pipe' -or $launch['identity'] -ne $identity -or $launch['xemu_session'] -ne '1' -or $launch['window_station'] -ne 'WinSta0' -or $launch['desktop'] -ne 'Default'){throw 'Owned DVD control has no matching graphical pipe child receipt'}
 $child=[Diagnostics.Process]::GetProcessById([int]$launch['xemu_pid'])
 if($child.SessionId -ne $session -or $child.ProcessName -ne 'xemu'){throw 'Owned graphical child identity differs'}
 $match=[Text.RegularExpressions.Regex]::Match($launch['arguments'],'-qmp tcp:127\.0\.0\.1:(\d+),server=on,wait=off')
 if(!$match.Success){throw 'Unexpected owned QMP endpoint'}
 $digest=[Security.Cryptography.SHA256]::Create();$file=[IO.File]::OpenRead($Pr248TargetPath)
 try {$hash=[BitConverter]::ToString($digest.ComputeHash($file)).Replace('-','').ToLowerInvariant()} finally {$file.Dispose();$digest.Dispose()}
 if($hash -ne $Pr248TargetSha256){throw 'Declared target media pin mismatch'}
 $audit['target_sha256']=$hash;$audit['owned_xemu_pid']=$child.Id;$audit['qmp_port']=[int]$match.Groups[1].Value
 $tcp=[Net.Sockets.TcpClient]::new();$tcp.Connect('127.0.0.1',$audit['qmp_port']);$stream=$tcp.GetStream();$stream.ReadTimeout=3000;$stream.WriteTimeout=3000
 $reader=[IO.StreamReader]::new($stream,[Text.UTF8Encoding]::new($false));$writer=[IO.StreamWriter]::new($stream,[Text.UTF8Encoding]::new($false));$writer.AutoFlush=$true
 $audit['greeting']=$serializer.DeserializeObject($reader.ReadLine());$script:Pr248QmpIndex=0
 function Invoke-Pr248OwnedQmp([string]$name,$arguments) {
  $script:Pr248QmpIndex++;$request=@{execute=$name;id=$script:Pr248QmpIndex};if($null -ne $arguments){$request['arguments']=$arguments}
  $writer.WriteLine($serializer.Serialize($request))
  do {$response=$serializer.DeserializeObject($reader.ReadLine())} while(!$response.ContainsKey('id') -or $response['id'] -ne $script:Pr248QmpIndex)
  $audit['operations'].Add(@{request=$request;response=$response})
  if($response.ContainsKey('error')){throw ('Owned QMP command failed: '+$serializer.Serialize($response['error']))}
  return ,$response['return']
 }
 [void](Invoke-Pr248OwnedQmp 'qmp_capabilities' $null)
 $blocks=Invoke-Pr248OwnedQmp 'query-block' $null;$matches=[Collections.Generic.List[object]]::new()
 foreach($block in $blocks){if($block['removable'] -and $block.ContainsKey('inserted') -and [IO.Path]::GetFullPath($block['inserted']['file']) -eq [IO.Path]::GetFullPath($Pr248OldPath)){$matches.Add($block)}}
 if($matches.Count -ne 1 -or !$matches[0]['device']){throw 'Owned declared DVD is not uniquely identifiable'}
 [void](Invoke-Pr248OwnedQmp 'blockdev-change-medium' @{device=$matches[0]['device'];filename=$Pr248TargetPath;format='raw';'read-only-mode'='read-only'})
 $audit['completed']=$true
} finally {
 [IO.File]::WriteAllText([IO.Path]::Combine($Pr248ResultDir,'native-media-control.json'),$serializer.Serialize($audit))
 if($null -ne $tcp){$tcp.Dispose()}
}
