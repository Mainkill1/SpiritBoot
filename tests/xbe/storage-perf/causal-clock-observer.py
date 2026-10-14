#!/usr/bin/env python3
"""Actual unbuffered read/EOF witnesses for complete owned serial markers.

These receipts support conditional interval arithmetic. Source/binary causal
proof and normative short-request calibration remain separate requirements.
"""
import hashlib
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import time
from datetime import datetime


class MarkerWitnesses:
    def __init__(self, expected_markers, identity):
        self.expected_markers = expected_markers
        self.identity = identity
        self.witnesses = []
        self.markers = []
        self.offset = 0
        self.pending = b''
        self.line_start = 0
        self.end_seen = False
        self.arm = None

    def appearance(self, start, finish, witness):
        absent = next((row for row in reversed(self.witnesses)
                       if row['eof'] and row['offset_after'] <= start
                       and row['index'] < witness['index']),None)
        if absent is None:raise ValueError('complete marker lacks actual pre-prefix EOF absence')
        return {'marker_byte_span':[start,finish],'absence_witness_index':absent['index'],
                'presence_witness_index':witness['index'],
                'host_bracket_ns':[absent['start_ns'],witness['end_ns']]}

    def consume(self, witness, block):
        if (witness['index'] != len(self.witnesses) or witness['operation'] != 'read'
                or type(witness['start_ns']) is not int or type(witness['end_ns']) is not int
                or witness['start_ns'] < 0 or witness['end_ns'] < witness['start_ns']
                or (self.witnesses and witness['start_ns'] < self.witnesses[-1]['end_ns'])
                or witness['offset_before'] != self.offset
                or witness['offset_after'] != self.offset+len(block)
                or witness['requested_bytes'] <= 0 or len(block) > witness['requested_bytes']
                or witness['returned_bytes'] != len(block) or witness['eof'] != (not block)
                or witness['sha256'] != hashlib.sha256(block).hexdigest()):
            raise ValueError('read syscall timestamp/offset/EOF/data witness differs')
        for key, extent in (('identity_before',witness['offset_before']),('identity_after',witness['offset_after'])):
            actual = witness[key]
            if (any(actual[field] != self.identity[field] for field in ('device','inode'))
                    or actual['size'] < extent):
                raise ValueError('serial file replaced or truncated')
        if not block and witness['identity_before']['size'] > self.offset:
            raise ValueError('EOF cannot witness unread available bytes')
        self.witnesses.append(witness)
        self.offset += len(block)
        self.pending += block
        while b'\n' in self.pending:
            line, self.pending = self.pending.split(b'\n',1)
            line += b'\n'
            start, finish = self.line_start, self.line_start+len(line)
            self.line_start = finish
            if b'STORAGE-CAUSAL-MARKER' in line:
                match = re.fullmatch(rb'(?:# )?STORAGE-CAUSAL-MARKER index=([0-9]+) sample=([0-9]+) edge=(begin|end)\r?\n',line)
                if not match or self.end_seen:
                    raise ValueError('partial/foreign/post-END marker framing')
                index, sample, edge = int(match[1]), int(match[2]), match[3].decode()
                if (index != len(self.markers) or index >= self.expected_markers
                        or sample != index//2 or edge != ('begin' if index%2==0 else 'end')):
                    raise ValueError('duplicate or reordered marker')
                self.markers.append({'index':index,'sample':sample,'edge':edge,
                                     **self.appearance(start,finish,witness)})
            if b'STORAGE-CAUSAL-ARM' in line:
                if (self.arm is not None or self.markers
                        or line not in (f'# STORAGE-CAUSAL-ARM samples={self.expected_markers//2}\n'.encode(),
                                        f'STORAGE-CAUSAL-ARM samples={self.expected_markers//2}\n'.encode())):
                    raise ValueError('duplicate, reordered or foreign guest ARM framing')
                self.arm = self.appearance(start,finish,witness)
            if b'STORAGE-CAUSAL-END' in line:
                if self.end_seen:
                    raise ValueError('duplicate causal END')
                self.end_seen = True
        if len(self.pending) > 4096:
            raise ValueError('unbounded or unframed serial line')

    def finish(self):
        if len(self.markers) != self.expected_markers or b'STORAGE-CAUSAL-' in self.pending:
            raise ValueError('incomplete or partial causal marker capture')
        return self.markers


def validate_serial_snapshot(actual, expected, offset):
    if (any(actual[field] != expected[field] for field in ('device','inode','pid','start_time','exe_path'))
            or actual['path_device'] != expected['device'] or actual['path_inode'] != expected['inode']
            or actual['offset'] != offset or actual['size'] < offset
            or actual['prefix_equal'] is not True or actual['foreign_writer_pids']):
        raise ValueError('owned file/prefix/cursor/PID lifetime or foreign writer differs')
    writers = actual['writer_fds']
    if (len(writers) != 1 or writers[0]['fd'] != expected['writer_fd']
            or writers[0]['device'] != expected['device'] or writers[0]['inode'] != expected['inode']
            or writers[0]['regular'] is not True or writers[0]['access_mode'] not in ('write','read-write')
            or writers[0]['position'] < actual['size']
            or writers[0]['position'] < expected.get('writer_previous_position',0)):
        raise ValueError('owned serial writer descriptor/flags/position differs')


def process_start(proc):
    return int((proc/'stat').read_text().rsplit(')',1)[1].split()[19])


def writable_descriptors(proc, identity):
    rows = []
    for path in (proc/'fd').iterdir():
        try:
            actual = path.stat()
            if (actual.st_dev,actual.st_ino) != (identity['device'],identity['inode']):
                continue
            values = dict(line.split(':',1) for line in (proc/'fdinfo'/path.name).read_text().splitlines())
            flags = int(values['flags'].strip(),8)
            mode = flags & os.O_ACCMODE
            if mode not in (os.O_WRONLY,os.O_RDWR):
                continue
            rows.append({'fd':int(path.name),'device':actual.st_dev,'inode':actual.st_ino,
                         'position':int(values['pos']),'flags_octal':oct(flags),
                         'access_mode':'write' if mode==os.O_WRONLY else 'read-write',
                         'regular':stat.S_ISREG(actual.st_mode),'path':os.readlink(path)})
        except FileNotFoundError:
            # Transient descriptor disappearance is retained by the scan's
            # limited scope, never converted to continuous writer exclusion.
            continue
    return rows


def serial_snapshot(fd, path, proc, expected, prefix, *, validate=True):
    begin = time.monotonic_ns()
    actual, named = os.fstat(fd), os.stat(path,follow_symlinks=False)
    if not stat.S_ISREG(actual.st_mode) or not stat.S_ISREG(named.st_mode):
        raise ValueError('serial descriptor/path must be regular files')
    foreign = []; scan_errors = []
    uid = os.getuid()
    for candidate in Path('/proc').iterdir():
        if not candidate.name.isdigit() or candidate.name==str(expected['pid']):
            continue
        try:
            if candidate.stat().st_uid == uid and writable_descriptors(candidate,expected):
                foreign.append(int(candidate.name))
        except FileNotFoundError:
            continue
        except PermissionError as error:
            scan_errors.append({'pid':int(candidate.name),'error':str(error)})
    value = {'device':actual.st_dev,'inode':actual.st_ino,'path_device':named.st_dev,
             'path_inode':named.st_ino,'size':actual.st_size,'offset':os.lseek(fd,0,os.SEEK_CUR),
             'prefix_equal':os.pread(fd,len(prefix),0)==prefix,'pid':expected['pid'],
             'start_time':process_start(proc),'exe_path':os.readlink(proc/'exe'),
             'writer_fds':writable_descriptors(proc,expected),'foreign_writer_pids':foreign,
             'foreign_writer_scan_complete':not scan_errors,'foreign_writer_scan_errors':scan_errors,
             'snapshot_start_ns':begin,'snapshot_end_ns':time.monotonic_ns(),
             'foreign_writer_scan_scope':'visible same-user /proc descriptors at snapshots; not continuous exclusion'}
    if validate:validate_serial_snapshot(value,expected,len(prefix))
    return value


def capture_read(fd, path, proc, expected, prefix, index, *, observation=None):
    """Timestamp exactly one actual os.read, outside parsing or buffered I/O."""
    witness = observation if observation is not None else {}
    witness.update(index=index,operation='read',requested_bytes=65536)
    before = serial_snapshot(fd,path,proc,expected,prefix,validate=False)
    witness['snapshot_before'] = before
    validate_serial_snapshot(before,expected,len(prefix))
    start = time.monotonic_ns()
    block = os.read(fd,65536)
    end = time.monotonic_ns()
    witness.update(start_ns=start,end_ns=end,offset_before=before['offset'],
                   offset_after=os.lseek(fd,0,os.SEEK_CUR),returned_bytes=len(block),eof=not block,
                   sha256=hashlib.sha256(block).hexdigest(),block_hex=block.hex(),
                   identity_before={key:before[key] for key in ('device','inode','size')})
    after = serial_snapshot(fd,path,proc,expected,prefix+block,validate=False)
    witness['snapshot_after'] = after
    witness['identity_after'] = {key:after[key] for key in ('device','inode','size')}
    validate_serial_snapshot(after,expected,len(prefix)+len(block))
    expected['writer_previous_position'] = after['writer_fds'][0]['position']
    return witness,block


def validate_primary_serial_route(route, command, source):
    serial = []; words = iter(command)
    for word in words:
        if word=='-serial':
            serial.append(next(words,None))
        elif word.startswith('-serial='):
            serial.append(word[len('-serial='):])
        elif word=='-chardev' or 'logfile=' in word:
            raise ValueError('unqualified explicit chardev/logfile substitution')
    rows = [row for row in route['query_chardev'] if row.get('label')=='serial0']
    if (serial != ['file:'+str(source)] or route['parent_type']!='child<lpc47m157>'
            or not route['parent_path'].startswith('/machine/')
            or route['parent_chardev0']!='serial0' or route['child_chardev']!='serial0'
            or route['backend_type']!='child<chardev-file>' or len(rows)!=1
            or rows[0].get('filename')!='file' or rows[0].get('frontend-open') is not True):
        raise ValueError('actual primary serial file backend/QOM route differs')


def unique_json(pairs):
    value = {}
    for key,item in pairs:
        if key in value:raise ValueError('duplicate JSON field')
        value[key] = item
    return value


PARENT = '/machine/peripheral/pr248-native-causal-uart'


def recipe_specs(stage):
    if stage not in ('initial','final'):raise ValueError('unknown diagnostic stage')
    return {'status':('query-status',{}),
            'parent-type':('qom-get',{'path':PARENT,'property':'type'}),
            'children':('qom-list',{'path':PARENT}),
            'parent-link':('qom-get',{'path':PARENT,'property':'chardev0'}),
            'child-link':('qom-get',{'path':PARENT+'/serial0','property':'chardev'}),
            'backends':('qom-list',{'path':'/chardevs'}),
            'chardev':('query-chardev',{})}


def read_recipe_stage(result, stage, remote_root=None):
    result = Path(result);remote_root = str(result) if remote_root is None else remote_root
    records = [];responses = {};previous = None
    for name,(command,arguments) in recipe_specs(stage).items():
        identity = 'causal-qmp-'+stage+'-'+name
        directories = [path for path in (result/'diagnostics').iterdir() if path.name.endswith('-'+identity)]
        if len(directories)!=1:raise ValueError('missing or duplicate exact QMP recipe: '+identity)
        directory = directories[0];values = {};hashes = {}
        for filename in ('request.json','result.json','qmp-result.json'):
            data = (directory/filename).read_bytes()
            values[filename] = json.loads(data,object_pairs_hook=unique_json)
            hashes[filename] = hashlib.sha256(data).hexdigest()
        request,completed,response = values['request.json'],values['result.json'],values['qmp-result.json']
        if (request.get('Id')!=identity or request.get('Type')!='qmp'
                or request.get('QmpCommand')!=command or request.get('QmpArguments')!=arguments
                or any(request.get(flag) is not False for flag in ('PauseBefore','PauseAfter','ResumeDuring'))
                or completed.get('Id')!=identity or completed.get('Type')!='qmp'
                or completed.get('Status')!='completed' or completed.get('Detail') is not None
                or completed.get('Directory')!=str(Path(remote_root)/'diagnostics'/directory.name)
                or completed.get('Artifacts')!=['qmp-result.json']):
            raise ValueError('actual QMP recipe/outcome/owned result directory differs')
        before,after = datetime.fromisoformat(completed['StartedUtc']),datetime.fromisoformat(completed['EndedUtc'])
        if before.tzinfo is None or after.tzinfo is None or after<before or (previous is not None and before<previous):
            raise ValueError('QMP recipe execution order/timestamp rollback differs')
        previous = after
        responses[name] = response
        records.append({'id':identity,'request':request,'result':completed,'response':response,
                        'relative_directory':str(Path('diagnostics')/directory.name),'artifact_sha256':hashes})
    if [row.get('type') for row in responses['children'] if row.get('name')=='serial0'] != ['child<serial>']:
        raise ValueError('actual owned serial0 child type differs')
    matching = [row for row in responses['backends'] if row.get('name')=='serial0']
    if len(matching)!=1:raise ValueError('unique primary serial backend missing')
    primary = [row for row in responses['chardev'] if row.get('label')=='serial0']
    if len(primary)!=1:raise ValueError('unique primary serial chardev missing')
    route = {'parent_path':PARENT,'parent_type':'child<'+responses['parent-type']+'>',
             'parent_chardev0':responses['parent-link'],'child_chardev':responses['child-link'],
             'backend_type':matching[0]['type'],'query_chardev':primary}
    status = responses['status']
    if (status.get('running') is not True or status.get('status')!='running'
            or ('singlestep' in status and status['singlestep'] is not False)):
        raise ValueError('owned VM QMP state is not ordinary running')
    return {'stage':stage,'records':records,'route':route,'status':status,
            'single_step_observed':status.get('singlestep'),
            'result_read_end_ns':time.monotonic_ns()}


def listening_qmp_fd(proc, command):
    endpoints = [];words = iter(command)
    for word in words:
        if word=='-qmp':endpoints.append(next(words,None))
        elif word.startswith('-qmp='):endpoints.append(word[5:])
    if len(endpoints)!=1:raise ValueError('unique runner-owned QMP endpoint missing')
    match = re.fullmatch(r'tcp:127\.0\.0\.1:([0-9]+),server=on,wait=off',endpoints[0] or '')
    if not match or not 0<int(match[1])<65536:raise ValueError('exact runner-owned loopback QMP endpoint differs')
    socket_fds = {}
    for path in (proc/'fd').iterdir():
        try:
            target = os.readlink(path)
            if target.startswith('socket:['):socket_fds.setdefault(target[8:-1],[]).append(int(path.name))
        except FileNotFoundError:continue
    address = '0100007F:'+format(int(match[1]),'04X')
    rows = []
    for line in (proc/'net/tcp').read_text().splitlines()[1:]:
        fields = line.split()
        if fields[1]==address and fields[3]=='0A' and fields[9] in socket_fds:
            rows.extend({'endpoint':endpoints[0],'fd':descriptor,'socket_inode':int(fields[9]),
                         'local_address_hex':fields[1],'state':fields[3],'uid':int(fields[7]),'raw_tcp_row':line.strip()}
                        for descriptor in socket_fds[fields[9]])
    if len(rows)!=1:raise ValueError('exact owned xemu QMP listening descriptor missing or ambiguous')
    return rows[0]


def qmp_listener_identity(row):
    return {key:row[key] for key in ('endpoint','fd','socket_inode','local_address_hex','state','uid')}






def replay_witnesses(serial, witnesses, expected_markers, identity):
    recorder = MarkerWitnesses(expected_markers,identity)
    for witness in witnesses:
        before,after = witness['offset_before'],witness['offset_after']
        if before < 0 or after < before or after > len(serial):
            raise ValueError('witness references unavailable observed bytes')
        recorder.consume(witness,serial[before:after])
    if recorder.offset != len(serial):raise ValueError('unread observed serial tail')
    return recorder.finish()




def pinned_module(path, pin, name):
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if digest != pin:raise ValueError('owned observer dependency source hash differs: '+str(path))
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid',type=int,required=True);parser.add_argument('--package',required=True)
    parser.add_argument('--result',required=True);parser.add_argument('--expected-job',required=True)
    parser.add_argument('--expected-xemu-sha256',required=True);parser.add_argument('--expected-config-sha256',required=True)
    parser.add_argument('--expected-guard-sha256',required=True);parser.add_argument('--expected-parser-sha256',required=True)
    args = parser.parse_args();result = Path(args.result).resolve()
    summary = {'schema_version':1,'purpose':'causal_clock_diagnostic_only','storage_operations':0,
               'performance_acceptance_eligible':False,'normative_clock_qualified':False,
               'source_binary_causal_proof':'requires independent reviewed packet and exact live route',
               'continuous_foreign_writer_exclusion':None,'receiver_complete':False,'error':None,
               'observer_pid':os.getpid(),'target_pid':args.pid,'clock_source':'host CLOCK_MONOTONIC, not CPU time'}
    receipt = result/'native-causal-clock-observer.json'
    def save():receipt.write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    save();fd = None;current = None
    try:
        package = Path(args.package).resolve()
        guard = pinned_module(package/'clock-observer.py',args.expected_guard_sha256,'frozen_causal_target_guard')
        native = pinned_module(package/'storage_native_runner.py',args.expected_parser_sha256,'frozen_causal_parser')
        _,_,proc,binding = guard.capture_binding(args)
        summary['binding'] = binding;save()
        source = result/'native-serial.log'
        summary['initial_qmp_listener'] = listening_qmp_fd(proc,binding['command']);save()
        initial = read_recipe_stage(result,'initial')
        summary['initial_recipes'] = initial;save()
        validate_primary_serial_route(initial['route'],binding['command'],source)
        fd = os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
        actual = os.fstat(fd)
        expected = {'device':actual.st_dev,'inode':actual.st_ino,'pid':args.pid,
                    'start_time':binding['start_time_before'],'exe_path':binding['exe_path']}
        writers = writable_descriptors(proc,expected);summary['initial_writer_fds'] = writers;save()
        if len(writers)!=1:raise ValueError('exact unique owned writable serial FD missing')
        expected.update(writer_fd=writers[0]['fd'],writer_previous_position=0)
        summary['serial_identity'] = dict(expected);save()
        recorder = MarkerWitnesses(100,expected);prefix = b'';began = time.monotonic()
        info = time.get_clock_info('monotonic')
        summary['host_clock'] = {'implementation':info.implementation,'resolution_seconds':info.resolution,
                                 'monotonic':info.monotonic,'adjustable':info.adjustable}
        if not info.monotonic or info.adjustable:raise ValueError('host clock is not coherent monotonic')
        # Managed QMP recipes complete before this external observer starts.
        # A fresh EOF after reading their receipts anchors the guest ARM.
        with (result/'native-causal-read-witnesses.jsonl').open('x') as ledger, (result/'native-causal-observed.log').open('xb') as serial:
            while not recorder.end_seen and time.monotonic()-began < 150:
                current = {}
                try:
                    witness,block = capture_read(fd,source,proc,expected,prefix,len(recorder.witnesses),observation=current)
                    ledger.write(json.dumps(witness,separators=(',',':'),allow_nan=False)+'\n');ledger.flush()
                    serial.write(block);serial.flush();prefix += block
                    recorder.consume(witness,block)
                except Exception as error:
                    current['error'] = str(error)
                    ledger.write(json.dumps(current,separators=(',',':'),allow_nan=False)+'\n');ledger.flush();raise
                if not block:time.sleep(.001)
            if not recorder.end_seen:raise TimeoutError('owned causal observer deadline')
        summary['markers'] = recorder.finish()
        summary['arm'] = recorder.arm
        if recorder.arm is None or initial['result_read_end_ns'] >= recorder.arm['host_bracket_ns'][0]:
            raise ValueError('initial managed QMP receipts do not precede guest ARM absence')
        summary['final_qmp_listener'] = listening_qmp_fd(proc,binding['command'])
        if qmp_listener_identity(summary['final_qmp_listener']) != qmp_listener_identity(summary['initial_qmp_listener']):
            raise ValueError('runner-owned listening QMP descriptor changed during capture')
        summary['final_serial_snapshot'] = serial_snapshot(fd,source,proc,expected,prefix)
        summary['start_time_at_end'] = process_start(proc);summary['exe_path_at_end'] = os.readlink(proc/'exe')
        if summary['start_time_at_end'] != expected['start_time'] or summary['exe_path_at_end'] != expected['exe_path']:
            raise ValueError('owned target lifetime differs at end')
        schedule = [{'requested_us':span,'busy':busy} for _ in range(5)
                    for span in (1000,10000,100000,1000000,5000000) for busy in (0,1)]
        parsed = native.parse_causal_clock(prefix.decode(errors='replace'),schedule)
        rows = []
        for sample in parsed['samples']:
            begin,end = summary['markers'][sample['index']*2:sample['index']*2+2]
            row = dict(sample);row.update(begin_host_ns=begin['host_bracket_ns'],end_host_ns=end['host_bracket_ns'])
            row['counter_rate_bounds'] = {}
            for counter in ('qpc','rdtsc'):
                try:
                    row['counter_rate_bounds'][counter] = native.derive_causal_rate(sample['begin'][counter],sample['end'][counter],begin['host_bracket_ns'],end['host_bracket_ns'])
                except ValueError as error:
                    row['counter_rate_bounds'][counter] = {'status':'INCONCLUSIVE','error':str(error),'normative_clock_qualified':False}
            rows.append(row)
        summary.update(receiver_complete=True,samples=rows,observed_serial_bytes=len(prefix),
                       observed_serial_sha256=hashlib.sha256(prefix).hexdigest(),read_witnesses=len(recorder.witnesses),
                       maximum_observed_read_start_gap_ns=max((b['start_ns']-a['start_ns'] for a,b in zip(recorder.witnesses,recorder.witnesses[1:])),default=None),
                       poll_gap_is_backend_bound=False,clock_qualification='INCONCLUSIVE; conditional bounds do not prove short-rate stability or continuous writer exclusion')
        save()
    except Exception as error:
        summary['error'] = str(error)
        if current is not None:summary['last_read_observation'] = current
        save();raise
    finally:
        if fd is not None:os.close(fd)


if __name__=='__main__':main()
