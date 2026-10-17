"""Exercise artifact receipts with independently authored, actually run tools."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import storage_artifact_record as recorder
from tools.storage_build_evidence import file_record


class StorageArtifactRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'contract.txt').write_text('owned test contract\n')
        subprocess.run(['git', 'init', '-q', str(self.source)], check=True)
        subprocess.run(['git', '-C', str(self.source), 'add', '.'], check=True)
        self.tree = subprocess.check_output(['git', '-C', str(self.source), 'write-tree'], text=True).strip()
        self.record = self.root / 'execution.json'
        self.output = self.root / 'output'
        self.input = self.root / 'input'
        self.input.write_bytes(b'exact input bytes')

    def test_success_receipt_binds_actually_consumed_input_output_and_source(self):
        command = [sys.executable, '-c',
                   'from pathlib import Path; import sys; Path(sys.argv[2]).write_bytes(Path(sys.argv[1]).read_bytes())',
                   str(self.input), str(self.output)]
        self.assertEqual(recorder.execute([command], [recorder.record_file(self.input)], self.output,
                                         self.record, self.source, self.tree, 'pack'), 0)
        result = json.loads(self.record.read_text())
        self.assertEqual(result['commands'], [command])
        self.assertEqual(result['source_tree'], self.tree)
        self.assertEqual(result['output'], recorder.record_file(self.output))
        self.assertEqual(file_record(result['inputs'][0], 'input'), self.input)
        self.assertTrue(result['source_worktree_sha256'])
        self.assertEqual(self.output.read_bytes(), b'exact input bytes')

    def test_failed_execution_cannot_keep_a_successful_receipt(self):
        self.record.write_text('{"exit_code":0}')
        self.assertEqual(recorder.execute([[sys.executable, '-c', 'raise SystemExit(9)']],
                                         [recorder.record_file(self.input)], self.output,
                                         self.record, self.source, self.tree, 'pack'), 9)
        result = json.loads(self.record.read_text())
        self.assertEqual(result['exit_code'], 9)
        self.assertNotIn('output', result)

    def test_input_mutation_during_execution_invalidates_receipt(self):
        command = [sys.executable, '-c',
                   'from pathlib import Path; import sys; Path(sys.argv[1]).write_bytes(b"changed")', str(self.input)]
        self.record.write_text('{"exit_code":0}')
        with self.assertRaises(ValueError):
            recorder.execute([command], [recorder.record_file(self.input)], self.input,
                             self.record, self.source, self.tree, 'pack')
        self.assertFalse(self.record.exists())

    def test_duplicate_pack_kernel_is_rejected_before_execution(self):
        self.record.write_text('{"exit_code":0}')
        args = argparse.Namespace(command=['owned-packer', '--kernel', str(self.input),
                                           '--kernel', str(self.input)],
                                  record=self.record, source=self.source, source_tree=self.tree)
        with self.assertRaises(ValueError):
            recorder.pack(args)
        self.assertFalse(self.record.exists())

    def test_postprocess_validation_invalidates_old_success_before_copy(self):
        self.record.write_text('{"exit_code":0}')
        args = argparse.Namespace(kernel=self.root / 'missing-kernel', record=self.record)
        with self.assertRaises(OSError):
            recorder.postprocess(args)
        self.assertFalse(self.record.exists())
