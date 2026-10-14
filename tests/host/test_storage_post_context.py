"""Read-only post-END clock construction faults; no VM or HTTP execution."""
import copy,importlib.util,os,pathlib,tempfile,types,unittest
from unittest import mock
SOURCE=pathlib.Path(__file__).parents[2]/'tests/xbe/storage-perf/storage-post-context.py'
def subject():
 spec=importlib.util.spec_from_file_location('storage_post_context',SOURCE);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
class StoragePostContextTests(unittest.TestCase):
 def test_observed_btrfs_subvolume_device_requires_exact_root_mount_inode_links_and_stable_fd(self):
  m=subject();record={'path':'/usr/lib/libc.so.6','mapped_device':'00:1a','mapped_inode':'102507','before_fd':{'st_dev':27,'st_ino':102507,'st_mode':33261,'st_size':2006328,'st_mtime_ns':1,'st_ctime_ns':2},'after_fd':{'st_dev':27,'st_ino':102507,'st_mode':33261,'st_size':2006328,'st_mtime_ns':1,'st_ctime_ns':2},'map_files_links':[{'address':'1000-2000','target':'/usr/lib/libc.so.6'}]};rows=[{'address':'1000-2000','path':'/usr/lib/libc.so.6','device':'00:1a','inode':'102507'}];mount='29 2 0:26 / / rw,relatime shared:1 - btrfs /dev/nvme0n1p5 rw,ssd,subvolid=5,subvol=/\n'
  self.assertEqual(m.libc_binding(record,rows,mount),'btrfs-root-subvolume-map-files')
  for bad_mount in [mount.replace('btrfs','ext4'),mount.replace('0:26','0:99'),mount.replace('subvolid=5','subvolid=6'),mount.replace('subvol=/','subvol=/foreign'),mount+'30 29 0:30 / /usr rw - tmpfs tmpfs rw\n',mount+mount]:
   with self.subTest(mount=bad_mount),self.assertRaises(ValueError):m.libc_binding(record,rows,bad_mount)
  for key,value in [('st_ino',102508),('st_dev',os.makedev(1,27)),('st_size',2006329),('st_mode',16877)]:
   changed=copy.deepcopy(record);changed['after_fd'][key]=value
   with self.subTest(stat=key),self.assertRaises(ValueError):m.libc_binding(changed,rows,mount)
  for links in [[],[{'address':'foreign','target':record['path']}],[{'address':'1000-2000','target':'/foreign/libc.so.6'}],record['map_files_links']*2]:
   changed=copy.deepcopy(record);changed['map_files_links']=links
   with self.subTest(links=links),self.assertRaises(ValueError):m.libc_binding(changed,rows,mount)
 def test_failed_mapping_stat_binding_retains_all_actual_observations(self):
  m=subject();real=os.fstat
  def mismatch(fd):
   actual=real(fd);fields={key:getattr(actual,key) for key in ('st_dev','st_ino','st_mode','st_size','st_mtime_ns','st_ctime_ns')};fields['st_dev']+=1;return types.SimpleNamespace(**fields)
  with mock.patch.object(m.os,'fstat',side_effect=mismatch):value=m.capture_clock_context(pathlib.Path('/proc')/str(os.getpid()))
  self.assertIn('libc_file',value['errors']);self.assertIsNone(value['libc_file']);observed=value['libc_file_observations']
  self.assertEqual(observed['before_fd'],observed['after_fd']);self.assertFalse(observed['device_equals_maps']);self.assertTrue(observed['inode_equals_maps']);self.assertTrue(observed['file_unchanged']);self.assertTrue(observed['sha256']);self.assertTrue(value['target_mountinfo'])
  with self.assertRaises(ValueError):m.validate_clock_context(value)
 def test_actual_clock_context_preserves_kernel_observations_without_secrets(self):
  self.assertTrue(SOURCE.exists(),'owned post context source missing');m=subject();observed=m.capture_clock_context(pathlib.Path('/proc')/str(os.getpid()))
  self.assertGreater(observed['monotonic_reads_ns'][1],observed['monotonic_reads_ns'][0]);self.assertEqual(observed['target_time_namespace'],observed['observer_time_namespace'])
  self.assertEqual(observed['target_boot_id'],observed['observer_boot_id']);self.assertIn(observed['target_seccomp'],(0,1,2));self.assertEqual(set(observed['interposition_variables_present']),{'LD_PRELOAD','LD_AUDIT'})
  self.assertTrue(observed['libc_mappings']);self.assertTrue(observed['vdso_mappings']);self.assertIsNone(observed['target_vdso_bytes_sha256'])
  self.assertTrue(observed['libc_file']['sha256']);self.assertTrue(all('value' not in k for k in observed['interposition_variables_present']))
 def test_exact_construction_context_rejects_namespace_seccomp_interposition_and_mapping_faults(self):
  self.assertTrue(SOURCE.exists(),'owned post context source missing');m=subject();observed=m.capture_clock_context(pathlib.Path('/proc')/str(os.getpid()));observed['target_seccomp']=0
  self.assertTrue(m.validate_clock_context(observed))
  faults=[('target_boot_id','foreign'),('target_time_namespace','time:[foreign]'),('target_seccomp',2),('target_seccomp',False),('monotonic_reads_ns',[5,4]),('monotonic_reads_ns',[5,5]),('libc_mappings',[]),('vdso_mappings',[])]
  for key,value in faults:
   changed=copy.deepcopy(observed);changed[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):m.validate_clock_context(changed)
  for name in ('LD_PRELOAD','LD_AUDIT'):
   changed=copy.deepcopy(observed);changed['interposition_variables_present'][name]=True
   with self.subTest(variable=name),self.assertRaises(ValueError):m.validate_clock_context(changed)
  for key,value in [('monotonic',False),('adjustable',True),('implementation','foreign')]:
   changed=copy.deepcopy(observed);changed['clock'][key]=value
   with self.subTest(clock=key),self.assertRaises(ValueError):m.validate_clock_context(changed)
  for key in ('device','inode','path'):
   changed=copy.deepcopy(observed);changed['libc_mappings'][0][key]='foreign'
   with self.subTest(mapping=key),self.assertRaises(ValueError):m.validate_clock_context(changed)
 def test_environment_records_presence_only_and_missing_namespace_fails_closed(self):
  self.assertTrue(SOURCE.exists(),'owned post context source missing');m=subject()
  with tempfile.TemporaryDirectory(prefix='pr248-clock-proc-') as work:
   proc=pathlib.Path(work);(proc/'root/proc/sys/kernel/random').mkdir(parents=True);(proc/'ns').mkdir();(proc/'status').write_text('Seccomp:\t0\n');(proc/'environ').write_bytes(b'LD_PRELOAD=do-not-print-secret\0OTHER=another-secret\0');(proc/'maps').write_text((pathlib.Path('/proc/self/maps')).read_text());(proc/'root/proc/sys/kernel/random/boot_id').write_text(pathlib.Path('/proc/sys/kernel/random/boot_id').read_text())
   observed=m.capture_clock_context(proc)
   self.assertTrue(observed['interposition_variables_present']['LD_PRELOAD']);self.assertNotIn('do-not-print-secret',str(observed));self.assertIn('target_time_namespace',observed['errors'])
   with self.assertRaises(ValueError):m.validate_clock_context(observed)
 def test_post_shutdown_state_is_observed_without_claiming_measured_pause(self):
  self.assertTrue(SOURCE.exists(),'owned post context source missing');m=subject()
  for value in ({'status':'running','running':True},{'status':'shutdown','running':False},{'status':'paused','running':False}):self.assertEqual(m.validate_post_state(value),value)
  for value in ({'status':'shutdown','running':True},{'status':'prelaunch','running':False},{'status':'running','running':False},{'status':'running','running':True,'singlestep':True},{'status':'running','running':True,'singlestep':None}):
   with self.subTest(value=value),self.assertRaises(ValueError):m.validate_post_state(value)
if __name__=='__main__':unittest.main()
