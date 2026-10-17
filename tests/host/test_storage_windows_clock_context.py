"""Portable PowerShell control tests with invented observations, never Windows API calls."""
from pathlib import Path
import importlib.util
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'tests/xbe/storage-perf/windows-clock-context.ps1'
GUARD = SOURCE.parent/'dvd-route-windows-guard.ps1'


class ClockContextControls(unittest.TestCase):
    def invoke(self, body):
        quote = lambda path: str(path).replace("'", "''")
        command = ("$ErrorActionPreference='Stop'; try { . '" + quote(GUARD)
                   + "'; . '" + quote(SOURCE) + "'; " + body
                   + " } catch { [Console]::Error.WriteLine($_.ToString()); exit 1 }")
        runtime=os.environ.get('PR248_PWSH') or shutil.which('pwsh')
        if not runtime:
            self.skipTest('PowerShell unavailable; native clock context remains unqualified')
        result = subprocess.run([runtime, '-NoProfile', '-NonInteractive', '-Command', command],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def sample(self):
        return r'''$sample=@{qpf_success=$true;qpf_frequency_dec='10000000';
          qpc_before_success=$true;qpc_before_dec='123456789';qpc_after_success=$true;qpc_after_dec='123456999';
          utc_begin='2026-10-14T00:00:00Z';utc_end='2026-10-14T00:00:01Z'};'''

    def test_actual_frequency_identity_and_quantum_are_distinct_from_precision_claims(self):
        self.invoke(self.sample() + r'''$r=Test-Pr248ClockSample $sample;
          Assert-Pr248 ($r['frequency_dec'] -ceq '10000000' -and $r['count_quantum_seconds']['numerator'] -eq 1 -and
            $r['count_quantum_seconds']['denominator_dec'] -ceq '10000000') 'actual frequency/quantum missing';
          Assert-Pr248 ($r['constructor_derived_ns_per_tick_dec'] -ceq '100') 'integer branch derivation differs';
          Assert-Pr248 (!$r['provider_precision_proved'] -and !$r['performance_acceptance_eligible']) 'narrow context promoted';''')

    def test_failed_missing_zero_and_out_of_range_calls_do_not_default_to_success(self):
        self.invoke(self.sample() + r'''foreach($fault in @('api','missing','zero','overflow')) {
          $bad=$sample.Clone();if($fault -eq 'api'){$bad['qpf_success']=$false}
          elseif($fault -eq 'missing'){$bad.Remove('qpc_before_success')}
          elseif($fault -eq 'zero'){$bad['qpf_frequency_dec']='0'}
          else{$bad['qpf_frequency_dec']='9223372036854775808'}
          $rejected=$false;try{Test-Pr248ClockSample $bad|Out-Null}catch{$rejected=$true}
          Assert-Pr248 $rejected ('invalid clock API evidence accepted: '+$fault)}''')

    def test_counter_rollback_and_timestamp_rollback_remain_unknown(self):
        self.invoke(self.sample() + r'''foreach($fault in @('counter','utc')) {
          $bad=$sample.Clone();if($fault -eq 'counter'){$bad['qpc_after_dec']='1'}
          else{$bad['utc_end']='2026-10-13T00:00:00Z'}
          $rejected=$false;try{Test-Pr248ClockSample $bad|Out-Null}catch{$rejected=$true}
          Assert-Pr248 $rejected 'rollback accepted'}''')

    def test_positive_qpf_unsupported_by_compiled_divisor_retains_observation(self):
        self.invoke(self.sample() + r'''$sample['qpf_frequency_dec']='4294967296';$r=Test-Pr248ClockSample $sample;
          Assert-Pr248 ($r['frequency_dec'] -ceq '4294967296' -and !$r['compiled_route_supported']) 'unsupported actual F hidden';
          Assert-Pr248 ($r['count_quantum_seconds']['denominator_dec'] -ceq '4294967296') 'actual quantum replaced';''')

    def test_full_guard_control_flow_with_invented_lower_context(self):
        source = ROOT/'tests/host/test_storage_windows_dvd_guard.py'
        spec = importlib.util.spec_from_file_location('existing_owned_guard_fixture', source)
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            path, fixture, result = module.WindowsDvdGuardTests().fixture(Path(temporary))
            fixture['parameters']['expected_iso_sha256'] = fixture['parameters']['expected_recorder_sha256']
            package=Path(fixture['parameters']['package']);flash=package/'flash.bin';flash.write_bytes(b'invented:flash.bin')
            fixture['parameters']['expected_flash_sha256']=hashlib.sha256(flash.read_bytes()).hexdigest()
            fixture['parameters']['expected_launcher_sha256']=hashlib.sha256((package/'native-launch.exe').read_bytes()).hexdigest()
            manifest_path=result/'input-manifest.json';manifest=json.loads(manifest_path.read_text())
            manifest['Inputs'].append({'Path':'flash.bin','Verified':True,'Sha256':fixture['parameters']['expected_flash_sha256'],
                                       'ExpectedSha256':fixture['parameters']['expected_flash_sha256']})
            manifest_path.write_text(json.dumps(manifest))
            path.write_text(json.dumps(fixture))
            (result/'native-serial.log').write_text('# STORAGE-CAUSAL-END samples=50 markers=100 storage_operations=0\n')
            qmp = result/'diagnostics/000-clock-qmp-initial-status';qmp.mkdir()
            request={'Id':'clock-qmp-initial-status','Type':'qmp','QmpCommand':'query-status','QmpArguments':{},
                     'PauseBefore':False,'PauseAfter':False,'ResumeDuring':False}
            outcome={'Id':'clock-qmp-initial-status','Type':'qmp','Status':'completed','Detail':None,
                     'Artifacts':['qmp-result.json'],'Directory':str(qmp),
                     'StartedUtc':'2026-10-14T00:00:01Z','EndedUtc':'2026-10-14T00:00:02Z'}
            for name,value in [('request.json',request),('result.json',outcome),('qmp-result.json',{'running':True,'status':'running'})]:
                (qmp/name).write_text(json.dumps(value))
            quoted=str(path).replace("'","''")
            self.invoke("$script:f=Read-Pr248Json '"+quoted+"';" + r'''
              function Get-Pr248DesktopContext {return $script:f['desktop']}
              function Get-Pr248ProcessSnapshot([int]$ProcessId){return $script:f['processes'][[string]$ProcessId]}
              function Get-NetTCPConnection {return [pscustomobject]@{OwningProcess=13;LocalAddress='127.0.0.1';LocalPort=1234;State='Listen'}}
              function Read-Pr248WindowsClockSample {return @{qpf_success=$true;qpf_frequency_dec='10000000';
                qpc_before_success=$true;qpc_before_dec='100';qpc_after_success=$true;qpc_after_dec='200';
                utc_begin='2026-10-14T00:00:00Z';utc_end='2026-10-14T00:00:01Z'}}
              $originalVersion=$PSVersionTable.PSVersion;try {
                $PSVersionTable.PSVersion=[version]'5.1.1';Invoke-Pr248WindowsClockContext $script:f['parameters'];
                $r=Read-Pr248Json ([IO.Path]::Combine($script:f['parameters']['result'],'native-windows-clock-context.json'));
                Assert-Pr248 ($r['status'] -ceq 'complete_context_observations' -and !$r['normative_clock_qualified'] -and
                  !$r['continuous_vm_state_exclusion_proved'] -and !$r['provider_precision_proved']) 'invented control completion promoted';
                $script:f['desktop']['user_name']='codex';Invoke-Pr248WindowsClockContext $script:f['parameters'];
                $r=Read-Pr248Json ([IO.Path]::Combine($script:f['parameters']['result'],'native-windows-clock-context.json'));
                Assert-Pr248 ($r['status'] -ceq 'complete_context_observations') 'actual lowercase account label rejected';
                $script:f['desktop']['session']=0;$rejected=$false;
                try {Invoke-Pr248WindowsClockContext $script:f['parameters']} catch {$rejected=$true};
                $r=Read-Pr248Json ([IO.Path]::Combine($script:f['parameters']['result'],'native-windows-clock-context.json'));
                Assert-Pr248 ($rejected -and $r['status'] -ceq 'INCONCLUSIVE' -and $r['error'] -ceq 'Owned live desktop unavailable') 'external service context silently treated as guest desktop'
              } finally {$PSVersionTable.PSVersion=$originalVersion}
            ''')


if __name__ == '__main__':
    unittest.main()
