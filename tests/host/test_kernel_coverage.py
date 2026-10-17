# SPDX-License-Identifier: GPL-2.0-only
"""Coverage inventories must never turn textual mentions into execution proof."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('kernel_coverage', ROOT / 'tools/kernel_coverage.py')
coverage = importlib.util.module_from_spec(SPEC) if SPEC else None
if SPEC and SPEC.loader and (ROOT / 'tools/kernel_coverage.py').exists():
    SPEC.loader.exec_module(coverage)
else:
    coverage = None


class KernelCoverageTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(coverage, 'kernel coverage inventory is not implemented')
        return coverage

    def test_export_abi_inventory_keeps_data_and_fastcall_distinct(self):
        exports = self.api().parse_exports('''LIBRARY xboxkrnl.exe\nEXPORTS\nFoo@8 @ 1 NONAME\n@Bar@12 @ 2 NONAME\nDatum @ 3 NONAME DATA\nPrint @ 4 NONAME\n''')
        self.assertEqual([(x['ordinal'], x['name'], x['kind'], x['calling_convention'], x['argument_bytes']) for x in exports],
                         [(1, 'Foo', 'callable', 'stdcall', 8), (2, 'Bar', 'callable', 'fastcall', 12),
                          (3, 'Datum', 'data', None, None), (4, 'Print', 'callable', 'cdecl', 0)])

    def test_duplicate_or_malformed_exports_fail_closed(self):
        api = self.api()
        for text in ['EXPORTS\nFoo@0 @ 1 NONAME\nFoo@4 @ 2 NONAME',
                     'EXPORTS\nFoo@0 @ 1 NONAME\nBar@4 @ 1 NONAME',
                     'EXPORTS\nFoo@oops @ 1 NONAME', 'EXPORTS\nFoo@0 @ 0 NONAME',
                     'EXPORTS\nFoo@0 @ 1 NONAME ALIAS', 'LIBRARY example']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                api.parse_exports(text)

    def test_comment_literal_declaration_definition_and_member_are_not_direct_calls(self):
        source = '''// Foo();\nconst char *text = "Foo()";\nextern int Foo(int n);\nint Foo(int n) { return n; }\nvoid t(void) {\n  extern int Foo(int n);\n  object.Foo(1); pointer->Foo(2);\n  Foo(3);\n}\n'''
        sites = self.api().scan_c(source, {'Foo': 'callable'})
        self.assertEqual([(s['line'], s['level'], s['function']) for s in sites if s['level'] == 'direct_invocation'], [(8, 'direct_invocation', 't')])
        self.assertTrue(all(not s['native_execution_qualified'] for s in sites))

    def test_conditionals_macros_and_function_pointer_are_conservative(self):
        source = '''#define RUN Foo()\nvoid t(void) {\n#if 0\n Foo();\n#else\n Foo();\n#endif\n void (*callback)(void) = &Foo;\n}\n'''
        sites = self.api().scan_c(source, {'Foo': 'callable'})
        self.assertEqual([(s['line'], s['level']) for s in sites], [(4, 'symbol_reference'), (6, 'symbol_reference'), (8, 'symbol_reference')])
        self.assertFalse(any(s['native_execution_qualified'] for s in sites))

    def test_data_reference_never_becomes_function_invocation(self):
        sites = self.api().scan_c('void t(void) { use(Datum); Datum(); }', {'Datum': 'data'})
        self.assertEqual([s['level'] for s in sites], ['symbol_reference', 'symbol_reference'])

    def test_unbalanced_source_fails_instead_of_silent_partial_inventory(self):
        api = self.api()
        for source in ['void t(void) { Foo();', '/* never closed', 'void t(void) { "never closed; }', '#if 0\nvoid t(void) {}']:
            with self.subTest(source=source), self.assertRaises(ValueError):
                api.scan_c(source, {'Foo': 'callable'})

    def fixture(self, directory):
        source = directory / 'assembled'; product = directory / 'product'
        (source / 'tests').mkdir(parents=True); product.mkdir()
        (source / 'exports.def').write_text('EXPORTS\nFoo@0 @ 1 NONAME\nBar@4 @ 2 NONAME\nDatum @ 3 NONAME DATA\n')
        (source / 'tests/probe.c').write_text('void t(void) { Foo(); use(Datum); }\n')
        (product / 'contract.md').write_text('Original owned contract: bound the transfer.\n')
        desc = lambda root, path, scope: {'scope': scope, 'path': path, 'sha256': hashlib.sha256((root / path).read_bytes()).hexdigest()}
        manifest = {'schema_version': 1, 'source_identity': {'declared_tree': 'a' * 40, 'scope': 'selected byte pins only'},
                    'exports': desc(source, 'exports.def', 'assembled'), 'expected_counts': {'total': 3, 'callable': 2, 'data': 1},
                    'test_sources': [desc(source, 'tests/probe.c', 'assembled')],
                    'supporting_sources': [desc(product, 'contract.md', 'product')],
                    'manual_contracts': [{'id': 'bounds', 'description': 'Owned bounds contract', 'exports': ['Bar'],
                                          'evidence': ['product:contract.md'], 'test_sources': ['assembled:tests/probe.c'],
                                          'gaps': ['Native adapter is not installed']}],
                    'exclusions': [{'id': 'physical', 'reason': 'No physical hardware evidence imported'}]}
        return source, product, manifest

    def test_report_partitions_exports_and_does_not_promote_manual_contract_to_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, product, manifest = self.fixture(Path(temporary))
            report = self.api().build_report(manifest, source, product)
            self.assertEqual(report['summary']['by_level'], {'direct_invocation': 1, 'symbol_reference': 1, 'manual_contract': 1, 'untested': 0})
            self.assertEqual(report['summary']['native_execution_qualified_exports'], 0)
            self.assertFalse(report['all_kernel_covered'])
            self.assertEqual(report, self.api().build_report(manifest, source, product))
            self.assertNotIn(str(source), json.dumps(report))

    def test_missing_changed_traversing_or_duplicate_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, product, manifest = self.fixture(Path(temporary))
            for fault in ['changed', 'missing', 'traversal', 'duplicate', 'unknown-scope', 'count']:
                modified = copy.deepcopy(manifest)
                if fault == 'changed': modified['test_sources'][0]['sha256'] = '0' * 64
                if fault == 'missing': modified['test_sources'][0]['path'] = 'tests/absent.c'
                if fault == 'traversal': modified['test_sources'][0]['path'] = '../outside.c'
                if fault == 'duplicate': modified['test_sources'] *= 2
                if fault == 'unknown-scope': modified['test_sources'][0]['scope'] = 'elsewhere'
                if fault == 'count': modified['expected_counts']['total'] = 4
                with self.subTest(fault=fault), self.assertRaises(ValueError):
                    self.api().build_report(modified, source, product)

    def test_unknown_manual_export_or_execution_claim_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, product, manifest = self.fixture(Path(temporary))
            for fault in ['unknown-export', 'unbound-evidence', 'execution-promotion']:
                modified = copy.deepcopy(manifest)
                if fault == 'unknown-export': modified['manual_contracts'][0]['exports'] = ['NotAnExport']
                if fault == 'unbound-evidence': modified['manual_contracts'][0]['evidence'] = ['product:missing.md']
                if fault == 'execution-promotion': modified['manual_contracts'][0]['native_execution_qualified'] = True
                with self.subTest(fault=fault), self.assertRaises(ValueError):
                    self.api().build_report(modified, source, product)

    def test_python_host_contract_is_pinned_without_inventing_export_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, product, manifest = self.fixture(Path(temporary))
            path = product / 'host_probe.py'
            path.write_text('def test_native_contract():\n    return "Foo()"\n')
            manifest['test_sources'].append({'scope': 'product', 'path': 'host_probe.py',
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            manifest['manual_contracts'][0]['test_sources'] = ['product:host_probe.py']
            report = self.api().build_report(manifest, source, product)
            self.assertEqual(report['summary']['by_level']['direct_invocation'], 1)
            self.assertEqual(report['summary']['native_execution_qualified_exports'], 0)

    def test_preprocessor_error_prose_is_not_parsed_as_a_c_literal(self):
        sites = self.api().scan_c("#ifndef SIZE\n#error selected kernel's default\n#endif\nvoid t(void) { Foo(); }\n", {'Foo': 'callable'})
        self.assertEqual([(s['line'], s['level']) for s in sites], [(4, 'direct_invocation')])

    def test_line_comment_continuation_does_not_create_a_direct_call(self):
        source = 'void t(void) {\n// continued comment ' + chr(92) + '\n Foo();\n}\n'
        self.assertEqual(self.api().scan_c(source, {'Foo': 'callable'}), [])

    def test_block_comment_opened_in_directive_does_not_create_function_calls(self):
        source = '#define NOTE /*\nvoid invented(void) { Foo(); }\n*/\nvoid actual(void) {}\n'
        self.assertEqual(self.api().scan_c(source, {'Foo': 'callable'}), [])
