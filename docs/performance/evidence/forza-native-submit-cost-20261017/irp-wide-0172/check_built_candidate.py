#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate exact built source/index and the linked GPL IRP initializer only."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', type=Path, required=True, help='baseline work directory')
p.add_argument('--candidate', type=Path, required=True, help='candidate work directory')
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
sha = lambda data: hashlib.sha256(data).hexdigest()
def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args], text=True)
def index(source):
    data = git(source, 'ls-files', '--stage')
    return data, {line.split('\t', 1)[1]: line.split('\t', 1)[0]
                  for line in data.splitlines()}
old, new = a.baseline / 'source', a.candidate / 'source'
old_data, old_index = index(old)
new_data, new_index = index(new)
changed = [name for name in sorted(set(old_index) | set(new_index))
           if old_index.get(name) != new_index.get(name)]
assert changed == ['ntoskrnl/io/iomgr/irp.c'], changed
for source in (old, new):
    assert not git(source, 'diff', '--name-only').strip(), 'unstaged tracked changes'
    assert not git(source, 'ls-files', '--others', '--exclude-standard').strip(), 'untracked source'
    assert not git(source, 'ls-files', '--others', '--ignored', '--exclude-standard').strip(), 'ignored source'
file = Path('ntoskrnl/io/iomgr/irp.c')
# Reverse only the intended helper insertion and reset call, then compare every
# byte of the approved GPL source file, including original programmer notices.
candidate_text = (new / file).read_text()
start = candidate_text.index('/*\n * Clear every packet byte without rounding past its extent.')
end = candidate_text.index('/*\n * @implemented\n */\nVOID\nNTAPI\nIoInitializeIrp(', start)
restored = candidate_text[:start] + candidate_text[end:]
restored = restored.replace('IopClearIrpPacket(Irp, PacketSize);', 'RtlZeroMemory(Irp, PacketSize);')
assert restored == (old / file).read_text(), 'unexpected IRP source change'
shapes = {}
for label, work in [('baseline', a.baseline), ('candidate', a.candidate)]:
    pe = work / 'build/ntoskrnl/xboxkrnl.unstripped.exe'
    cmd = ['objdump', '-d', '--disassemble=_IoInitializeIrp@12', str(pe)]
    disasm = subprocess.check_output(cmd, text=True)
    (a.output / ('linked-' + label + '-IoInitializeIrp.txt')).write_text(disasm)
    wide = re.findall(r'^([0-9a-f]+):\s+f3 ab\s+rep stos\s+%eax', disasm, re.M)
    byte = re.findall(r'^([0-9a-f]+):\s+f3 aa\s+rep stos\s+%al', disasm, re.M)
    shapes[label] = {'pe_sha256': sha(pe.read_bytes()), 'command': cmd,
                     'rep_stosl_addresses': wide, 'rep_stosb_addresses': byte,
                     'disassembly_sha256': sha(disasm.encode())}
assert not shapes['baseline']['rep_stosl_addresses'], 'baseline already has wide reset'
assert len(shapes['candidate']['rep_stosl_addresses']) == 1, 'candidate wide reset absent/duplicated'
assert len(shapes['candidate']['rep_stosb_addresses']) == 1, 'candidate exact byte fallback/tail absent'
flash = a.candidate.parent / 'flash.bin'
receipt = {'scope': 'Metadata-only full source index comparison; approved GPL irp.c text and named initializer disassembly. No prohibited implementation bodies inspected.',
           'baseline_index_sha256': sha(old_data.encode()), 'candidate_index_sha256': sha(new_data.encode()),
           'indexed_file_count': len(new_index), 'changed_index_paths': changed,
           'unstaged_untracked_ignored_source_files': [],
           'baseline_irp_sha256': sha((old / file).read_bytes()),
           'candidate_irp_sha256': sha((new / file).read_bytes()),
           'only_intended_helper_and_call_change': True,
           'flash_sha256': sha(flash.read_bytes()), 'linked_shape': shapes}
(a.output / 'built-source-linked-validation.json').write_text(json.dumps(receipt, indent=2) + '\n')
print('PASS: source index differs only in irp.c; exact intended source change; linked REP STOSL and byte fallback/tail')
print('flash_sha256=' + receipt['flash_sha256'])
