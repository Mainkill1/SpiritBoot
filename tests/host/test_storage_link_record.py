"""Exercise the executed linker boundary with our own small compiler inputs."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools import storage_link_record as recorder
from tools.storage_build_evidence import resolved_inputs


class StorageLinkRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_nested_compiler_and_linker_responses_expand_and_bind(self):
        (self.root / 'outer.rsp').write_text('-O2 @inner.rsp -Wl,--start-group,@ld.rsp,--end-group')
        (self.root / 'inner.rsp').write_text('"input with space.o" -o output.exe')
        (self.root / 'ld.rsp').write_text('-l:libdisk.a --library=classpnp')
        arguments, records = recorder.expand_arguments(['gcc', '@outer.rsp'], self.root)
        self.assertEqual(arguments, ['gcc', '-O2', 'input with space.o', '-o', 'output.exe',
                                    '-Xlinker', '--start-group', '-Xlinker', '-l:libdisk.a',
                                    '-Xlinker', '--library=classpnp', '-Xlinker', '--end-group'])
        self.assertEqual({Path(r['path']).name for r in records}, {'outer.rsp', 'inner.rsp', 'ld.rsp'})
        (self.root / 'ld.rsp').write_text('-lharmless')
        with self.assertRaises(ValueError):
            recorder.verify_files(records)

    def test_response_cycle_and_missing_input_are_rejected(self):
        (self.root / 'cycle.rsp').write_text('@cycle.rsp')
        for name in ('cycle.rsp', 'absent.rsp'):
            with self.subTest(name=name), self.assertRaises((ValueError, OSError)):
                recorder.expand_arguments(['gcc', '@' + name], self.root)

    def test_xlinker_response_expansion(self):
        (self.root / 'ld.rsp').write_text('--start-group -ldisk --end-group')
        expanded, _ = recorder.expand_arguments(['gcc', '-Xlinker', '@ld.rsp'], self.root)
        self.assertEqual(expanded, ['gcc', '-Xlinker', '--start-group', '-Xlinker', '-ldisk',
                                    '-Xlinker', '--end-group'])

    @unittest.skipUnless(shutil.which('gcc'), 'requires host gcc')
    def test_gnu_escapes_inside_both_quote_modes_match_real_compiler(self):
        source = self.root / 'main.c'
        source.write_text('int main(void) { return 0; }\n')
        subprocess.run(['gcc', '-c', str(source), '-o', str(self.root / 'input with space.o')], check=True)
        for quote in ('"', "'"):
            with self.subTest(quote=quote):
                (self.root / 'link.rsp').write_text(quote + r'input\ with\ space.o' + quote +
                                                  ' -o program -Wl,-Map=program.map')
                subprocess.run(['gcc', '@link.rsp'], cwd=self.root, check=True)
                self.assertEqual(recorder.run_link(['gcc', '@link.rsp'], self.root / 'executed.json', self.root), 0)

    @unittest.skipUnless(shutil.which('gcc'), 'requires host gcc')
    def test_records_the_executed_link_and_original_output(self):
        source = self.root / 'main.c'
        source.write_text('int main(void) { return 0; }\n')
        subprocess.run(['gcc', '-c', str(source), '-o', str(self.root / 'main.o')], check=True)
        (self.root / 'link.rsp').write_text('main.o -o program -Wl,-Map=program.map')
        record = self.root / 'executed.json'
        self.assertEqual(recorder.run_link(['gcc', '@link.rsp'], record, self.root), 0)
        result = json.loads(record.read_text())
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['argv'], ['gcc', '@link.rsp'])
        self.assertIn('main.o', result['expanded_argv'])
        self.assertEqual(Path(result['output_path']), self.root / 'program')
        self.assertEqual(Path(result['linked_output']['path']).read_bytes(), (self.root / 'program').read_bytes())
        self.assertTrue(result['resolved_inputs'])
        recorder.verify_files(result['response_files'] + result['resolved_inputs'])
        # Reconfiguration cannot replace the executed command record.
        (self.root / 'build.ninja').write_text('unrelated current graph')
        self.assertEqual(json.loads(record.read_text()), result)

    @unittest.skipUnless(shutil.which('gcc'), 'requires host gcc')
    def test_failed_link_cannot_reuse_previous_success(self):
        record = self.root / 'executed.json'
        record.write_text('{"exit_code": 0}')
        (self.root / 'missing.o').write_bytes(b'own invalid object fixture')
        self.assertNotEqual(recorder.run_link(['gcc', 'missing.o', '-o', 'program',
                                              '-Wl,-Map=program.map'], record, self.root), 0)
        result = json.loads(record.read_text())
        self.assertNotEqual(result['exit_code'], 0)
        self.assertNotIn('linked_output', result)

    def test_output_and_map_must_be_unambiguous(self):
        for args in (['gcc', '-o', 'a'], ['gcc', '-o', 'a', '-o', 'b', '-Wl,-Map=x'],
                     ['gcc', '-o', 'a', '-Wl,-Map=x,-Map=y']):
            with self.subTest(args=args), self.assertRaises(ValueError):
                recorder.link_paths(args, self.root)

    def test_known_gnu_pe_synthetic_input_is_explicit_not_a_missing_archive(self):
        archive = self.root / 'libowned.a'
        archive.write_bytes(b'!<arch>\n')
        path = self.root / 'pe.map'
        path.write_text('LOAD libowned.a\nOUTPUT(kernel.exe pei-i386)\nLOAD dll stuff\n')
        files, transient, synthetic = resolved_inputs(path, self.root)
        self.assertEqual([Path(item['path']).name for item in files], ['libowned.a'])
        self.assertEqual(transient, [])
        self.assertEqual(synthetic, ['gnu-ld-pe:dll stuff'])
        path.write_text(path.read_text() + 'LOAD arbitrary missing object\n')
        with self.assertRaises(ValueError):
            resolved_inputs(path, self.root)
