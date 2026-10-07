#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
from pathlib import Path
import subprocess
import sys
root, output = map(Path, sys.argv[1:3])
here = Path(__file__).resolve().parent
output.mkdir(parents=True, exist_ok=True)
supply = (root / 'ntoskrnl/xb/mm/pagesupply.c').read_text()
api = (root / 'ntoskrnl/xb/mm/api.c').read_text()
body = supply[:supply.index('/*\n * Frame ownership:')] + '\n#endif\n'
body += supply[supply.index('BOOLEAN\nNxkPageSupplyIsFree'):supply.index('BOOLEAN\nNxkPageSupplyTakeSpecific')]
body += api[api.index('/* LOCK / UNLOCK '):api.index('/* QUERIES ')]
# Count real scalar stores without altering production sources.
body = body.replace('NxpPinBatch[Page] = 0;', '{ NxpPinBatch[Page] = 0; cleared += sizeof(USHORT); }')
(output / 'pins-actual.inc').write_text(body)
diagnostics = ['-DDBG=1', '-DNXK_PIN_BATCH_DIAGNOSTICS'] if '--diagnostics' in sys.argv else []
subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra'] + diagnostics + ['-I' + str(here.parent / 'clean-room/include'), '-I' + str(output), '-I' + str(root / 'ntoskrnl/xb/mm'), str(here / 'pins.c'), '-o', str(output / 'pins')], check=True)
subprocess.run([str(output / 'pins'), '1' if '--optimized' in sys.argv else '0'], check=True)
