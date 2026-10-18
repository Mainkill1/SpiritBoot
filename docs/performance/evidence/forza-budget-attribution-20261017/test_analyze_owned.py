# SPDX-License-Identifier: MIT
import unittest
from pathlib import Path
import json
import analyze_owned as owned

ROOT=Path(__file__).resolve().parent

def row(**kw):
    r=dict(host_ns=1000,virtual_ns=900,thread=1,handle=2,bytes=512,
           total_ns=100,status=0,info=0,reentry=0,bad=0)
    for i in range(9):r.update({f'p{i}_ns':0,f'p{i}_count':0,f'p{i}_open':0})
    r.update(kw);return r


def log(r):
    return 'owned_meta rows=1 overflow=0 lost=0\nowned_read '+' '.join(
        f'{k}={v:08x}'if k in owned.HEX else f'{k}={v}'for k,v in r.items())


class OwnedTests(unittest.TestCase):
    def test_corrected_abi_and_sites(self):
        source=(ROOT/'v12b-owned-observer.c.txt').read_text()
        sites=json.loads((ROOT/'owned-phase-sites.json').read_text())
        owned.verify_observer(source,sites)
        with self.assertRaises(ValueError):owned.verify_observer(source.replace('esp+16','esp+12'),sites)
        sites[0]['entry']+=1
        with self.assertRaises(ValueError):owned.verify_observer(source,sites)

    def test_malformed_capture(self):
        for text in ['owned_meta rows=1 overflow=0 lost=0',log(row()).replace('bytes=512','bytes=x'),log(row())+' bytes=512']:
            with self.subTest(text=text),self.assertRaises(ValueError):owned.parse_log(text)

    def test_nested_phases_not_added(self):
        r=row(p3_ns=80,p3_count=1,p7_ns=60,p7_count=1)
        sites=[{'name':str(i)}for i in range(9)]
        s=owned.summarize([r],sites)
        self.assertEqual(s['total_api_ns']['sum'],100)
        self.assertEqual(s['unobserved_time_bounds_ns']['aggregate_lower'],0)
        self.assertEqual(s['unobserved_time_bounds_ns']['aggregate_upper'],20)

    def test_invalid_phase_scopes_diagnosed(self):
        for changes,key in [({'p3_open':1},'open_phase_depths'),({'p3_ns':101},'phase_exceeds_total'),({'bad':1},'bad_selected'),({'reentry':1},'reentry_selected')]:
            checks=owned.validation({'overflow':0,'lost':0},[row(**changes)],0)
            self.assertGreater(checks[key],0)

    def test_dpc_partition(self):
        sites=[{'name':str(i)}for i in range(9)]
        s=owned.summarize([row(),row(p1_count=1,p1_ns=20)],sites)
        self.assertEqual(s['partitions']['dpc_absent']['reads'],1)
        self.assertEqual(s['partitions']['dpc_present']['reads'],1)


if __name__=='__main__':unittest.main()
