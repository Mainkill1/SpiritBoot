# SPDX-License-Identifier: GPL-2.0-only
"""Invented debugger stops only: no socket or native process is contacted."""
import argparse
import json
import struct
import tempfile
import unittest
from pathlib import Path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/storage_allocation_diagnostic'))

from capture_owned_fixture import capture

ROOT=Path(__file__).parent
from storage_allocation_test_support import KERNEL, FIXTURE


class InventedRsp:
    wrong_gate=False;bad_result=False;disconnect=False;cleanup_failure=False
    def __init__(self,host,port,deadline):
        self.breakpoints=set();self.deadline=deadline;self.phase='initial';self.index=0
        self.sock=type('Socket',(),{'close':lambda _:None})()
    def packet(self,command):return 'S05' if command=='?' else 'E01' if self.cleanup_failure else 'OK'
    def stop_reply(self,value):return value
    def regs(self):
        pc={'initial':0xfffffff0,'gate':FIXTURE['entry_address']+int(self.wrong_gate),
            'measure':FIXTURE['sites']['measure_entry']['address'],
            'issue':FIXTURE['sites']['operation_issue']['address'],
            'consumer':FIXTURE['sites']['consumer_verified']['address'],'stepped':0x12200}[self.phase]
        return [0,0,0,0,0x80008000,0x80008100,0,0,pc]
    def run(self,command):
        if self.disconnect and self.phase=='measure':raise EOFError('invented disconnect')
        if command=='s':self.after_step=self.phase;self.phase='stepped'
        elif self.phase=='initial':self.phase='gate'
        elif self.phase=='gate':self.phase='measure'
        elif self.phase=='stepped':
            if self.after_step in ('measure','consumer'):
                if self.after_step=='consumer':self.index+=1
                self.phase='issue'
            else:self.phase='consumer'
        else:raise AssertionError('unexpected invented control sequence')
        return 'S05'
    def read(self,address,size):
        for site in KERNEL['sites']:
            if address==site['address']:return bytes.fromhex(site['entry_bytes'])[:size]
        for site in FIXTURE['sites'].values():
            if address==site['address']:return bytes.fromhex(site['bytes'])[:size]
        if address==FIXTURE['entry_address']:return bytes.fromhex(FIXTURE['entry_bytes'])[:size]
        if address==KERNEL['current_thread_address']:return struct.pack('<I',0x80003000)
        if address==KERNEL['service_count_address']:return struct.pack('<I',100+self.index)
        strings={0x9000:b'small-hdd-read.cold-ish\0',0xa000:b'cold-ish\0'}
        for start,data in strings.items():
            if start<=address<start+len(data):return data[address-start:address-start+size]
        esp=0x80008000
        if address==esp:
            values=[0x12000,0x40,0x9000,0xa000] if self.phase=='measure' else [0x40,0,0,0,esp+0x88,0xb000,4096,esp+0x80]
            return struct.pack('<'+'I'*len(values),*values)
        if address==esp+0x6c:return struct.pack('<I',self.index)
        if address==esp+0x80:return struct.pack('<q',self.index*4096)
        if address==esp+0x88:return struct.pack('<II',0,4096)
        if address in (esp+0x58,esp+0x5c):return struct.pack('<I',int(self.bad_result))
        raise AssertionError('unknown invented read')
    def bp(self,address,enabled=True):(self.breakpoints.add if enabled else self.breakpoints.discard)(address)
    def interrupt(self):pass


class CaptureTests(unittest.TestCase):
    def run_case(self,cls):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);context=root/'context.json'
            context.write_text(json.dumps(dict(status='owned_paused_route_verified',mode='DIAGNOSTIC_ONLY',
                gdb_port=58931,kernel_sha256=KERNEL['final_sha256'],selected_case=FIXTURE['selected_case'],
                evidence_kind='INVENTED_HOST_CONTROL_FIXTURE')))
            binding=root/'binding.json'; binding.write_text(json.dumps(KERNEL))
            fixture=root/'fixture.json'; fixture.write_text(json.dumps(FIXTURE))
            args=argparse.Namespace(binding=binding,fixture=fixture,
                context=context,transport=ROOT/'trace-menu-io.py',port=58931,seconds=60,out=root/'capture')
            code=capture(args,transport_class=cls)
            result=json.loads((args.out/'report.json').read_text())
            rows=[json.loads(line) for line in (args.out/'boundaries.jsonl').read_text().splitlines()]
            self.last_events=[json.loads(line) for line in (args.out/'events.jsonl').read_text().splitlines()]
            control=args.out/'debugger-control.jsonl'
            self.last_control=[json.loads(line) for line in control.read_text().splitlines()] if control.exists() else []
        return code,result,rows
    def test_exact_1024_issue_consumer_pairs_stop_before_serial_shutdown(self):
        code,result,rows=self.run_case(InventedRsp)
        self.assertEqual(code,0);self.assertTrue(result['owned_boundaries']['complete'])
        self.assertEqual(result['owned_boundaries']['operations'],1024)
        self.assertEqual(len([row for row in rows if row['kind']=='issue']),1024)
        self.assertEqual(rows[-1]['index'],1023)
        self.assertFalse(result['native_qualified']);self.assertIsNone(result['physical_storage_peak_bytes'])
    def test_wrong_gate_does_not_read_kernel_or_claim_boundaries(self):
        class Bad(InventedRsp):wrong_gate=True
        code,result,rows=self.run_case(Bad)
        self.assertEqual(code,1);self.assertFalse(result['owned_boundaries']['complete']);self.assertEqual(rows,[])
    def test_actual_failed_consumer_and_disconnect_are_retained(self):
        for name in ('bad_result','disconnect'):
            cls=type('Bad',(InventedRsp,),{name:True})
            code,result,rows=self.run_case(cls)
            self.assertEqual(code,1);self.assertEqual(result['integrity'],'unknown')
            self.assertFalse(result['owned_boundaries']['complete']);self.assertIsNotNone(result['owned_boundaries']['error'])
    def test_cleanup_failure_cannot_be_success(self):
        class Bad(InventedRsp):cleanup_failure=True
        code,result,rows=self.run_case(Bad)
        self.assertEqual(code,1);self.assertEqual(result['integrity'],'unknown')


if __name__=='__main__':unittest.main()
