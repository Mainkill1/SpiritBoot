# SPDX-License-Identifier: MIT
"""Public synthetic cohort qualification; no native data or host actions."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_join_independent import identity, IDENTITY_TOOLS
from qualify import qualify


def events():
    output = []
    for api in range(1, 65):
        iosb, child, parent = 0x1000 + api*16, 0x3000 + api*16, 0x5000 + api*16
        for kind in (1, 12, 3, 4, 5, 5, 2, 6):
            row = dict.fromkeys(identity.FIELDS, 0)
            row.update(kind=kind, api=api, thread=1)
            if kind in (1, 12, 3, 2, 6): row['iosb'] = iosb
            if kind == 1: row.update(bytes=512, value0=0x42c)
            elif kind == 12: row.update(value0=1, parent=parent)
            elif kind == 3: row.update(child=child, parent=parent, srb=child+4)
            elif kind == 4: row.update(child=child, srb=child+4)
            elif kind == 5:
                row['child'] = parent if output[-1]['kind'] == 5 else child
                if row['child'] == parent: row['iosb'] = iosb
            elif kind == 2: row.update(status=0x103, value0=0, info=512)
            elif kind == 6: row.update(info=512)
            output.append(row)
    return output


def encode(rows, open_api=0, map_open=0):
    lines = [f'identity_meta version=1 events={len(rows)} overflow=0 reentry=0 lost=0 read_fail=0 open_api={open_api} map_open={map_open} map_reentry=0 map_lost=0']
    for seq, original in enumerate(rows, 1):
        row = {**original, 'seq': seq, 'host_ns': seq*1000, 'virtual_ns': seq*1000}
        lines.append('identity_event ' + ' '.join(f'{key}={row[key]:08x}' if key in identity.HEX else f'{key}={row[key]}' for key in sorted(identity.FIELDS)))
    return '\n'.join(lines + [f'identity_end events={len(rows)}'])+'\n'


def prefix():
    lines = ['prefix_meta version=2 descriptors=1 rows=64 translations=1 overflow=0 reentry=0 thread_mismatch=0 invalid_prefix=0 open_api=0 excluded_rows=64',
             'prefix_limits handle=0000042c max_api=64 admitted=64 returned=64 admission_closed=1 range_count=2',
             'prefix_range id=1 start=84001000 end=84055400',
             'prefix_range id=2 start=84069000 end=84069b08',
             'prefix_health allocated_descriptors=1 allocated_instructions=1 descriptor_overflow=0 instruction_overflow=0 row_overflow=0 excluded_overflow=0 max_probe=1 max_excluded_probe=1',
             'prefix_tb id=1 pc=84001000 count=1 generation=1 born_api=1 born_identity_seq=1',
             'prefix_insn tb=1 ordinal=1 pc=84001000 rep=0']
    for api in range(1, 65):
        seq = 1+(api-1)*8
        lines.append(f'prefix_row api={api} identity_seq={seq} tb=1 first=1 last=1 executions=2 begun=2 rep_iterations=0')
        lines.append(f'prefix_excluded api={api} identity_seq={seq} pc=00100000 first=1 last=1 executions=3 begun=3 rep_iterations=0')
    return '\n'.join(lines+['prefix_translation api=1 identity_seq=1 tb=1', 'prefix_end rows=64 excluded_rows=64'])+'\n'


def receipts(start=0, end=600000):
    return '\n'.join(json.dumps(row) for row in [
        {'Id':'synthetic-resume','Status':'completed','EndedUtc':f'1970-01-01T00:00:00.{start:09d}Z'},
        {'Id':'synthetic-pause','Status':'completed','StartedUtc':f'1970-01-01T00:00:00.{end:09d}Z'}])+'\n'


class QualifyTests(unittest.TestCase):
    def check(self, p=None, rows=None, r=None, **meta):
        return qualify(prefix() if p is None else p, encode(events() if rows is None else rows, **meta), receipts() if r is None else r, identity)

    def test_exact_complete_cohort_qualifies(self):
        result = self.check()
        self.assertEqual(result.get('status'), 'qualified')
        self.assertEqual(result.get('selected_calls'), 64)
        self.assertEqual(result.get('successful_callbacks'), 64)
        self.assertEqual(result.get('instruction_starts'), {'total': 320, 'owned': 128, 'excluded': 192})

    def test_callback_before_return_is_a_valid_completed_lifetime(self):
        rows=events(); rows[-1], rows[-2] = rows[-2], rows[-1]
        result=self.check(rows=rows)
        self.assertEqual(result['successful_callbacks'],64)
        self.assertLess(result['calls'][-1]['callback_seq'],result['calls'][-1]['return_seq'])

    def test_iosb_reuse_after_callback_keeps_distinct_api_generations(self):
        rows=events()
        for row in rows:
            if row['iosb']: row['iosb']=0x1000
        result=self.check(rows=rows)
        self.assertEqual(result['successful_callbacks'],64)
        self.assertEqual(len({row['api']for row in result['calls']}),64)

    def test_callback_length_matches_each_requests_actual_size(self):
        rows=events(); rows[-8]['bytes']=65536; rows[-2]['info']=65536; rows[-1]['info']=65536
        result=self.check(rows=rows)
        self.assertEqual(result['calls'][-1]['bytes'],65536)

    def test_translation_reference_cannot_escape_active_api(self):
        text=prefix().replace('born_api=1 born_identity_seq=1','born_api=2 born_identity_seq=1')
        text=text.replace('prefix_translation api=1 identity_seq=1','prefix_translation api=2 identity_seq=1')
        with self.assertRaises(ValueError): self.check(p=text)

    def test_config_drift_cannot_qualify(self):
        for old, new in [('version=2', 'version=1'), ('handle=0000042c', 'handle=00000430'),
                         ('max_api=64', 'max_api=65'), ('end=84055400', 'end=84055401'),
                         ('start=84069000', 'start=84069001'), ('end=84069b08', 'end=84069b09')]:
            with self.subTest(new=new), self.assertRaises(ValueError): self.check(p=prefix().replace(old,new))

    def test_incomplete_admission_cannot_qualify(self):
        with self.assertRaises(ValueError):
            self.check(p=prefix().replace('admitted=64 returned=64 admission_closed=1', 'admitted=63 returned=63 admission_closed=0'))

    def test_identity_admission_handle_mismatch_rejects(self):
        rows = events(); rows[-8]['value0'] = 0x430
        with self.assertRaises(ValueError): self.check(rows=rows)

    def test_all_calls_and_callbacks_must_be_inside_receipts(self):
        for start, end in ((2000,600000), (0,511000), (2000,3000)):
            with self.subTest(start=start,end=end), self.assertRaises(ValueError):
                self.check(r=receipts(start,end))

    def test_missing_duplicate_unknown_failed_or_short_callback_rejects(self):
        changes = []
        rows = events(); rows.pop(); changes.append(rows)
        rows = events(); rows.insert(8, copy.deepcopy(rows[7])); changes.append(rows)
        for key, value in [('iosb',0x99999), ('status',0xc0000001), ('info',511)]:
            rows = events(); rows[-1][key] = value; changes.append(rows)
        for index, rows in enumerate(changes):
            with self.subTest(index=index), self.assertRaises(ValueError): self.check(rows=rows)

    def test_post_drain_callbacks_are_explicitly_unassigned(self):
        rows=events()
        duplicate=copy.deepcopy(rows[-1])
        unknown=copy.deepcopy(rows[-1]); unknown['iosb']=0x99999; unknown['status']=0xc0000001
        rows.extend([duplicate,unknown])
        try:
            result=self.check(rows=rows)
        except ValueError as error:
            self.fail(f'Post-drain callbacks must be counted separately: {error}')
        self.assertEqual(result['successful_callbacks'],64)
        self.assertEqual(result['unassigned_post_drain'],2)
        self.assertEqual(result['selected_drain_seq'],512)

    def test_post_drain_requires_all_native_returns_too(self):
        rows=events(); rows[-1],rows[-2]=rows[-2],rows[-1]
        rows.insert(len(rows)-1,copy.deepcopy(rows[-2]))
        with self.assertRaises(ValueError): self.check(rows=rows)

    def test_unknown_callback_before_full_drain_is_not_ignored(self):
        rows=events(); unknown=copy.deepcopy(rows[7]); unknown['iosb']=0x99999
        rows.insert(8,unknown)
        with self.assertRaises(ValueError): self.check(rows=rows)

    def test_missing_selected_callback_cannot_be_replaced_by_unassigned_event(self):
        rows=events(); rows[-1]['iosb']=0x99999
        with self.assertRaises(ValueError): self.check(rows=rows)

    def test_native_failure_cannot_pass_via_successful_callback(self):
        rows=events(); rows[-2]['status']=0xc0000001
        with self.assertRaises(ValueError): self.check(rows=rows)

    def test_identity_issues_and_uncompleted_lifetimes_reject(self):
        changes=[]
        rows=events(); rows[-3]['iosb']=0x99999; changes.append(rows)
        rows=events(); del rows[-4]; changes.append(rows)  # Child completion omitted.
        rows=events(); del rows[-3]; changes.append(rows)  # Parent completion omitted.
        for index, rows in enumerate(changes):
            with self.subTest(index=index), self.assertRaises(ValueError): self.check(rows=rows)

    def test_open_api_and_mapper_state_rejects(self):
        rows=events(); del rows[-2]
        with self.assertRaises(ValueError): self.check(rows=rows,open_api=1)
        rows=events(); extra=dict.fromkeys(identity.FIELDS,0); extra.update(kind=9,thread=1,request=0x9000)
        rows.append(extra)
        with self.assertRaises(ValueError): self.check(rows=rows,map_open=1)

    def test_missing_call_prefix_and_unknown_references_reject(self):
        p='\n'.join(line for line in prefix().splitlines() if not line.startswith(('prefix_row api=64 ', 'prefix_excluded api=64 ')))+'\n'
        p=p.replace('rows=64','rows=63')
        with self.assertRaises(ValueError): self.check(p=p)
        for old,new in [('api=64 identity_seq=505','api=65 identity_seq=505'),
                        ('api=64 identity_seq=505','api=64 identity_seq=511')]:
            with self.subTest(new=new), self.assertRaises(ValueError): self.check(p=prefix().replace(old,new))

    def test_health_and_truncated_capture_rejects(self):
        with self.assertRaises(ValueError): self.check(p=prefix().replace('row_overflow=0','row_overflow=1'))
        with self.assertRaises(ValueError): self.check(p=prefix().rsplit('prefix_end',1)[0])

    def test_cli_records_input_and_analyzer_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            files={'prefix':prefix(),'identity':encode(events()),'receipts':receipts()}
            command=[sys.executable,str(Path(__file__).with_name('qualify.py')),'--identity-tools',str(IDENTITY_TOOLS),'--output',str(root/'result.json')]
            for key,text in files.items():
                path=root/key; path.write_text(text); command.extend(['--'+key,str(path)])
            result=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((root/'result.json').exists())
            output=json.loads((root/'result.json').read_text())
            self.assertEqual(output['hashes'], {key:hashlib.sha256(text.encode()).hexdigest()for key,text in files.items()})
            self.assertIn('analyze_identity.py',output['tool_hashes'])
            self.assertIn('analyze_prefix.py',output['tool_hashes'])
            self.assertIn('qualify.py',output['tool_hashes'])


if __name__=='__main__': unittest.main()
