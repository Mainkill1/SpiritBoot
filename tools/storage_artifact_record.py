#!/usr/bin/env python3
"""Run the existing kernel fixups/flash packer unchanged and record their inputs."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

try:
    from .storage_build_evidence import digest, file_record, verify_source
except ImportError:
    from storage_build_evidence import digest, file_record, verify_source


def record_file(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': digest(path)}


def checked_tool(command):
    path = shutil.which(command)
    if not path:
        raise ValueError('artifact tool unavailable: ' + command)
    return record_file(path)


def execute(commands, inputs, output, record, source, tree, kind):
    """Keep a failed attempt from retaining an earlier successful receipt."""
    record = Path(record).resolve()
    record.unlink(missing_ok=True)
    source_identity = verify_source(source, tree)
    evidence = {'schema': 1, 'kind': kind, 'source_directory': str(Path(source).resolve()),
                'source_tree': tree, 'source_worktree_sha256': source_identity['worktree_sha256'],
                'commands': commands, 'inputs': inputs,
                'tools': [checked_tool(cmd[0]) for cmd in commands], 'exit_code': None}
    for command in commands:
        result = subprocess.run(command)
        evidence['exit_code'] = result.returncode
        if result.returncode:
            break
    if evidence['exit_code'] == 0:
        verify_source(source, tree, source_identity['worktree_sha256'])
        # The fixup intentionally writes its kernel input. Other inputs must
        # remain unchanged across execution. Its original bytes have a copy.
        for item in inputs:
            file_record(item, 'artifact pipeline input')
        evidence['output'] = record_file(output)
    temporary = record.with_suffix('.tmp')
    temporary.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
    temporary.replace(record)
    return evidence['exit_code']


def postprocess(args):
    args.record.unlink(missing_ok=True)
    kernel = args.kernel.resolve()
    before = args.record.with_suffix('.before.exe').resolve()
    after = args.record.with_suffix('.after.exe').resolve()
    shutil.copyfile(kernel, before)
    commands = [[str(args.objcopy), '--remove-section=.reloc', str(kernel)],
                [sys.executable, str(args.fix_exports), str(kernel), str(args.exports)]]
    inputs = [record_file(before), record_file(args.fix_exports), record_file(args.exports)]
    result = execute(commands, inputs, kernel, args.record, args.source, args.source_tree, 'postprocess')
    if result == 0:
        shutil.copyfile(kernel, after)
        evidence = json.loads(args.record.read_text())
        evidence['before_kernel'] = record_file(before)
        evidence['after_kernel'] = record_file(after)
        args.record.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
    return result


def pack(args):
    args.record.unlink(missing_ok=True)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        raise ValueError('missing original flash assembly command')
    def option(name):
        if command.count(name) != 1:
            raise ValueError('flash assembly requires explicit unique ' + name)
        index = command.index(name)
        if index + 1 >= len(command):
            raise ValueError('missing flash assembly operand')
        return Path(command[index+1]).resolve()
    kernel, loader, output = option('--kernel'), option('--nxldr'), option('--out')
    inputs = [record_file(kernel), record_file(loader), record_file(loader.with_suffix('.elf')),
              record_file(command[0])]
    if '--rom-resident' in command:
        inputs.append(record_file(option('--symbols')))
    result = execute([command], inputs, output, args.record, args.source, args.source_tree, 'pack')
    if result == 0:
        evidence = json.loads(args.record.read_text())
        evidence.update(kernel=record_file(kernel), loader=record_file(loader), flash=record_file(output))
        args.record.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    for name in ('postprocess', 'pack'):
        child = sub.add_parser(name)
        child.add_argument('--record', type=Path, required=True)
        child.add_argument('--source', type=Path, required=True)
        child.add_argument('--source-tree', required=True)
        if name == 'postprocess':
            for option in ('kernel', 'objcopy', 'fix-exports', 'exports'):
                child.add_argument('--' + option, type=Path, required=True)
        else:
            child.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        return postprocess(args) if args.mode == 'postprocess' else pack(args)
    except (OSError, ValueError) as error:
        print('storage artifact evidence failed: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
