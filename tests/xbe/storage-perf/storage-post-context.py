#!/usr/bin/env python3
"""Read-only owned context after strict END, before the job's final quit."""
import argparse,hashlib,importlib.util,json,os,pathlib,re,stat,time

def load(path,name,pin):
 if hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()!=pin:raise ValueError('pinned helper differs '+name)
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def libc_binding(record,rows,mountinfo):
 before,after=record['before_fd'],record['after_fd'];name=record['path']
 if (before!=after or not stat.S_ISREG(after['st_mode']) or after['st_size']<=0
     or str(after['st_ino'])!=record['mapped_inode'] or not rows
     or any((row['path'],row['device'],row['inode'])!=(name,record['mapped_device'],record['mapped_inode']) for row in rows)):raise ValueError('mapped libc inode/file changed/differs')
 actual=(os.major(after['st_dev']),os.minor(after['st_dev']));mapped=tuple(int(x,16) for x in record['mapped_device'].split(':'))
 if actual==mapped:return 'maps-and-stat-device-inode-equal'
 # Linux maps uses the backing superblock device; Btrfs getattr instead uses
 # its root anon_dev. This fallback is limited to the observed Deck root route.
 mounts=[]
 for raw in mountinfo.splitlines():
  fields=raw.split();separator=fields.index('-')
  if len(fields)<separator+4:raise ValueError('malformed actual mountinfo')
  mount=fields[4]
  if name==mount or name.startswith(mount.rstrip('/')+'/'):mounts.append((len(mount),fields,separator))
 if not mounts:raise ValueError('mapped libc covering mount missing')
 longest=max(item[0] for item in mounts);covering=[item for item in mounts if item[0]==longest]
 if len(covering)!=1:raise ValueError('mapped libc covering mount ambiguous')
 _,fields,separator=covering[0];options=fields[separator+3].split(',');mountdev=tuple(int(x) for x in fields[2].split(':'))
 links=record['map_files_links'];expected={row['address'] for row in rows}
 if (fields[3:5]!=['/','/'] or fields[separator+1]!='btrfs' or not fields[separator+2].startswith('/dev/')
     or mountdev!=mapped or actual[0]!=0 or mapped[0]!=0 or actual[1]<=0 or mapped[1]<=0
     or 'subvolid=5' not in options or 'subvol=/' not in options
     or len(links)!=len(rows) or {link.get('address') for link in links}!=expected
     or any(link.get('target')!=name or 'error' in link for link in links)):raise ValueError('unexplained mapped libc/stat device difference')
 return 'btrfs-root-subvolume-map-files'

def capture_clock_context(proc):
 proc=pathlib.Path(proc);info=time.get_clock_info('monotonic')
 value={'schema_version':1,'purpose':'post_END_clock_construction_context','errors':{},'clock':{'implementation':info.implementation,'monotonic':info.monotonic,'adjustable':info.adjustable,'resolution_seconds':info.resolution},'target_vdso_bytes_sha256':None,'continuous_observation':False,'constructor_branch_observed_directly':False,'construction_assumptions':['trusted kernel CLOCK_MONOTONIC availability is stable from owned process construction through END','mapped libc/vDSO implement the ordinary clock route; vDSO bytes are not read','recorded post context and frozen launch construction hold during the measured interval; no unrecorded intervention']}
 def observe(name,function):
  try:value[name]=function()
  except (OSError,ValueError,StopIteration) as error:value[name]=None;value['errors'][name]=str(error)
 observe('monotonic_reads_ns',lambda:[time.clock_gettime_ns(time.CLOCK_MONOTONIC),time.clock_gettime_ns(time.CLOCK_MONOTONIC)])
 observe('observer_boot_id',lambda:pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip())
 observe('target_boot_id',lambda:(proc/'root/proc/sys/kernel/random/boot_id').read_text().strip())
 observe('observer_time_namespace',lambda:os.readlink('/proc/self/ns/time'))
 observe('target_time_namespace',lambda:os.readlink(proc/'ns/time'))
 observe('target_mountinfo',lambda:(proc/'mountinfo').read_text())
 observe('target_seccomp',lambda:int(next(line for line in (proc/'status').read_text().splitlines() if line.startswith('Seccomp:')).split()[1]))
 def variables():
  names={word.split(b'=',1)[0] for word in (proc/'environ').read_bytes().split(b'\0') if word}
  return {name:name.encode() in names for name in ('LD_PRELOAD','LD_AUDIT')}
 observe('interposition_variables_present',variables)
 def mappings():
  rows=[]
  for raw in (proc/'maps').read_text().splitlines():
   fields=raw.split(None,5)
   if len(fields)<5:raise ValueError('malformed actual process mapping')
   rows.append({'address':fields[0],'permissions':fields[1],'offset':fields[2],'device':fields[3],'inode':fields[4],'path':fields[5] if len(fields)==6 else '', 'raw':raw})
  return rows
 observe('maps',mappings)
 rows=value.get('maps') or [];value['libc_mappings']=[row for row in rows if re.search(r'/libc(?:-[0-9.]+)?\.so(?:\.6)?$',row['path'])];value['vdso_mappings']=[row for row in rows if row['path']=='[vdso]']
 def libc_file():
  record={};value['libc_file_observations']=record
  identities={(row['path'],row['device'],row['inode']) for row in value['libc_mappings']}
  if len(identities)!=1:raise ValueError('unique mapped libc identity missing')
  name,device,inode=next(iter(identities));path=proc/'root'/name.lstrip('/')
  record.update(path=name,read_path=str(path),mapped_device=device,mapped_inode=inode)
  record['map_files_links']=[]
  for row in value['libc_mappings']:
   link={'address':row['address']}
   try:link['target']=os.readlink(proc/'map_files'/row['address'])
   except OSError as error:link.update(target=None,error=str(error))
   record['map_files_links'].append(link)
  def fields(item):return {key:getattr(item,key) for key in ('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns')}
  with path.open('rb') as stream:
   before=os.fstat(stream.fileno());record['before_fd']=fields(before);digest=hashlib.sha256()
   for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
   after=os.fstat(stream.fileno());record['after_fd']=fields(after);record['sha256']=digest.hexdigest()
  mapped_device='{:02x}:{:02x}'.format(os.major(after.st_dev),os.minor(after.st_dev))
  record.update(actual_device=mapped_device,actual_inode=str(after.st_ino),device_equals_maps=mapped_device==device,inode_equals_maps=str(after.st_ino)==inode,file_unchanged=all(getattr(before,key)==getattr(after,key) for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')))
  method=libc_binding(record,value['libc_mappings'],value.get('target_mountinfo') or '');record['binding_method']=method
  return {'path':name,'read_path':str(path),'device':mapped_device,'inode':str(after.st_ino),'mapped_device':device,'mapped_inode':inode,'binding_method':method,'bytes':after.st_size,'mtime_ns':after.st_mtime_ns,'ctime_ns':after.st_ctime_ns,'sha256':digest.hexdigest()}
 observe('libc_file',libc_file);return value

def validate_clock_context(value):
 clock=value.get('clock',{});reads=value.get('monotonic_reads_ns')
 if (value.get('errors') or clock.get('implementation')!='clock_gettime(CLOCK_MONOTONIC)' or clock.get('monotonic') is not True or clock.get('adjustable') is not False
     or not isinstance(reads,list) or len(reads)!=2 or any(type(x) is not int or x<=0 for x in reads) or reads[1]<=reads[0]
     or not value.get('target_boot_id') or value['target_boot_id']!=value.get('observer_boot_id')
     or not value.get('target_time_namespace') or value['target_time_namespace']!=value.get('observer_time_namespace')
     or type(value.get('target_seccomp')) is not int or value['target_seccomp']!=0
     or value.get('interposition_variables_present')!={'LD_PRELOAD':False,'LD_AUDIT':False}):raise ValueError('required clock construction observations missing/differ')
 libc=value.get('libc_file');rows=value.get('libc_mappings');vdso=value.get('vdso_mappings')
 if (not isinstance(libc,dict) or not re.fullmatch('[0-9a-f]{64}',libc.get('sha256','')) or not rows or not vdso
     or any(row.get('path')!=libc.get('path') or row.get('device')!=libc.get('mapped_device') or row.get('inode')!=libc.get('mapped_inode') for row in rows)
     or len(vdso)!=1 or vdso[0].get('path')!='[vdso]'):raise ValueError('actual libc/vDSO mapping identity missing/differs')
 if libc_binding(value['libc_file_observations'],rows,value['target_mountinfo'])!=libc.get('binding_method'):raise ValueError('actual libc binding method differs')
 return True

def validate_post_state(value):
 if (not isinstance(value,dict) or value.get('status') not in ('running','shutdown','paused')
     or value.get('running') is not (value['status']=='running')
     or ('singlestep' in value and value['singlestep'] is not False)):raise ValueError('unexpected post END VM state')
 return value

def main():
 p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True)
 for name in ('package','result','expected-job','expected-device','expected-xemu-sha256','expected-config-sha256','expected-guard-sha256','expected-post-helper-sha256','expected-recorder-sha256','expected-parser-sha256','expected-case'):p.add_argument('--'+name,required=True)
 a=p.parse_args();package=pathlib.Path(a.package).resolve();result=pathlib.Path(a.result).resolve();receipt=result/'native-storage-post-context.json'
 observed={'schema_version':1,'stage':'post','purpose':'owned_storage_post_END_context','performance_acceptance_eligible':False,'continuous_observation':False,'guard_complete':False,'error':None,'target_pid':a.pid,'started_monotonic_ns':time.monotonic_ns(),'serial_end':{}}
 def save():receipt.write_text(json.dumps(observed,indent=2,allow_nan=False)+'\n')
 save()
 try:
  helper=load(package/'dvd-post-route-observer.py','storage_post_helpers',a.expected_post_helper_sha256)
  raw=helper.serial_end_receipt(result,a.expected_job,observed['serial_end']);save()
  parser=load(package/'storage_native_runner.py','storage_post_parser',a.expected_parser_sha256);parsed=parser.parse_serial(raw)
  if (parsed.get('complete') is not True or set(parsed['cases'])!={a.expected_case} or parsed['cases'][a.expected_case]['status']!='ok' or parsed['metadata'].get('fixture_generation')!='2'):raise ValueError('complete unique successful selected END missing')
  observed['serial_end']['strict_successful_END_verified']=True;observed['heavy_hash_started_monotonic_ns']=time.monotonic_ns();save()
  guard=load(package/'clock-observer.py','storage_post_target',a.expected_guard_sha256);_,_,proc,binding=guard.capture_binding(a);observed['binding']=binding;save();(result/'native-clock-observer-target.json').rename(result/'native-storage-post-target.json')
  observed['clock_context']=capture_clock_context(proc);save();validate_clock_context(observed['clock_context'])
  observed['recorder']=helper.input_receipt(package,'storage-perf.iso',a.expected_recorder_sha256);save()
  for name,pin in [('storage-perf.iso',a.expected_recorder_sha256),('storage_native_runner.py',a.expected_parser_sha256)]:
   rows=[row for row in binding['manifest']['Inputs'] if row.get('Path')==name]
   if len(rows)!=1 or rows[0].get('Verified') is not True or rows[0].get('Sha256')!=pin or rows[0].get('ExpectedSha256')!=pin:raise ValueError('actual manifest input differs '+name)
  state=helper.read_recipe(result,'storage-status-post','query-status',{},str(result));observed['managed_state']=state;observed['post_state']=validate_post_state(state['response']);save()
  query=helper.read_recipe(result,'storage-block-post','query-block',{},str(result));observed['managed_query']=query;observed['actual_route']=helper.validate_media_route(query['response'],package,package/'storage-perf.iso',a.expected_device);save()
  observed.update(start_time_at_end=guard.process_start(proc),exe_path_at_end=os.readlink(proc/'exe'))
  if observed['start_time_at_end']!=binding['start_time_before'] or observed['exe_path_at_end']!=binding['exe_path']:raise ValueError('owned process lifetime changed')
  serial=pathlib.Path(observed['serial_end']['path']);after=serial.stat()
  for field,key in [('st_dev','device'),('st_ino','inode'),('st_size','bytes'),('st_uid','uid'),('st_nlink','nlink'),('st_mtime_ns','mtime_ns'),('st_ctime_ns','ctime_ns')]:
   if getattr(after,field)!=observed['serial_end'][key]:raise ValueError('END serial identity changed during post context')
  if helper.digest(serial)!=observed['serial_end']['sha256']:raise ValueError('END serial bytes changed during post context')
  observed.update(guard_complete=True,ended_monotonic_ns=time.monotonic_ns());save()
 except Exception as error:observed.update(error=str(error),ended_monotonic_ns=time.monotonic_ns());save();raise
if __name__=='__main__':main()
