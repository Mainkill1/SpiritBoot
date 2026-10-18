# SPDX-License-Identifier: MIT
"""Independent synthetic tests. No firmware or external disassembly is read."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from analyze_prefix import build_symbol_map, counts_by_api, parse


# Instruction 2 crosses an enclosing-symbol boundary. Instruction 3 has no
# exact decoded PC in the supplied map, even though it lies inside a symbol.
CAPTURE = '''prefix_meta version=1 descriptors=2 rows=4 translations=1 overflow=0 reentry=0 thread_mismatch=0 invalid_prefix=0 open_api=0
prefix_tb id=1 pc=84001000 count=3 generation=1 born_api=1 born_identity_seq=10
prefix_insn tb=1 ordinal=1 pc=84001000 rep=0
prefix_insn tb=1 ordinal=2 pc=84001004 rep=1
prefix_insn tb=1 ordinal=3 pc=84001005 rep=0
prefix_tb id=2 pc=84001000 count=1 generation=2 born_api=0 born_identity_seq=0
prefix_insn tb=2 ordinal=1 pc=84001000 rep=0
prefix_row api=1 identity_seq=10 tb=1 first=1 last=2 executions=2 begun=4 rep_iterations=17
prefix_row api=1 identity_seq=11 tb=1 first=2 last=3 executions=3 begun=6
prefix_row api=2 identity_seq=20 tb=2 first=1 last=1 executions=7 begun=7 rep_iterations=0
prefix_row api=1 identity_seq=11 tb=2 first=1 last=1 executions=1 begun=1 rep_iterations=0
prefix_translation api=1 identity_seq=10 tb=1
prefix_end rows=4
'''
OBJDUMP = '''owned-synthetic: file format pei-i386
Disassembly of section .text:
84001000 <first>:
84001000:  90                      nop
84001001:  0f 1f 00                nopl (%eax)
84001004 <second.constprop.0>:
84001004:  f3 a4                   rep movsb %ds:(%esi),%es:(%edi)
84001006:  90                      nop
84001007:  ff                      (bad)
Disassembly of section .other:
84002000:  90                      nop
84002001 <third>:
84002001:  c3                      ret
'''


class IndependentPrefixTests(unittest.TestCase):
    def symbol_map(self, listing=OBJDUMP):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'owned-synthetic-image.bin'
            image.write_bytes(b'owned synthetic identity only; never disassembled')
            with patch('analyze_prefix.subprocess.check_output', return_value=listing) as call:
                result = build_symbol_map(image)
            call.assert_called_once_with(['objdump', '-d', str(image)], text=True)
            self.assertEqual(result['image_sha256'], hashlib.sha256(image.read_bytes()).hexdigest())
            return result

    def counts(self, capture=CAPTURE):
        return counts_by_api(parse(capture), self.symbol_map())

    def test_exact_decoded_boundaries_and_enclosing_symbols(self):
        owners = self.symbol_map()['instruction_owners']
        self.assertEqual(owners, {'84001000': 'first', '84001001': 'first',
            '84001004': 'second.constprop.0', '84001006': 'second.constprop.0',
            '84002001': 'third'})
        self.assertNotIn('84001005', owners)  # Middle of REP encoding, not a boundary.

    def test_new_section_does_not_inherit_previous_symbol(self):
        self.assertNotIn('84002000', self.symbol_map()['instruction_owners'])

    def test_bad_decoding_is_not_attributed(self):
        self.assertNotIn('84001007', self.symbol_map()['instruction_owners'])

    def test_duplicate_decoded_pc_rejects_ambiguous_map(self):
        with self.assertRaises(ValueError):
            self.symbol_map(OBJDUMP + '84001000: 90 nop\n')

    def test_empty_disassembly_rejects(self):
        with self.assertRaises(ValueError):
            self.symbol_map('Disassembly of section .text:\n84001000 <empty>:\n')

    def test_unknown_pc_retained_without_nearest_symbol_guess(self):
        api = self.counts()[1]
        self.assertEqual(api['unknown_pcs'], {'84001005': 3})
        self.assertEqual(api['symbols'], {'first': 3, 'second.constprop.0': 5, '<unknown>': 3})

    def test_started_instructions_and_rep_iterations_are_separate(self):
        api = self.counts()[1]
        self.assertEqual(api['begun'], 11)
        self.assertEqual(api['prefix_executions'], 6)
        self.assertEqual(api['rep_iterations_known'], 17)
        self.assertEqual(api['rows_with_unknown_rep'], 1)
        self.assertEqual(sum(api['symbols'].values()), 11)  # Never 11 + 17.

    def test_unknown_rep_does_not_invent_zero_or_one_iteration(self):
        api = self.counts(CAPTURE.replace(' rep_iterations=17', ''))[1]
        self.assertEqual(api['begun'], 11)
        self.assertEqual(api['rep_iterations_known'], 0)
        self.assertEqual(api['rows_with_unknown_rep'], 2)

    def test_api_phase_and_global_counts_preserved(self):
        result = self.counts()
        self.assertEqual(result[2]['symbols'], {'first': 7})
        self.assertEqual(result[1]['phases_by_identity_seq'][10], {'first': 2, 'second.constprop.0': 2})
        self.assertEqual(result[1]['phases_by_identity_seq'][11],
                         {'first': 1, 'second.constprop.0': 3, '<unknown>': 3})
        self.assertEqual(sum(api['begun'] for api in result.values()), 18)
        for api in result.values():
            self.assertEqual(sum(sum(phase.values()) for phase in api['phases_by_identity_seq'].values()), api['begun'])

    def test_distinct_tb_generations_at_same_pc_preserve_counts(self):
        parsed = parse(CAPTURE)
        self.assertEqual({desc['generation'] for desc in parsed['descriptors'].values()}, {1, 2})
        self.assertEqual(self.counts()[1]['symbols']['first'], 3)

    def test_all_record_boundary_truncations_reject(self):
        lines = CAPTURE.splitlines(keepends=True)
        for cutoff in range(len(lines)):
            with self.subTest(cutoff=cutoff), self.assertRaises(ValueError):
                parse(''.join(lines[:cutoff]))

    def test_missing_instruction_cannot_be_hidden_by_metadata(self):
        with self.assertRaises(ValueError):
            parse(CAPTURE.replace('prefix_insn tb=1 ordinal=3 pc=84001005 rep=0\n', ''))

    def test_duplicate_descriptor_instruction_translation_and_footer_reject(self):
        for prefix in ('prefix_meta ', 'prefix_tb ', 'prefix_insn ', 'prefix_translation ', 'prefix_end '):
            line = next(line for line in CAPTURE.splitlines(keepends=True) if line.startswith(prefix))
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                parse(CAPTURE.replace(line, line + line, 1))

    def test_duplicate_row_rejects_even_with_adjusted_counts(self):
        line = next(line for line in CAPTURE.splitlines(keepends=True) if line.startswith('prefix_row '))
        with self.assertRaises(ValueError):
            parse(CAPTURE.replace('rows=4', 'rows=5').replace(line, line + line))

    def test_non_numeric_missing_equals_and_unknown_records_reject(self):
        for bad in ('executions=oops', 'executions', 'executions='):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse(CAPTURE.replace('executions=2', bad))
        with self.assertRaises(ValueError):
            parse(CAPTURE.replace('prefix_row ', 'row ', 1))

    def test_footer_and_all_header_totals_are_binding(self):
        for old, new in [('descriptors=2', 'descriptors=1'), ('rows=4', 'rows=3'),
                         ('translations=1', 'translations=0'), ('prefix_end rows=4', 'prefix_end rows=5')]:
            with self.subTest(old=old), self.assertRaises(ValueError):
                parse(CAPTURE.replace(old, new, 1))

    def test_rep_iterations_require_marked_instruction_within_executed_prefix(self):
        with self.assertRaises(ValueError):
            parse(CAPTURE.replace('first=1 last=2 executions=2 begun=4',
                                  'first=1 last=1 executions=2 begun=2'))

    def test_translation_birth_identity_mismatch_rejects(self):
        with self.assertRaises(ValueError):
            parse(CAPTURE.replace('prefix_translation api=1 identity_seq=10',
                                  'prefix_translation api=1 identity_seq=11'))

    def test_pc_width_and_first_pc_consistency_reject(self):
        for old, new in [('pc=84001005', 'pc=100000000'),
                         ('prefix_tb id=1 pc=84001000', 'prefix_tb id=1 pc=84001001')]:
            with self.subTest(new=new), self.assertRaises(ValueError):
                parse(CAPTURE.replace(old, new))

    def test_prefix_begun_total_cannot_be_altered_silently(self):
        with self.assertRaises(ValueError):
            parse(CAPTURE.replace('executions=3 begun=6', 'executions=3 begun=9'))


if __name__ == '__main__':
    unittest.main()
