# SPDX-License-Identifier: MIT
"""Generic synthetic vectors and REP conservation; no sample-specific goldens."""
import unittest
import hashlib
from pathlib import Path
import tempfile
from unittest.mock import patch
from summarize_work import vector_summary, rep_summary, decode_rep_scalar, extract_rep_metadata


class WorkTests(unittest.TestCase):
    def test_exact_phase_vectors_define_repeated_floor_and_additive_deltas(self):
        reads = [
            {'api': 1, 'phase_symbols': {'entry_to_ready': {'base': 3}, 'ready_to_bind': {'child': 2}}},
            {'api': 2, 'phase_symbols': {'entry_to_ready': {'base': 3}, 'ready_to_bind': {'child': 2}}},
            {'api': 3, 'phase_symbols': {'entry_to_ready': {'base': 3, 'irq': 4}, 'ready_to_bind': {'child': 2}}},
        ]
        result = vector_summary(reads, {1,2,3}, {'irq'})
        self.assertEqual(result.get('minimum_begun'), 5)
        self.assertEqual(result.get('floor_apis'), [1,2])
        self.assertEqual(result.get('floor_calls'), 2)
        delta = result['deltas'][2]
        self.assertEqual(delta['instruction_delta'], 4)
        self.assertTrue(delta['componentwise_additive'])
        self.assertEqual(delta['interrupt_entry_delta'], 4)
        self.assertEqual(delta['delta_by_phase'], {'entry_to_ready': {'irq': 4}})

    def test_equal_totals_with_different_vectors_do_not_invent_unique_floor(self):
        reads = [{'api':1,'phase_symbols':{'entry_to_ready':{'a':2}}},
                 {'api':2,'phase_symbols':{'ready_to_bind':{'a':2}}}]
        result = vector_summary(reads, {1,2}, set())
        self.assertEqual(result.get('minimum_begun'), 2)
        self.assertFalse(result.get('unique_floor'))
        self.assertEqual(result.get('deltas'), [])
        self.assertEqual(len(result['minimum_vectors']), 2)

    def test_signed_delta_does_not_call_substitution_additive(self):
        reads = [{'api':1,'phase_symbols':{'entry_to_ready':{'a':2}}},
                 {'api':2,'phase_symbols':{'entry_to_ready':{'b':3}}}]
        result = vector_summary(reads, {1,2}, set())
        self.assertIn('deltas', result)
        delta = result['deltas'][1]
        self.assertFalse(delta['componentwise_additive'])
        self.assertEqual(delta['delta_by_phase'], {'entry_to_ready': {'a':-2,'b':3}})
        self.assertEqual(delta['instruction_delta'], 1)

    def test_empty_cohort_is_not_a_zero_work_control(self):
        result = vector_summary([], set(), set())
        self.assertIsNone(result.get('minimum_begun'))
        self.assertEqual(result.get('floor_calls'), 0)
        self.assertFalse(result.get('unique_floor'))

    def sample(self):
        capture = {'descriptors': {1:{'instructions':{1:{'pc':0x1000,'rep':1},2:{'pc':0x1002,'rep':0}}},
                                  2:{'instructions':{1:{'pc':0x1004,'rep':1},2:{'pc':0x1006,'rep':1}}}},
                   'rows': [dict(api=1,identity_seq=1,tb=1,first=1,last=2,executions=2,begun=4,rep_iterations=9),
                            dict(api=1,identity_seq=2,tb=1,first=1,last=1,executions=1,begun=1,rep_iterations=3),
                            dict(api=1,identity_seq=3,tb=2,first=1,last=2,executions=1,begun=2,rep_iterations=5)],
                   'excluded':[dict(api=1,identity_seq=2,pc=0x9999,first=1,last=2,executions=1,begun=2,rep_iterations=7)]}
        symbols={'image_sha256':'abc','instruction_owners':{'00001000':'clear','00001004':'copy','00001006':'other'}}
        phases={(1,1):'entry_to_ready',(1,2):'ready_to_bind',(1,3):'bind_to_start'}
        metadata={'image_sha256':'abc','instructions':{'00001000':{'mnemonic':'rep stosl','element_width_bytes':4}}}
        return capture,symbols,phases,metadata

    def test_rep_iterations_are_separate_and_conserved_with_ambiguity(self):
        result=rep_summary(*self.sample())
        self.assertEqual(result.get('known_iterations'),24)
        self.assertEqual(result.get('owned_unambiguous_iterations'),12)
        self.assertEqual(result.get('owned_ambiguous_iterations'),5)
        self.assertEqual(result.get('excluded_iterations'),7)
        self.assertEqual(sum(row['iterations'] for row in result['records']),24)
        first=next(row for row in result['records']if row['phase']=='entry_to_ready')
        self.assertEqual(first['linked_symbol'],'clear')
        self.assertEqual(first['instruction_starts'],2)
        self.assertEqual(first['iterations'],9)
        self.assertEqual(first['body_byte_operations'],36)
        ambiguous=next(row for row in result['records']if row['scope']=='ambiguous_owned')
        self.assertIsNone(ambiguous['body_byte_operations'])
        self.assertIsNone(ambiguous['linked_symbol'])

    def test_unknown_rep_does_not_become_known_zero(self):
        args=self.sample(); del args[0]['rows'][0]['rep_iterations']
        result=rep_summary(*args)
        self.assertEqual(result.get('known_iterations'),15)
        self.assertEqual(result.get('unknown_iteration_rows'),1)
        row=next(row for row in result['records']if row['phase']=='entry_to_ready')
        self.assertEqual(row['unknown_rows'],1)
        self.assertIsNone(row['body_byte_operations'])

    def test_rep_image_identity_mismatch_rejects(self):
        args=self.sample(); args[3]['image_sha256']='wrong'
        with self.assertRaises(ValueError): rep_summary(*args)

    def test_unselected_rep_counts_remain_explicit(self):
        args=self.sample(); del args[2][(1,3)]
        result=rep_summary(*args)
        self.assertEqual(result.get('known_iterations'),19)
        self.assertEqual(result.get('unselected_known_iterations'),5)

    def test_owned_image_scalar_binding_is_exact_and_payload_free(self):
        with tempfile.TemporaryDirectory() as directory:
            image=Path(directory)/'owned-synthetic.exe';image.write_bytes(b'owned synthetic')
            digest=hashlib.sha256(image.read_bytes()).hexdigest()
            symbols={'image_sha256':digest,'instruction_owners':{'00001000':'clear'}}
            listing='00001000 <clear>:\n    1000: f3 aa    rep stos %al,%es:(%edi)\n'
            with patch('summarize_work.subprocess.check_output',return_value=listing):
                result=extract_rep_metadata(image,symbols,{'00001000'})
                self.assertEqual(result,{'image_sha256':digest,'instructions':{'00001000':{
                    'linked_symbol':'clear','mnemonic':'rep stos','element_width_bytes':1}}})
                with self.assertRaises(ValueError):extract_rep_metadata(image,symbols,{'00001001'})
            with self.assertRaises(ValueError):
                extract_rep_metadata(image,{'image_sha256':'wrong','instruction_owners':{}},{'00001000'})

    def test_scalar_decoder_exposes_no_bytes_or_operands(self):
        self.assertEqual(decode_rep_scalar('rep stos %al,%es:(%edi)'), {'mnemonic':'rep stos','element_width_bytes':1})
        self.assertEqual(decode_rep_scalar('rep movsl %ds:(%esi),%es:(%edi)'), {'mnemonic':'rep movsl','element_width_bytes':4})
        self.assertEqual(decode_rep_scalar('repne scas %ax,%es:(%edi)'), {'mnemonic':'repne scas','element_width_bytes':2})
        self.assertIsNone(decode_rep_scalar('mov %eax,%ebx'))


if __name__ == '__main__': unittest.main()
