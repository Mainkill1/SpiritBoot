"""Invented syscall/counter faults for the independently owned diagnostic."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT/'tests/xbe/storage-perf'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CausalClockTests(unittest.TestCase):
    def native(self):
        return load(ROOT/'tools/storage_native_runner.py', 'causal_native')

    def observer(self):
        path = FIXTURE/'causal-clock-observer.py'
        self.assertTrue(path.exists(), 'causal unbuffered observer missing')
        return load(path, 'causal_observer')

    def serial(self):
        return ('# STORAGE-CAUSAL-READY fixture_generation=2 diagnostic_revision=3 samples=1 markers=2 purpose=causal_counter_brackets deadline_counter=qpc qpc_hz=1000000\n'
                '# STORAGE-CAUSAL-ARM samples=1\n'
                '# STORAGE-CAUSAL-MARKER index=0 sample=0 edge=begin\n'
                '# STORAGE-CAUSAL-MARKER index=1 sample=0 edge=end\n'
                '# STORAGE-CAUSAL-BOUND marker=0 counter=qpc before=100 after=110\n'
                '# STORAGE-CAUSAL-BOUND marker=0 counter=rdtsc before=1000 after=1010\n'
                '# STORAGE-CAUSAL-BOUND marker=1 counter=qpc before=1110 after=1120\n'
                '# STORAGE-CAUSAL-BOUND marker=1 counter=rdtsc before=2010 after=2020\n'
                '# STORAGE-CAUSAL-SAMPLE index=0 requested_us=1000 busy=1\n'
                '# STORAGE-CAUSAL-END samples=1 markers=2 storage_operations=0\n')

    def test_parser_binds_complete_ordered_counter_records_and_schedule(self):
        module = self.native()
        self.assertTrue(hasattr(module, 'parse_causal_clock'), 'causal protocol parser missing')
        parsed = module.parse_causal_clock(self.serial(), [{'requested_us':1000,'busy':1}])
        self.assertTrue(parsed['complete'])
        self.assertEqual(parsed['samples'][0]['begin']['qpc'], [100,110])
        self.assertEqual(parsed['samples'][0]['end']['rdtsc'], [2010,2020])
        faults = {
            'partial': self.serial().rsplit('\n',1)[0],
            'duplicate': self.serial().replace('index=1 sample=0 edge=end','index=0 sample=0 edge=end'),
            'reordered': self.serial().replace('index=0 sample=0 edge=begin','index=1 sample=0 edge=begin'),
            'duplicate-field': self.serial().replace('before=100 ', 'before=999 before=100 '),
            'rollback': self.serial().replace('before=1110 after=1120','before=90 after=1120'),
            'inside-rollback': self.serial().replace('before=100 after=110','before=100 after=90'),
            'counter-substitution': self.serial().replace('counter=rdtsc','counter=qpc',1),
            'failed': self.serial()+'not ok 1 - declared failure\n',
            'post-end': self.serial()+'# STORAGE-CAUSAL-MARKER index=2 sample=1 edge=begin\n',
            'short-busy': self.serial().replace('before=1110 after=1120','before=1109 after=1120'),
            'schedule': self.serial().replace('requested_us=1000','requested_us=999'),
            'missing-arm': self.serial().replace('# STORAGE-CAUSAL-ARM samples=1\n',''),
        }
        for name, serial in faults.items():
            with self.subTest(fault=name), self.assertRaises(ValueError):
                module.parse_causal_clock(serial,[{'requested_us':1000,'busy':1}])

    def test_rate_bounds_use_exact_counter_and_host_endpoint_arithmetic(self):
        module = self.native()
        self.assertTrue(hasattr(module, 'derive_causal_rate'), 'causal exact rate bounds missing')
        result = module.derive_causal_rate([10,20],[50,60],[100,190],[300,390])
        self.assertEqual(result['counter_delta_bounds'],[30,50])
        self.assertEqual(result['host_delta_ns_bounds'],[110,290])
        self.assertEqual(result['rate_lower'],{'numerator':3000000000,'denominator':29})
        self.assertEqual(result['rate_upper'],{'numerator':5000000000,'denominator':11})
        self.assertFalse(result['normative_clock_qualified'])
        self.assertEqual(result['causal_proof_status'],'not_established_by_arithmetic')
        for args in (([0,10],[20,30],[0,100],[80,160]),
                     ([20,10],[50,60],[100,190],[300,390]),
                     ([10,20],[15,30],[100,190],[300,390])):
            with self.subTest(args=args),self.assertRaises(ValueError):module.derive_causal_rate(*args)

    def witness(self, index, offset, block, start, end, **changes):
        identity={'device':1,'inode':2,'size':offset+len(block)}
        row={'index':index,'operation':'read','start_ns':start,'end_ns':end,
             'offset_before':offset,'offset_after':offset+len(block),'requested_bytes':65536,
             'returned_bytes':len(block),'eof':not block,'sha256':hashlib.sha256(block).hexdigest(),
             'identity_before':dict(identity),'identity_after':dict(identity)}
        row.update(changes)
        return row

    def test_unbuffered_eof_and_complete_presence_supply_actual_witness_endpoints(self):
        module=self.observer(); recorder=module.MarkerWitnesses(2,{'device':1,'inode':2})
        prefix=b'# STORAGE-CAUSAL-MARKER index=0 sample=0 edge=begin'
        first=prefix+b'\n'; second=b'# STORAGE-CAUSAL-MARKER index=1 sample=0 edge=end\n'
        recorder.consume(self.witness(0,0,b'',100,140),b'')
        recorder.consume(self.witness(1,0,prefix,150,160),prefix)
        recorder.consume(self.witness(2,len(prefix),b'',170,180),b'')
        recorder.consume(self.witness(3,len(prefix),b'\n',190,200),b'\n')
        recorder.consume(self.witness(4,len(first),b'',300,340),b'')
        recorder.consume(self.witness(5,len(first),second,350,390),second)
        observed=recorder.finish()
        self.assertEqual(observed[0]['host_bracket_ns'],[100,200])
        self.assertEqual(observed[0]['absence_witness_index'],0,'partial EOF must not tighten absence')
        self.assertEqual(observed[0]['presence_witness_index'],3)
        self.assertEqual(observed[0]['marker_byte_span'],[0,len(first)])
        self.assertEqual(observed[1]['host_bracket_ns'],[300,390])
        self.assertEqual(observed[1]['absence_witness_index'],4)

    def test_read_witness_accepts_bytes_appended_inside_its_actual_syscall_interval(self):
        module=self.observer();recorder=module.MarkerWitnesses(1,{'device':1,'inode':2})
        recorder.consume(self.witness(0,0,b'',100,140),b'')
        marker=b'# STORAGE-CAUSAL-MARKER index=0 sample=0 edge=begin\n'
        row=self.witness(1,0,marker,150,190)
        row['identity_before']['size']=0
        recorder.consume(row,marker)
        self.assertEqual(recorder.finish()[0]['host_bracket_ns'],[100,190])

    def test_witness_rejects_partial_missing_eof_identity_cursor_time_and_order_faults(self):
        module=self.observer(); marker=b'# STORAGE-CAUSAL-MARKER index=0 sample=0 edge=begin\n'
        faults=[{'returned_bytes':len(marker)-1},{'eof':True},{'offset_after':1},
                {'start_ns':90},{'identity_after':{'device':1,'inode':3,'size':len(marker)}},
                {'identity_after':{'device':1,'inode':2,'size':len(marker)-1}},
                {'sha256':'0'*64}]
        for changes in faults:
            with self.subTest(fault=changes),self.assertRaises(ValueError):
                recorder=module.MarkerWitnesses(2,{'device':1,'inode':2})
                recorder.consume(self.witness(0,0,b'',100,140),b'')
                recorder.consume(self.witness(1,0,marker,150,190,**changes),marker)
        for mode in ('no-eof','partial','duplicate','reordered','unread'):
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                recorder=module.MarkerWitnesses(2,{'device':1,'inode':2})
                if mode!='no-eof':recorder.consume(self.witness(0,0,b'',100,140),b'')
                block=marker[:-1] if mode=='partial' else marker
                if mode=='reordered':block=marker.replace(b'index=0',b'index=1')
                recorder.consume(self.witness(0 if mode=='no-eof' else 1,0,block,150,190),block)
                if mode=='duplicate':recorder.consume(self.witness(2,len(block),marker,200,220),marker)
                recorder.finish()

    def test_runtime_file_and_owned_writer_snapshots_reject_changed_identity_lifetime_and_writers(self):
        module=self.observer()
        expected={'device':1,'inode':2,'pid':123,'start_time':456,'exe_path':'/owned/xemu','writer_fd':9}
        snapshot={'device':1,'inode':2,'path_device':1,'path_inode':2,'size':20,'offset':10,
                  'prefix_equal':True,'pid':123,'start_time':456,'exe_path':'/owned/xemu',
                  'writer_fds':[{'fd':9,'device':1,'inode':2,'position':20,'access_mode':'write','regular':True}],
                  'foreign_writer_pids':[]}
        module.validate_serial_snapshot(snapshot,expected,10)
        for key,value in [('inode',3),('path_inode',3),('size',9),('offset',9),
                          ('prefix_equal',False),('start_time',457),('exe_path','/foreign/xemu'),
                          ('foreign_writer_pids',[999]),('writer_fds',[])]:
            changed=copy.deepcopy(snapshot);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):module.validate_serial_snapshot(changed,expected,10)

    def test_actual_read_witnesses_retain_syscall_offsets_eof_and_inode_failures(self):
        module=self.observer()
        self.assertTrue(hasattr(module,'capture_read'),'actual unbuffered syscall capture missing')
        with tempfile.TemporaryDirectory(prefix='pr248-causal-read-') as work:
            path=Path(work)/'owned-serial.log'
            writer=os.open(path,os.O_CREAT|os.O_WRONLY|os.O_APPEND,0o600)
            reader=os.open(path,os.O_RDONLY)
            try:
                identity=os.fstat(reader)
                proc=Path('/proc')/str(os.getpid())
                expected={'device':identity.st_dev,'inode':identity.st_ino,'pid':os.getpid(),
                          'start_time':module.process_start(proc),'exe_path':os.readlink(proc/'exe'),
                          'writer_fd':writer,'writer_previous_position':0}
                witness,block=module.capture_read(reader,path,proc,expected,b'',0)
                self.assertEqual(block,b'');self.assertTrue(witness['eof'])
                self.assertEqual(witness['offset_before'],0);self.assertEqual(witness['offset_after'],0)
                self.assertGreaterEqual(witness['end_ns'],witness['start_ns'])
                os.write(writer,b'owned bytes\n')
                witness,block=module.capture_read(reader,path,proc,expected,b'',1)
                self.assertEqual(block,b'owned bytes\n');self.assertFalse(witness['eof'])
                self.assertEqual(witness['offset_after'],len(block))
                os.lseek(reader,0,os.SEEK_SET)
                with self.assertRaises(ValueError):module.capture_read(reader,path,proc,expected,block,2)
                os.lseek(reader,len(block),os.SEEK_SET)
                moved=path.with_name('original');path.rename(moved);path.write_bytes(block)
                with self.assertRaises(ValueError):module.capture_read(reader,path,proc,expected,block,2)
                path.unlink();moved.rename(path)
                os.ftruncate(writer,0)
                with self.assertRaises(ValueError):module.capture_read(reader,path,proc,expected,block,2)
            finally:
                os.close(reader);os.close(writer)

    def test_primary_qmp_serial_route_cannot_be_replaced_by_a_logfile_receipt(self):
        module=self.observer()
        self.assertTrue(hasattr(module,'validate_primary_serial_route'),'primary serial backend route gate missing')
        source='/owned/results/native-serial.log'
        route={'parent_path':'/machine/peripheral-anon/device[7]','parent_type':'child<lpc47m157>',
               'parent_chardev0':'serial0','child_chardev':'serial0','backend_type':'child<chardev-file>',
               'query_chardev':[{'label':'serial0','filename':'file','frontend-open':True}]}
        command=['./xemu','-serial','file:'+source,'-device','lpc47m157']
        module.validate_primary_serial_route(route,command,source)
        for key,value in [('parent_chardev0','logger0'),('child_chardev','logger0'),
                          ('backend_type','child<chardev-null>'),('parent_type','child<other>'),
                          ('query_chardev',[{'label':'serial0','filename':'file','frontend-open':False}]),
                          ('query_chardev',[{'label':'serial0','filename':'null','frontend-open':True}])]:
            changed=copy.deepcopy(route);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):module.validate_primary_serial_route(changed,command,source)
        for args in (['./xemu','-serial','file:/foreign'],command+['-serial','file:'+source],
                     command+['-chardev','null,id=logger0,logfile='+source]):
            with self.subTest(args=args),self.assertRaises(ValueError):module.validate_primary_serial_route(route,args,source)

    def test_post_read_rejection_retains_actual_data_and_syscall_metadata(self):
        module=self.observer()
        with tempfile.TemporaryDirectory(prefix='pr248-causal-retention-') as work:
            path=Path(work)/'owned.log';writer=os.open(path,os.O_CREAT|os.O_WRONLY,0o600)
            os.write(writer,b'actual measured bytes\n');reader=os.open(path,os.O_RDONLY)
            proc=Path('/proc')/str(os.getpid());actual=os.fstat(reader)
            expected={'device':actual.st_dev,'inode':actual.st_ino,'pid':os.getpid(),
                      'start_time':module.process_start(proc),'exe_path':os.readlink(proc/'exe'),'writer_fd':writer}
            original=os.read;observation={}
            def replaced(fd,length):
                block=original(fd,length);path.rename(path.with_name('old'));path.write_bytes(block);return block
            try:
                with mock.patch.object(module.os,'read',side_effect=replaced),self.assertRaises(ValueError):
                    module.capture_read(reader,path,proc,expected,b'',0,observation=observation)
                self.assertEqual(observation['returned_bytes'],len(b'actual measured bytes\n'))
                self.assertEqual(observation['sha256'],hashlib.sha256(b'actual measured bytes\n').hexdigest())
                self.assertGreaterEqual(observation['end_ns'],observation['start_ns'])
                self.assertNotEqual(observation['snapshot_after']['path_inode'],expected['inode'])
            finally:os.close(reader);os.close(writer)


    def test_reanalysis_replays_the_exact_observed_serial_bytes_and_eof_ledger(self):
        module=self.observer()
        self.assertTrue(hasattr(module,'replay_witnesses'),'bound read-witness replay missing')
        first=b'# STORAGE-CAUSAL-MARKER index=0 sample=0 edge=begin\n'
        second=b'# STORAGE-CAUSAL-MARKER index=1 sample=0 edge=end\n'
        rows=[self.witness(0,0,b'',100,140),self.witness(1,0,first,150,190),
              self.witness(2,len(first),b'',300,340),self.witness(3,len(first),second,350,390)]
        markers=module.replay_witnesses(first+second,rows,2,{'device':1,'inode':2})
        self.assertEqual(markers[1]['host_bracket_ns'],[300,390])
        for mode in ('changed-bytes','unread-tail','missing-eof','truncated-ledger'):
            raw=first+second;changed=copy.deepcopy(rows)
            if mode=='changed-bytes':raw=raw.replace(b'begin',b'xxxxx')
            if mode=='unread-tail':raw+=b'unread'
            if mode=='missing-eof':changed.pop(2)
            if mode=='truncated-ledger':changed.pop()
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                module.replay_witnesses(raw,changed,2,{'device':1,'inode':2})


    def test_supported_recipe_stage_binds_exact_commands_outputs_and_failed_results(self):
        module=self.observer()
        self.assertTrue(hasattr(module,'read_recipe_stage'),'supported runner QMP recipe binding missing')
        with tempfile.TemporaryDirectory(prefix='pr248-causal-recipes-') as work:
            result=Path(work)/'owned-run';diagnostics=result/'diagnostics';diagnostics.mkdir(parents=True)
            specs=module.recipe_specs('initial')
            parent='/machine/peripheral/pr248-native-causal-uart'
            # Exact observed V263 query-status shape; singlestep is absent.
            values={'status':{'status':'running','running':True},
                    'parent-type':'lpc47m157','children':[{'name':'serial0','type':'child<serial>'}],
                    'parent-link':'serial0','child-link':'serial0',
                    'backends':[{'name':'serial0','type':'child<chardev-file>'}],
                    'chardev':[{'label':'serial0','filename':'file','frontend-open':True}]}
            for index,(name,(command,args)) in enumerate(specs.items()):
                identity='causal-qmp-initial-'+name;directory=diagnostics/('20261014-0000'+str(index)+'-'+identity);directory.mkdir()
                (directory/'request.json').write_text(json.dumps({'Id':identity,'Type':'qmp','QmpCommand':command,'QmpArguments':args,
                     'PauseBefore':False,'PauseAfter':False,'ResumeDuring':False}))
                (directory/'result.json').write_text(json.dumps({'Id':identity,'Type':'qmp','Status':'completed',
                     'StartedUtc':f'2026-10-14T00:00:{index*2:02d}+00:00','EndedUtc':f'2026-10-14T00:00:{index*2+1:02d}+00:00',
                     'Directory':str(directory),'Detail':None,'Artifacts':['qmp-result.json']}))
                (directory/'qmp-result.json').write_text(json.dumps(values[name]))
            stage=module.read_recipe_stage(result,'initial')
            module.validate_primary_serial_route(stage['route'],['./xemu','-serial','file:/owned/log'],'/owned/log')
            self.assertEqual(stage['route']['parent_path'],parent)
            self.assertIsNone(stage['single_step_observed'])
            self.assertNotIn('singlestep',stage['status'])
            self.assertGreater(stage['result_read_end_ns'],0)
            original_route=stage['route']
            chardev_path=next(diagnostics.glob('*-causal-qmp-initial-chardev'))/'qmp-result.json'
            primary=values['chardev'][0]
            for peer in (35076,39999):
                chardev_path.write_text(json.dumps([primary,{'label':'compat_monitor0',
                    'filename':f'tcp:127.0.0.1:34303,server=on <-> 127.0.0.1:{peer}',
                    'frontend-open':True}]))
                self.assertEqual(module.read_recipe_stage(result,'initial')['route'],original_route)
            for changed in ({'label':'foreign','filename':'file','frontend-open':True},
                            {'label':'serial0','filename':'null','frontend-open':True},
                            {'label':'serial0','filename':'file','frontend-open':False}):
                chardev_path.write_text(json.dumps([changed]))
                with self.subTest(primary=changed),self.assertRaises(ValueError):
                    changed_stage=module.read_recipe_stage(result,'initial')
                    module.validate_primary_serial_route(changed_stage['route'],['./xemu','-serial','file:/owned/log'],'/owned/log')
            chardev_path.write_text(json.dumps([primary,primary]))
            with self.assertRaises(ValueError):module.read_recipe_stage(result,'initial')
            chardev_path.write_text(json.dumps(values['chardev']))
            directory=next(diagnostics.glob('*-causal-qmp-initial-status'))
            status_path=directory/'qmp-result.json'
            for status in ({'status':'paused','running':False},
                           {'status':'running','running':False},
                           {'status':'running','running':'true'},
                           {'status':'running'},
                           {'status':'running','running':True,'singlestep':True},
                           {'status':'running','running':True,'singlestep':None}):
                status_path.write_text(json.dumps(status))
                with self.subTest(status=status),self.assertRaises(ValueError):
                    module.read_recipe_stage(result,'initial')
            status_path.write_text(json.dumps({'status':'running','running':True,'singlestep':False}))
            self.assertIs(module.read_recipe_stage(result,'initial')['single_step_observed'],False)
            status_path.write_text(json.dumps(values['status']))
            original=(directory/'result.json').read_text();bad=json.loads(original);bad['Status']='failed'
            (directory/'result.json').write_text(json.dumps(bad))
            with self.assertRaises(ValueError):module.read_recipe_stage(result,'initial')
            (directory/'result.json').write_text(original)
            (directory/'qmp-result.json').write_text('{"running":false,"running":true}')
            with self.assertRaisesRegex(ValueError,'duplicate'):module.read_recipe_stage(result,'initial')

    def test_actual_loopback_listening_endpoint_is_bound_to_owned_descriptor_inode(self):
        module=self.observer();proc=Path('/proc')/str(os.getpid())
        with socket.socket() as server:
            server.bind(('127.0.0.1',0));server.listen(1)
            endpoint=f'tcp:127.0.0.1:{server.getsockname()[1]},server=on,wait=off'
            command=['./xemu','-qmp',endpoint]
            row=module.listening_qmp_fd(proc,command)
            self.assertEqual(row['fd'],server.fileno())
            self.assertEqual(row['uid'],os.getuid())
            self.assertGreater(row['socket_inode'],0)
            self.assertTrue(hasattr(module,'qmp_listener_identity'),'stable owned listener identity missing')
            changed=copy.deepcopy(row);changed['raw_tcp_row']='changed unrelated kernel table formatting'
            self.assertEqual(module.qmp_listener_identity(row),module.qmp_listener_identity(changed))
            for key in ('endpoint','fd','socket_inode','local_address_hex','state','uid'):
                changed=copy.deepcopy(row);changed[key]=str(changed[key])+'changed'
                self.assertNotEqual(module.qmp_listener_identity(row),module.qmp_listener_identity(changed))
            with self.assertRaises(ValueError):module.listening_qmp_fd(proc,command+['-qmp',endpoint])
            duplicate=os.dup(server.fileno())
            try:
                with self.assertRaises(ValueError):module.listening_qmp_fd(proc,command)
            finally:os.close(duplicate)

    @unittest.skipUnless(shutil.which('cc'),'actual causal C fault test requires host compiler')
    def test_actual_guest_brackets_enclose_each_mock_emission_in_both_counter_domains(self):
        source=FIXTURE/'causal-clock.c'
        self.assertTrue(source.exists(),'owned causal guest fixture missing')
        with tempfile.TemporaryDirectory(prefix='pr248-causal-c-') as work:
            executable=Path(work)/'causal-clock-mock'
            subprocess.run(['cc','-std=gnu11','-O0','-I'+str(FIXTURE/'host-mock'),'-I'+str(FIXTURE),
                            str(source),str(FIXTURE/'host-mock/metrology-mock.c'),'-o',str(executable)],
                           check=True,capture_output=True,text=True)
            raw=subprocess.run([str(executable)],check=True,capture_output=True,text=True).stdout
            schedule=[{'requested_us':span,'busy':busy} for _ in range(5)
                      for span in (1000,10000,100000,1000000,5000000) for busy in (0,1)]
            parsed=self.native().parse_causal_clock(raw,schedule)
            emissions=[]
            for line in raw.splitlines():
                if line.startswith('MOCK-CAUSAL-EMISSION '):
                    emissions.append(dict(word.split('=',1) for word in line.split()[1:]))
            self.assertEqual(len(emissions),100)
            for emission in emissions:
                sample=parsed['samples'][int(emission['index'])//2]
                edge=sample['begin' if int(emission['index'])%2==0 else 'end']
                for counter in ('qpc','rdtsc'):
                    self.assertLessEqual(edge[counter][0],int(emission[counter]))
                    self.assertGreaterEqual(edge[counter][1],int(emission[counter]))


if __name__=='__main__':unittest.main()
