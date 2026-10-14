#!/usr/bin/env python3
"""Read-only owned fixed-wrapper DVD guard around runner-managed query recipes."""
import argparse,datetime,hashlib,importlib.util,json,os,pathlib,stat,time

def unique_json(pairs):
 value={}
 for key,item in pairs:
  if key in value:raise ValueError('duplicate JSON field')
  value[key]=item
 return value

def read_json(path):return json.loads(pathlib.Path(path).read_bytes(),object_pairs_hook=unique_json)

def digest(path):
 value=hashlib.sha256()
 with pathlib.Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):value.update(block)
 return value.hexdigest()

def input_receipt(package,name,expected,observation=None):
 observed={} if observation is None else observation
 package=pathlib.Path(package).resolve();relative=pathlib.Path(name)
 if relative.is_absolute() or len(relative.parts)!=1 or relative.name in ('','.','..'):raise ValueError('input must be an exact package filename')
 path=package/relative
 observed['path']=str(path)
 if path.is_symlink():raise ValueError('symbolic input is unqualified')
 before=path.stat()
 if not stat.S_ISREG(before.st_mode):raise ValueError('input is not regular')
 measured=digest(path);observed['sha256']=measured;after=path.stat()
 observed.update(device=after.st_dev,inode=after.st_ino,bytes=after.st_size,mtime_ns=after.st_mtime_ns,ctime_ns=after.st_ctime_ns)
 fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
 if measured!=expected or any(getattr(before,key)!=getattr(after,key) for key in fields):raise ValueError('actual input hash/identity differs')
 return observed

def validate_media_route(blocks,package,expected_file,expected_device):
 if not isinstance(blocks,list) or any(not isinstance(row,dict) for row in blocks):raise ValueError('query-block is not an actual block array')
 removable=[row for row in blocks if row.get('removable') is True]
 if len(removable)!=1:raise ValueError('unique declared removable DVD route missing')
 row=removable[0]
 if len([item for item in blocks if item.get('device')==expected_device])!=1:raise ValueError('declared device is not unique')
 inserted=row.get('inserted')
 if not isinstance(inserted,dict) or not isinstance(inserted.get('file'),str):raise ValueError('inserted media file missing')
 package=pathlib.Path(package).resolve();path=pathlib.Path(inserted['file']);actual=(path if path.is_absolute() else package/path).resolve()
 if (row.get('device')!=expected_device or row.get('locked') is not False
     or actual!=pathlib.Path(expected_file).resolve() or actual.parent!=package
     or inserted.get('ro') is not True or inserted.get('drv')!='raw'):
  raise ValueError('actual removable device/file/readonly/backend differs')
 return {'device':row['device'],'actual_inserted_path':str(actual),'raw_block':row}

def read_recipe(result,identity,command,arguments,remote_result):
 result=pathlib.Path(result);matches=[p for p in (result/'diagnostics').iterdir() if p.name.endswith('-'+identity)]
 if len(matches)!=1:raise ValueError('missing or duplicate exact managed recipe '+identity)
 directory=matches[0];hashes={};values={}
 for name in ('request.json','result.json','qmp-result.json'):
  path=directory/name;values[name]=read_json(path);hashes[name]=digest(path)
 request,outcome,response=(values[name] for name in ('request.json','result.json','qmp-result.json'))
 if (request.get('Id')!=identity or request.get('Type')!='qmp' or request.get('QmpCommand')!=command
     or request.get('QmpArguments')!=arguments or any(request.get(flag) is not False for flag in ('PauseBefore','PauseAfter','ResumeDuring'))
     or outcome.get('Id')!=identity or outcome.get('Type')!='qmp' or outcome.get('Status')!='completed'
     or outcome.get('Detail') is not None or outcome.get('Artifacts')!=['qmp-result.json']
     or outcome.get('Directory')!=str(pathlib.Path(remote_result)/'diagnostics'/directory.name)):
  raise ValueError('actual typed recipe/outcome/directory differs')
 before=datetime.datetime.fromisoformat(outcome['StartedUtc']);after=datetime.datetime.fromisoformat(outcome['EndedUtc'])
 if before.tzinfo is None or after.tzinfo is None or after<before:raise ValueError('managed recipe timestamp order differs')
 return {'identity':identity,'request':request,'result':outcome,'response':response,'relative_directory':str(pathlib.Path('diagnostics')/directory.name),'artifact_sha256':hashes}

def main():
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=('initial','final'),required=True);p.add_argument('--pid',type=int,required=True);p.add_argument('--package',required=True);p.add_argument('--result',required=True);p.add_argument('--expected-job',required=True);p.add_argument('--expected-device',required=True);p.add_argument('--expected-xemu-sha256',required=True);p.add_argument('--expected-config-sha256',required=True);p.add_argument('--expected-guard-sha256',required=True);p.add_argument('--expected-recorder-sha256',required=True);p.add_argument('--expected-target-sha256',required=True);a=p.parse_args()
 result=pathlib.Path(a.result).resolve();package=pathlib.Path(a.package).resolve();receipt=result/('native-dvd-'+a.stage+'-guard.json')
 observed={'schema_version':1,'stage':a.stage,'purpose':'owned_DVD_functional_method_only','fixed_media':True,'media_method':'fixed-wrapper','exact_original_media_parity':False,'target_pid':a.pid,'expected_device_hypothesis':a.expected_device,'performance_acceptance_eligible':False,'guard_complete':False,'error':None,'started_monotonic_ns':time.monotonic_ns()}
 def save():receipt.write_text(json.dumps(observed,indent=2,allow_nan=False)+'\n')
 save()
 try:
  path=package/'clock-observer.py'
  if digest(path)!=a.expected_guard_sha256:raise ValueError('owned target guard source differs')
  spec=importlib.util.spec_from_file_location('dvd_target_guard',path);guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
  _,_,proc,binding=guard.capture_binding(a);observed['binding']=binding;save()
  (result/'native-clock-observer-target.json').rename(result/('native-dvd-'+a.stage+'-target.json'))
  manifest=binding['manifest'];observed.update(recorder={},target={});save()
  source=input_receipt(package,'storage-perf.iso',a.expected_recorder_sha256,observation=observed['recorder']);save()
  target=input_receipt(package,'target.iso',a.expected_target_sha256,observation=observed['target']);save()
  for name,pin in [('storage-perf.iso',a.expected_recorder_sha256),('target.iso',a.expected_target_sha256)]:
   rows=[row for row in manifest['Inputs'] if row.get('Path')==name]
   if len(rows)!=1 or rows[0].get('Verified') is not True or rows[0].get('Sha256')!=pin or rows[0].get('ExpectedSha256')!=pin:raise ValueError('actual manifest input differs '+name)
  observed.update(recorder=source,target=target);save()
  query=read_recipe(result,'dvd-qmp-'+a.stage,'query-block',{},str(result));observed['managed_query']=query;save()
  expected_file=package/'storage-perf.iso'
  observed['actual_route']=validate_media_route(query['response'],package,expected_file,a.expected_device);save()
  if a.stage=='final':
   first=read_json(result/'native-dvd-initial-guard.json');observed['initial_guard_sha256']=digest(result/'native-dvd-initial-guard.json')
   if (first.get('guard_complete') is not True or first.get('error') is not None or first['binding']['pid']!=binding['pid']
       or first['binding']['start_time_before']!=binding['start_time_before'] or first['binding']['exe_path']!=binding['exe_path']
       or first['binding']['command']!=binding['command'] or first['recorder']!=source or first['target']!=target
       or first['actual_route']!=observed['actual_route'] or first.get('fixed_media') is not True or first.get('media_method')!='fixed-wrapper' or first.get('exact_original_media_parity') is not False):raise ValueError('initial/final owned lifetime or media identity differs')
   times=[first['managed_query']['result']['EndedUtc'],query['result']['StartedUtc']]
   moments=[datetime.datetime.fromisoformat(value) for value in times]
   if moments!=sorted(moments):raise ValueError('managed fixed-media observation order differs')
  observed.update(start_time_at_end=guard.process_start(proc),exe_path_at_end=os.readlink(proc/'exe'))
  if observed['start_time_at_end']!=binding['start_time_before'] or observed['exe_path_at_end']!=binding['exe_path']:raise ValueError('owned process lifetime changed')
  observed.update(guard_complete=True,ended_monotonic_ns=time.monotonic_ns());save()
 except Exception as error:
  observed.update(error=str(error),ended_monotonic_ns=time.monotonic_ns());save();raise
if __name__=='__main__':main()
