"""Run the actual PowerShell guard's pure validation functions on invented data."""
import os
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tests/xbe/storage-perf/dvd-route-windows-guard.ps1'


class WindowsDvdGuardTests(unittest.TestCase):
    def invoke(self, body):
        runtime = os.environ.get('PR248_PWSH') or shutil.which('pwsh')
        if not runtime:
            self.skipTest('PowerShell is unavailable; native Windows method stays unqualified')
        source = str(SOURCE).replace("'", "''")
        command = ("$ErrorActionPreference='Stop'; try { . '" + source + "'; " + body +
                   " } catch { [Console]::Error.WriteLine($_.ToString()); "
                   "[Console]::Error.WriteLine($_.ScriptStackTrace); exit 1 }")
        result = subprocess.run([runtime, '-NoProfile', '-NonInteractive', '-Command', command],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def command_builder(self):
        path = SOURCE.parent/'make-windows-dvd-guard-command.py'
        spec = importlib.util.spec_from_file_location('windows_dvd_command', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def fixture(self, root):
        package, result = root / 'package', root / 'result'
        package.mkdir(); (result / 'diagnostics/run-state').mkdir(parents=True)
        def put(path, value):
            path.write_text(json.dumps(value))
        def sha(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()
        for name in ('xemu.exe', 'native-launch.exe', 'xemu.toml', 'storage-perf.iso', 'target.iso'):
            (package / name).write_bytes(('invented:' + name).encode())
        effective = result / 'diagnostics/run-state/effective-live.toml'
        effective.write_text('invented isolated config')
        expected_arguments = '-m 64 -qmp tcp:127.0.0.1:1234,server=on,wait=off -config_path ' + str(effective)
        put(result / 'launch.json', {'job': 'pr248-native-invented', 'runId': 'result',
            'startPaused': False, 'arguments': ['-config_path', str(package / 'xemu.toml'), '-m', '64',
                                               '-qmp', 'tcp:127.0.0.1:1234,server=on,wait=off']})
        put(result / 'input-manifest.json', {'JobId': 'pr248-native-invented', 'PackageDirectory': str(package),
            'ExecutableSha256': sha(package / 'native-launch.exe'), 'Inputs': [
                {'Path': name, 'Verified': True, 'Sha256': sha(package / name),
                 'ExpectedSha256': sha(package / name)} for name in ('xemu.exe','xemu.toml','storage-perf.iso','target.iso')]})
        put(result / 'diagnostics/run-state/report.json', {'Status': 'prepared',
            'ConfigSourcePath': str(package / 'xemu.toml'), 'ConfigSha256': sha(package / 'xemu.toml'),
            'EffectiveConfigPath': str(effective), 'EffectiveConfigSha256': sha(effective)})
        common = {'identity': 'invented-codex', 'session': '1', 'server_pid': '12',
                  'pipe_name': 'owned', 'window_station': 'WinSta0', 'desktop': 'Default'}
        fields = {
            'native-user-launch.txt': {**common, 'xemu_pid': '13', 'xemu_session': '1',
                'launch_transport': 'named-pipe', 'arguments': expected_arguments},
            'native-pipe-server.txt': {**common, 'owner_sid': 'invented-sid', 'operation': 'RUN',
                'acl_sddl': 'D:P(A;;0x1f019f;;;invented-sid)'},
            'native-pipe-client.txt': {**common, 'client_pid': '11', 'handshake_verified': 'True', 'operation': 'RUN'},
        }
        for name, values in fields.items():
            (result / name).write_text(''.join(key + '=' + value + '\n' for key, value in values.items()))
        for stage in ('initial', 'change', 'final'):
            directory = result / ('diagnostics/000-dvd-qmp-' + stage); directory.mkdir()
            identity = 'dvd-qmp-' + stage
            args = {} if stage != 'change' else {'device':'ide0-cd1','filename':str(package/'target.iso'),
                'format':'raw','read-only-mode':'read-only'}
            command = 'query-block' if stage != 'change' else 'blockdev-change-medium'
            put(directory/'request.json', {'Id':identity,'Type':'qmp','QmpCommand':command,'QmpArguments':args,
                'PauseBefore':False,'PauseAfter':False,'ResumeDuring':False})
            time = {'initial':1,'change':3,'final':5}[stage]
            put(directory/'result.json', {'Id':identity,'Type':'qmp','Status':'completed','Detail':None,
                'Artifacts':['qmp-result.json'],'Directory':str(directory),
                'StartedUtc':f'2026-10-14T00:00:0{time}+00:00','EndedUtc':f'2026-10-14T00:00:0{time+1}+00:00'})
            put(directory/'qmp-result.json', {} if stage == 'change' else [{
                'device':'ide0-cd1','removable':True,'locked':False,'inserted':{
                    'file':str(package/('storage-perf.iso' if stage == 'initial' else 'target.iso')),'ro':True,'drv':'raw'}}])
        processes = {}
        for index, name in enumerate(('wrapper','client','server','guest'),10):
            processes[str(index)] = {'pid':index,'parent_pid':index-1,'session':1,'owner_sid':'invented-sid',
                'start_ticks':index,'exe_path':str(package/('native-launch.exe' if name=='wrapper' else 'xemu.exe')),
                'command_line':str(package/'xemu.exe')+' '+expected_arguments}
        fixture = {'desktop':{'identity':'invented-codex','owner_sid':'invented-sid','session':1,
            'user_name':'Codex','user_interactive':True},'processes':processes,
            'parameters':{'stage':'initial','wrapper_pid':10,'package':str(package),'result':str(result),
                'expected_job':'pr248-native-invented','expected_device':'ide0-cd1','expected_package':str(package),
                'expected_xemu_sha256':sha(package/'xemu.exe'),'expected_config_sha256':sha(package/'xemu.toml'),
                'expected_recorder_sha256':sha(package/'storage-perf.iso'),'expected_target_sha256':sha(package/'target.iso')}}
        path = root/'fixture.json'; put(path,fixture)
        return path, fixture, result

    def run_fixture(self, path, stages):
        quoted = str(path).replace("'", "''")
        return self.invoke("$script:f=Read-Pr248Json '" + quoted + "'" + r''';
            function Get-Pr248DesktopContext { return $script:f['desktop'] }
            function Get-Pr248ProcessSnapshot([int]$ProcessId) { return $script:f['processes'][[string]$ProcessId] }
            function Get-NetTCPConnection {
                return [pscustomobject]@{OwningProcess=13;LocalAddress='127.0.0.1';LocalPort=1234;State='Listen'}
            }
        ''' + stages)

    def test_strict_decoder_rejects_recursive_duplicates_and_invalid_json(self):
        self.invoke(r'''
        $good=ConvertFrom-Pr248StrictJson '{"a":[{"b":1}],"escaped":"x\\y","nil":null}';
        if($good['a'][0]['b'] -ne 1){throw 'valid nested JSON changed'}
        foreach($bad in @('{"status":"error","status":"ok"}',
                         '{"x":{"a":1,"\u0061":2}}', '[{"a":1,"a":2}]',
                         '{"x":01}', '{"x":true}junk', '{"x":NaN}', '{"x":[1,]}')){
          $rejected=$false; try{ConvertFrom-Pr248StrictJson $bad | Out-Null}catch{$rejected=$true}
          if(!$rejected){throw ('accepted invalid/duplicate JSON: '+$bad)}
        }
        ''')

    def test_route_guard_rejects_foreign_ambiguous_locked_or_writable_media(self):
        self.invoke(r'''
        $package=[IO.Path]::GetFullPath('owned-package');
        $old=[IO.Path]::Combine($package,'storage-perf.iso');
        $value=@{device='ide0-cd1';removable=$true;locked=$false;
                 inserted=@{file=$old;ro=$true;drv='raw'}};
        $ok=Test-Pr248DvdRoute @($value) $package $old 'ide0-cd1';
        if($ok['device'] -ne 'ide0-cd1'){throw 'valid DVD route changed'}
        foreach($field in @('device','locked','removable','file','relative','ro','drv')){
          $bad=ConvertFrom-Pr248StrictJson ($value|ConvertTo-Json -Depth 8 -Compress);
          switch($field){
            'device' {$bad['device']='ide1-cd0'}
            'locked' {$bad['locked']=$true}
            'removable' {$bad['removable']=$false}
            'file' {$bad['inserted']['file']=[IO.Path]::GetFullPath('foreign.iso')}
            'relative' {$bad['inserted']['file']='storage-perf.iso'}
            'ro' {$bad['inserted']['ro']=$false}
            'drv' {$bad['inserted']['drv']='qcow2'}
          }
          $rejected=$false;try{Test-Pr248DvdRoute @($bad) $package $old 'ide0-cd1'|Out-Null}catch{$rejected=$true}
          if(!$rejected){throw ('invalid route accepted: '+$field)}
        }
        $rejected=$false;try{Test-Pr248DvdRoute @($value,$value) $package $old 'ide0-cd1'|Out-Null}catch{$rejected=$true}
        if(!$rejected){throw 'ambiguous removable route accepted'}
        ''')

    def test_child_identity_binds_parent_creation_owner_exe_command_and_listener(self):
        self.invoke(r'''
        $expected=@{pid=42;parent_pid=41;session=1;owner_sid='owned';
                    exe_path='xemu.exe';command_line='xemu -qmp owned';
                    parent_start_ticks=99;minimum_start_ticks=99};
        $actual=@{pid=42;parent_pid=41;session=1;owner_sid='owned';
                  exe_path='xemu.exe';command_line='xemu -qmp owned';start_ticks=100};
        Test-Pr248ProcessIdentity $actual $expected;
        foreach($field in @('pid','parent_pid','session','owner_sid','exe_path','command_line','start_ticks')){
          $bad=$actual.Clone();$bad[$field]=if($field -eq 'start_ticks'){98}elseif($bad[$field] -is [string]){'foreign'}else{0};
          $rejected=$false;try{Test-Pr248ProcessIdentity $bad $expected}catch{$rejected=$true}
          if(!$rejected){throw ('foreign process accepted: '+$field)}
        }
        Test-Pr248Listener @(@{pid=42;address='127.0.0.1';port=1234;state='Listen'}) 42 1234;
        foreach($entry in @(@{pid=43;address='127.0.0.1';port=1234;state='Listen'},
                           @{pid=42;address='0.0.0.0';port=1234;state='Listen'},
                           @{pid=42;address='127.0.0.1';port=1234;state='Established'})){
          $rejected=$false;try{Test-Pr248Listener @($entry) 42 1234}catch{$rejected=$true}
          if(!$rejected){throw 'wrong owned listener accepted'}
        }
        ''')

    def test_actual_main_preserves_failure_and_checks_initial_final_lifetime(self):
        with tempfile.TemporaryDirectory(prefix='pr248-win-dvd-main-') as temporary:
            path, fixture, result = self.fixture(Path(temporary))
            self.run_fixture(path, r'''
                Invoke-Pr248DvdGuard $script:f['parameters'];
                $script:f['parameters']['stage']='final';Invoke-Pr248DvdGuard $script:f['parameters'];
            ''')
            final = json.loads((result/'native-dvd-final-guard.json').read_text())
            self.assertTrue(final['guard_complete'])
            self.assertIsNone(final['error'])
            self.assertIsNone(final['runtime_cwd'])
            self.assertIsNone(final['target']['ntfs_file_id'])
            fixture['parameters']['stage'] = 'final'
            fixture['processes']['13']['start_ticks'] += 1
            path.write_text(json.dumps(fixture))
            self.run_fixture(path, r'''
                $rejected=$false;try{Invoke-Pr248DvdGuard $script:f['parameters']}catch{$rejected=$true}
                if(!$rejected){throw 'changed native lifetime accepted'}
            ''')
            failed = json.loads((result/'native-dvd-final-guard.json').read_text())
            self.assertFalse(failed['guard_complete'])
            self.assertIn('start_ticks', failed['error'])

    def test_actual_main_stops_on_failed_managed_recipe_and_retains_actual_media_hash(self):
        with tempfile.TemporaryDirectory(prefix='pr248-win-dvd-fault-') as temporary:
            path, fixture, result = self.fixture(Path(temporary))
            outcome_path = result/'diagnostics/000-dvd-qmp-initial/result.json'
            outcome = json.loads(outcome_path.read_text()); outcome['Status']='failed'
            outcome_path.write_text(json.dumps(outcome))
            self.run_fixture(path, r'''
                $rejected=$false;try{Invoke-Pr248DvdGuard $script:f['parameters']}catch{$rejected=$true}
                if(!$rejected){throw 'failed managed query accepted'}
            ''')
            failed = json.loads((result/'native-dvd-initial-guard.json').read_text())
            self.assertFalse(failed['guard_complete'])
            self.assertEqual(failed['target']['sha256'],fixture['parameters']['expected_target_sha256'])
            self.assertIn('QMP result',failed['error'])

    def test_short_frozen_loader_rejects_ambiguous_context_and_wrong_source(self):
        tool = self.command_builder()
        expected = {'expected_package':r'C:\owned\Queue\Testing\agent-pr248-native-win-dvd',
            'expected_job':'pr248-native-win-dvd','expected_device':'ide0-cd1',
            **{key:'a'*64 for key in ('expected_xemu_sha256','expected_config_sha256',
                                      'expected_recorder_sha256','expected_target_sha256')}}
        args = tool.make_arguments(expected,hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'initial')
        self.assertLess(len(args[-1]),12000)
        self.assertNotIn('ExecutionPolicy',args[-1])
        for key, value in (('expected_package',r'C:\owned\..\foreign'),
                           ('expected_package',r'C:\owned\{resultDir}'),
                           ('expected_job','foreign'),('expected_device','ide1-cd0')):
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                tool.make_arguments({**expected,key:value},'a'*64,'initial')
        # The loader must stop before interpreting any differing source bytes.
        with tempfile.TemporaryDirectory(prefix='pr248-win-dvd-loader-') as temporary:
            directory = Path(temporary)
            (directory/'dvd-route-windows-guard.ps1').write_text('throw "unexpected source execution"')
            command = tool.make_arguments(expected,'a'*64,'initial')[-1]
            # Linux lacks Windows separators; only the invented test filename
            # expansion changes here. The remaining actual loader is unchanged.
            command = command.replace("'{packageDir}\\dvd-route-windows-guard.ps1'",
                                      "'"+str(directory/'dvd-route-windows-guard.ps1')+"'")
            self.invoke("$rejected=$false;try{"+command+"}catch{"
                        "$rejected=$_.Exception.Message -ceq 'Frozen DVD guard source differs'};"
                        "if(!$rejected){throw 'wrong source reached invocation'}")


if __name__ == '__main__':
    unittest.main()
