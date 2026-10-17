#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile actual semaphore/exception-filter bodies against a host boundary shim.

Without --source-root, test the patch postimage plus pinned, unchanged production
function excerpts. With it, extract all three functions from the assembled tree.
This checks status/exception decisions and release/cleanup behavior; it is not an
x86 SEH/ABI or native execution test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/host/fixtures/kernel-semaphore-overflow'
FUNCTIONS = {'NtReleaseSemaphore': 'ntoskrnl/ex/sem.c',
             'KeReleaseSemaphore': 'ntoskrnl/ke/semphobj.c',
             'ExSystemExceptionFilter': 'ntoskrnl/ex/harderr.c'}


def function(text, name):
    """Extract a named production body, retaining its complete declaration."""
    hits = list(re.finditer(r'^' + re.escape(name) + r'\s*\([^;{}]*?\)\s*\{', text, re.M))
    if len(hits) != 1:
        raise ValueError('expected exactly one definition: ' + name)
    hit = hits[0]
    start = text.rfind('\n\n', 0, hit.start()) + 2
    opening = text.index('{', hit.start())
    depth, end = 1, opening + 1
    while depth:
        if end >= len(text):
            raise ValueError('unbalanced production function: ' + name)
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


def production_functions(source_root=None):
    if source_root is not None:
        return {name: function((source_root / path).read_text(), name)
                for name, path in FUNCTIONS.items()}
    baseline = (FIXTURE / 'baseline-functions.c').read_text()
    result = {name: function(baseline, name) for name in FUNCTIONS}
    patch = (ROOT / 'patches/roswell/0136-kernel-semaphore-overflow.patch').read_text()
    current, lines = None, []
    for line in patch.splitlines():
        if line.startswith('+++ b/'):
            current = line[6:]
        elif current == FUNCTIONS['NtReleaseSemaphore'] and line.startswith((' ', '+')):
            lines.append(line[1:])
    result['NtReleaseSemaphore'] = function('\n'.join(lines), 'NtReleaseSemaphore')
    return result


def check(platform, source_root=None, output=None):
    bodies = production_functions(source_root)
    text = ((FIXTURE / 'shim.h').read_text() + '\n' +
            bodies['ExSystemExceptionFilter'] + '\n' +
            bodies['KeReleaseSemaphore'] + '\n' +
            bodies['NtReleaseSemaphore'] + '\n' +
            (FIXTURE / 'cases.c').read_text())
    with tempfile.TemporaryDirectory(prefix='semaphore-overflow-') as temporary:
        directory = Path(temporary)
        source, binary = directory / 'check.c', directory / 'check'
        source.write_text(text)
        # The shim uses setjmp rather than the production x86 SEH machinery.
        # GCC's conservative clobber warning concerns that host-only mechanism.
        command = ['cc', '-std=c11', '-O2', '-fwrapv', '-Wall', '-Wextra', '-Werror', '-Wno-clobbered',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        if platform == 'xbox':
            command.append('-DSARCH_XBOX=1')
        subprocess.run(command + [str(source), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
        if output is not None:
            output.mkdir(parents=True, exist_ok=True)
            (output / ('production-' + platform + '.c')).write_text(text)
    return {'platform': platform, 'source_mode': 'assembled-source' if source_root else 'patch-postimage',
            'function_sha256': {name: hashlib.sha256(body.encode()).hexdigest()
                                for name, body in bodies.items()},
            'native_execution_qualified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--platform', choices=('xbox', 'nt'), default='xbox')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.platform, args.source_root, args.output), sort_keys=True))


if __name__ == '__main__':
    main()
