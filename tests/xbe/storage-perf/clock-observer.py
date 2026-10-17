#!/usr/bin/env python3
"""Owned PID diagnostic: exact runner runtime bindings and monotonic markers."""
import argparse,json,pathlib,time,os,re,hashlib

def sha(path):
 digest=hashlib.sha256()
 with pathlib.Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
 return digest.hexdigest()

def process_start(proc):
 return int((proc/'stat').read_text().rsplit(')',1)[1].split()[19])

def validate_target_binding(observed,expected):
 package=pathlib.Path(observed['package']);result=pathlib.Path(observed['result'])
 launch,manifest,report=observed['launch'],observed['manifest'],observed['report']
 if (launch['job']!=expected['job_id'] or manifest['JobId']!=expected['job_id']
     or launch['runId']!=result.name or not expected['job_id'].startswith('pr248-native-')):
  raise ValueError('observer exact owned job/run identity differs')
 if (observed['pid']!=observed['launcher_pid'] or not observed['target_uids']
     or any(uid!=observed['uid'] for uid in observed['target_uids'])
     or observed['start_time_before']<=0 or observed['start_time_after']!=observed['start_time_before']):
  raise ValueError('observer exact owned PID/UID/lifetime differs')
 if (observed['exe_path']!=str(package/'xemu') or observed['cwd']!=str(package)
     or observed['exe_sha256']!=expected['emulator_sha256']):
  raise ValueError('observer exact owned mapped executable differs')
 for name,pin in [('xemu',expected['emulator_sha256']),('xemu.toml',expected['config_sha256'])]:
  rows=[x for x in manifest['Inputs'] if x['Path']==name]
  if len(rows)!=1 or rows[0].get('Verified') is not True or rows[0].get('Sha256')!=pin or rows[0].get('ExpectedSha256')!=pin:
   raise ValueError('observer actual pinned input differs: '+name)
 effective=str(result/'diagnostics/run-state/effective-live.toml')
 if (report['Status'] not in ['prepared','complete'] or report['ConfigSourcePath']!=str(package/'xemu.toml')
     or report['ConfigSha256']!=expected['config_sha256'] or report['EffectiveConfigPath']!=effective
     or observed['effective_config_sha256']!=report['EffectiveConfigSha256']):
  raise ValueError('observer exact runner-isolated config/hash differs')
 arguments=[];configured=[];source=iter(launch['arguments'])
 for word in source:
  if word=='-config_path':configured.append(next(source,None))
  elif word.startswith('-config_path='):configured.append(word[13:])
  else:arguments.append(word)
 if configured!=[str(package/'xemu.toml')]:raise ValueError('observer declared source config differs')
 if observed['command']!=['./xemu']+arguments+['-config_path',effective]:
  raise ValueError('observer actual argv differs from exact runner isolation transform')
 return True

def capture_binding(a):
 package=pathlib.Path(a.package).resolve();result=pathlib.Path(a.result).resolve();proc=pathlib.Path('/proc')/str(a.pid)
 observed={'schema_version':2,'package':str(package),'result':str(result),'pid':a.pid,'uid':os.getuid(),
           'observer_pid':os.getpid(),'expected':{'job_id':a.expected_job,'emulator_sha256':a.expected_xemu_sha256,
           'config_sha256':a.expected_config_sha256},'settings_changed':False,'binding_validated':False}
 receipt=result/'native-clock-observer-target.json'
 def save():receipt.write_text(json.dumps(observed,indent=2)+'\n')
 try:
  observed['start_time_before']=process_start(proc);save()
  observed['command']=[x.decode(errors='replace') for x in (proc/'cmdline').read_bytes().split(b'\0') if x]
  observed['exe_path']=os.readlink(proc/'exe');observed['cwd']=os.readlink(proc/'cwd')
  observed['target_uids']=[int(x) for x in next(line for line in (proc/'status').read_text().splitlines() if line.startswith('Uid:')).split()[1:]];save()
  observed['exe_sha256']=sha(proc/'exe')
  observed['effective_config_sha256']=sha(result/'diagnostics/run-state/effective-live.toml');save()
  observed['launch']=json.loads((result/'launch.json').read_text())
  observed['manifest']=json.loads((result/'input-manifest.json').read_text())
  observed['report']=json.loads((result/'diagnostics/run-state/report.json').read_text())
  pids=[int(line.split('=',1)[1]) for line in (result/'native-host-controls.txt').read_text().splitlines() if line.startswith('pid=')]
  if len(pids)!=1:raise ValueError('owned launcher PID receipt missing or duplicated')
  observed['launcher_pid']=pids[0];observed['start_time_after']=process_start(proc);save()
  validate_target_binding(observed,observed['expected']);observed['binding_validated']=True;save()
 except Exception as error:
  observed['error']=str(error);save();raise
 return package,result,proc,observed

def main():
 p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True);p.add_argument('--package',required=True);p.add_argument('--result',required=True)
 p.add_argument('--expected-job',required=True);p.add_argument('--expected-xemu-sha256',required=True);p.add_argument('--expected-config-sha256',required=True);a=p.parse_args()
 package,result,proc,binding=capture_binding(a);decoded=binding['command']
 info=time.get_clock_info('monotonic');controls={'pid':a.pid,'observer_pid':os.getpid(),'uid':os.getuid(),'command':decoded,'clock':{'implementation':info.implementation,'resolution_seconds':info.resolution,'monotonic':info.monotonic,'adjustable':info.adjustable},'settings_changed':False,'affinity':sorted(os.sched_getaffinity(a.pid)),'nice':os.getpriority(os.PRIO_PROCESS,a.pid),'scheduler':os.sched_getscheduler(a.pid),'topology':[]}
 for cpu in controls['affinity']:
  row={'cpu':cpu}
  for field in ['core_id','physical_package_id','thread_siblings_list']:
   try:row[field]=(pathlib.Path('/sys/devices/system/cpu')/('cpu'+str(cpu))/'topology'/field).read_text().strip()
   except OSError as err:row[field]=None;row[field+'_error']=str(err)
  controls['topology'].append(row)
 (result/'native-clock-observer-controls.json').write_text(json.dumps(controls,indent=2)+'\n')
 source=result/'native-serial.log';deadline=time.monotonic()+150;buffer=b'';consumed=0;index=None;begin=None;samples=[];prev_start=None;gaps=[];error=None
 try:
  with source.open('rb') as stream:
   while time.monotonic()<deadline:
    before=time.monotonic_ns();block=stream.read(1024*1024);after=time.monotonic_ns()
    if prev_start is not None:gaps.append(after-prev_start)
    lower=prev_start if prev_start is not None else before;prev_start=before
    buffer+=block
    while consumed<len(buffer):
     tail=buffer[consumed:]
     if index is None:
      arm=re.search(rb'STORAGE-CLOCK-ARM index=(\d+)\r?\n',tail)
      if arm:
       index=int(arm.group(1));consumed+=arm.end();begin=None;continue
      if b'STORAGE-CLOCK-END samples=50' in tail:
       if len(samples)!=50:raise ValueError('missing unique diagnostic clock samples')
       raise StopIteration
      # Keep bounded partial text while preserving complete future ARM framing.
      if len(tail)>65536:consumed=len(buffer)-65536
      break
     if begin is None:
      at=tail.find(b'<')
      if at<0:break
      begin={'lower_ns':lower,'upper_ns':after};consumed+=at+1;continue
     at=tail.find(b'>')
     if at<0:break
     if index!=len(samples):raise ValueError('nonunique/out-of-order marker index')
     end={'lower_ns':lower,'upper_ns':after};samples.append({'index':index,'begin_receiver_bracket':begin,'end_receiver_bracket':end,'host_wall_ns_estimate':end['upper_ns']-begin['upper_ns'],'host_wall_ns_lower':end['lower_ns']-begin['upper_ns'],'host_wall_ns_upper':end['upper_ns']-begin['lower_ns']});consumed+=at+1;index=None;begin=None
    time.sleep(.001)
   else:raise TimeoutError('owned clock observer deadline')
 except StopIteration:pass
 except Exception as err:error=str(err)
 try:
  binding['start_time_at_sampler_end']=process_start(proc)
  binding['exe_path_at_sampler_end']=os.readlink(proc/'exe')
  binding['same_pid_lifetime_at_sampler_end']=(binding['start_time_at_sampler_end']==binding['start_time_before']
      and binding['exe_path_at_sampler_end']==binding['exe_path'])
  if not binding['same_pid_lifetime_at_sampler_end']:error=error or 'owned diagnostic PID lifetime changed during sampling'
 except Exception as err:
  binding['pid_lifetime_end_error']=str(err);error=error or 'owned diagnostic PID lifetime unconfirmed at sampler end'
 (result/'native-clock-observer-target.json').write_text(json.dumps(binding,indent=2)+'\n')
 payload={'schema_version':1,'purpose':'diagnostic_clock_relation_only','samples':samples,'samples_expected':50,'receiver_complete':len(samples)==50 and error is None,'error':error,'maximum_observed_poll_gap_ns':max(gaps) if gaps else None,'serial_backend_delivery_bound_ns':None,'clock_qualification':'INCONCLUSIVE until unmeasured backend/marker boundary delivery is qualified','performance_acceptance_eligible':False,'storage_operations':0,'clock_source':'host CLOCK_MONOTONIC, not process CPU time'}
 (result/'native-clock-observer.json').write_text(json.dumps(payload,indent=2)+'\n')
 if error:raise RuntimeError(error)

if __name__=='__main__':main()
