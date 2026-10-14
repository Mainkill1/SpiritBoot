"""Evidence-gate behavior tests; fixture text comes from a real qualified receipt."""
import copy
import datetime as dt
import json
from pathlib import Path
import hashlib
import shutil
import tempfile
import unittest

import analyze

CAMPAIGN = Path('/home/codex/xemu-shader-workbench-handoff/.scratch/remaining-mm-audit-20261013')
FULL_MANIFEST = Path('/home/codex/xemu-shader-workbench-handoff/.scratch/spiritboot-release-hardening-20261013/artifacts/mm-qualified-release64/build.json')
NOSG_MANIFEST = Path('/home/codex/xemu-shader-workbench-handoff/.scratch/remaining-mm-no-sg-20261013/artifacts/no-sg-release64/build.json')

class QualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.log = next((CAMPAIGN/'results').glob('probe-closing-api-leaf-performance-0-combined-*/serial.log')).read_text()

    def test_every_enabled_leaf_is_qualified_including_legacy_todo_passes(self):
        self.assertEqual(len(analyze.parse_api(self.log)), 634)

    def test_ordinary_tap_cannot_claim_a_different_test_passed(self):
        with self.assertRaises(ValueError):
            analyze.parse_api(self.log.replace('ok 1 - rtl/status/success', 'ok 1 - unknown/different-test', 1))

    def test_malformed_leaf_cannot_be_ignored(self):
        with self.assertRaises(ValueError):
            analyze.parse_api(self.log+'\n# LEAF name=unknown ticks=1 ok=0 todo=0 extra=garbage\n')

    def test_false_leaf_correctness_cannot_qualify(self):
        with self.assertRaises(ValueError):
            analyze.parse_api(self.log.replace('ok=1 todo=0', 'ok=0 todo=0', 1))

    def test_legacy_process_todo_failure_cannot_qualify(self):
        rows = self.log.splitlines()
        row = next(x for x in rows if x.startswith('ok ') and 'ke/procprio/the_process_lists_its_threads # TODO ' in x)
        with self.assertRaises(ValueError):
            analyze.parse_api(self.log.replace(row, 'not '+row, 1))

    def test_missing_tap_record_cannot_qualify(self):
        with self.assertRaises(ValueError):
            analyze.parse_api('\n'.join(x for x in self.log.splitlines() if not x.startswith('ok 1 - ')))

class StatisticsTests(unittest.TestCase):
    def test_seven_pair_costs_keep_all_samples_and_a_large_outlier(self):
        s = analyze.seven_stats([1,2,3,4,5,6,7], [2,3,4,5,6,7,1000])
        self.assertEqual(s.get('pairs'), 7)
        self.assertEqual(s.get('full_median_us'), 5)
        self.assertEqual(s.get('nosg_median_us'), 4)
        self.assertEqual(s.get('full_max_us'), 1000)
        self.assertEqual(s.get('full_slower_pairs'), 7)
        self.assertEqual(s.get('full_samples_us'), [2,3,4,5,6,7,1000])
        self.assertEqual(s.get('paired_deltas_us'), [1,1,1,1,1,1,993])

    def test_incomplete_cost_pairs_cannot_produce_a_comparison(self):
        with self.assertRaises(ValueError):
            analyze.seven_stats([1]*6, [2]*7)

    def test_zero_costs_are_retained_without_inventing_a_ratio(self):
        s = analyze.seven_stats([0]*7, [1]*7)
        self.assertEqual(s.get('nosg_samples_us'), [0]*7)
        self.assertIsNone(s.get('ratio_full_over_nosg'))

def ordered_runs():
    epoch=dt.datetime(2026,10,14,tzinfo=dt.timezone.utc)
    runs=[]
    for i in range(7):
        for side in (('full','nosg') if i%2==0 else ('nosg','full')):
            begin=epoch+dt.timedelta(seconds=len(runs)*25)
            runs.append({'pair':i,'side':side,'started':begin,'ended':begin+dt.timedelta(seconds=20)})
    return runs

class CampaignTests(unittest.TestCase):
    def test_fourteen_alternating_nonoverlapping_runs_are_required(self):
        self.assertTrue(analyze.validate_run_order(ordered_runs()))

    def test_missing_run_cannot_qualify(self):
        with self.assertRaises(ValueError):
            analyze.validate_run_order(ordered_runs()[:-1])

    def test_reversed_pair_order_cannot_qualify(self):
        runs=ordered_runs();runs[0]['side'],runs[1]['side']=runs[1]['side'],runs[0]['side']
        with self.assertRaises(ValueError):
            analyze.validate_run_order(runs)

    def test_overlapping_runs_cannot_qualify(self):
        runs=ordered_runs();runs[1]['started']=runs[0]['started']
        with self.assertRaises(ValueError):
            analyze.validate_run_order(runs)

    def test_exact_one_patch_control_is_verified(self):
        result=analyze.validate_manifests(FULL_MANIFEST,NOSG_MANIFEST)
        self.assertEqual(result.get('removed_patch'),'patches/roswell/0124-direct-sync-gather-write.patch')

    def test_a_second_missing_patch_invalidates_attribution(self):
        j=json.loads(NOSG_MANIFEST.read_text());j['patches'].pop()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'build.json';p.write_text(json.dumps(j))
            with self.assertRaises(ValueError):
                analyze.validate_manifests(FULL_MANIFEST,p)

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        source=next((CAMPAIGN/'results').glob('probe-closing-api-leaf-performance-0-combined-*'))
        for name in ['launch.json','inputs.json','result.json','launch-xemu.toml','serial.log']:
            shutil.copyfile(source/name,self.path/name)

    def change_json(self,name,key,value):
        p=self.path/name;j=json.loads(p.read_text(encoding='utf-8-sig'));j[key]=value;p.write_text(json.dumps(j))

    def test_real_frozen_receipt_qualifies_all_leaves(self):
        self.assertEqual(len(analyze.receipt(self.path,0,'full')['values']),634)

    def test_wrong_executable_cannot_qualify(self):
        self.change_json('launch.json','exeSha256','0'*64)
        with self.assertRaises(ValueError):analyze.receipt(self.path,0,'full')

    def test_wrong_bios_cannot_qualify(self):
        self.change_json('launch.json','biosSha256','0'*64)
        with self.assertRaises(ValueError):analyze.receipt(self.path,0,'full')

    def test_changed_eeprom_seed_cannot_qualify(self):
        self.change_json('inputs.json','eepromSha256','0'*64)
        with self.assertRaises(ValueError):analyze.receipt(self.path,0,'full')

    def test_changed_config_even_with_updated_hash_cannot_qualify(self):
        p=self.path/'launch-xemu.toml';p.write_text(p.read_text().replace('vsync = false','vsync = true'))
        self.change_json('inputs.json','configSha256',hashlib.sha256(p.read_bytes()).hexdigest())
        with self.assertRaises(ValueError):analyze.receipt(self.path,0,'full')

    def test_timed_out_guest_cannot_qualify(self):
        self.change_json('result.json','exited',False)
        with self.assertRaises(ValueError):analyze.receipt(self.path,0,'full')

if __name__=='__main__':
    unittest.main()
