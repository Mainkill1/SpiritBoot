#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile extracted bodies to i386; require a native REP STOSL.

Freestanding host IRP model: proves helper code shape, not firmware ABI/linkage.
Final firmware disassembly remains a separate release gate.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from check_irp_reset import PLATFORM, body

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
src = (a.source_root / 'ntoskrnl/io/iomgr/irp.c').read_text()
functions = ''
if '\nIopClearIrpPacket(' in src:
    functions += body(src, 'IopClearIrpPacket')
functions += body(src, 'IoInitializeIrp') + body(src, 'IoReuseIrp')
platform = re.sub(r'^#include .*\n', '', PLATFORM, flags=re.M)
platform = '''typedef __SIZE_TYPE__ size_t;
typedef __UINTPTR_TYPE__ uintptr_t;
typedef __INT32_TYPE__ int32_t;
typedef __UINT32_TYPE__ uint32_t;
#define assert(x) ((void)0)
void *memset(void *, int, __SIZE_TYPE__);
''' + platform
# The model's APC source is observable to prevent constant-folding header state.
platform = platform.replace('static struct { UCHAR ApcStateIndex; } current_thread;',
                            'extern struct { UCHAR ApcStateIndex; } current_thread;')
a.output.mkdir(parents=True, exist_ok=True)
cfile = a.output / 'extracted.c'
notice = src[:src.index('/* INCLUDES')]
cfile.write_text(notice + platform + functions)
assembly = a.output / 'extracted.s'
command = ['gcc', '-m32', '-march=pentium', '-Os', '-fno-strict-aliasing',
           '-fno-inline', '-fno-pic', '-fno-asynchronous-unwind-tables',
           '-S', str(cfile), '-o', str(assembly)]
subprocess.run(command, check=True)
text = assembly.read_text()
# The helper, if present, must own the store: unrelated stores do not qualify.
name = 'IopClearIrpPacket' if functions.startswith('VOID NTAPI IopClearIrpPacket') else 'IoInitializeIrp'
section = text.split(name + ':\n', 1)[1].split('\n\t.size', 1)[0]
wide = bool(re.search(r'\brep\s+stosl\b', section))
receipt = {'source_sha256': hashlib.sha256(src.encode()).hexdigest(),
           'extracted_sha256': hashlib.sha256(cfile.read_bytes()).hexdigest(),
           'assembly_sha256': hashlib.sha256(assembly.read_bytes()).hexdigest(),
           'compiler': subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
           'command': command, 'native_rep_stosl': wide,
           'scope': 'i386 extracted helper/model only; not final linked firmware'}
(a.output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(('PASS' if wide else 'FAIL') + ': native REP STOSL ' + ('present' if wide else 'absent'))
raise SystemExit(0 if wide else 1)
