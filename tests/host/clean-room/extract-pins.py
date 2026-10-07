# SPDX-License-Identifier: GPL-2.0-or-later
# Compile the actual supply bookkeeping and public API bodies. The omitted
# supply functions contain privileged i386 relocation assembly unavailable on
# this host. Markers fail loudly if source organization changes.
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[3]
supply = (root / 'ntoskrnl/xb/mm/pagesupply.c').read_text()
api = (root / 'ntoskrnl/xb/mm/api.c').read_text()
body = supply[:supply.index('/*\n * Frame ownership:')] + '\n#endif\n'
body += supply[supply.index('BOOLEAN\nNxkPageSupplyIsFree'):supply.index('BOOLEAN\nNxkPageSupplyTakeSpecific')]
body += api[api.index('/* LOCK / UNLOCK '):api.index('/* QUERIES ')]
Path(sys.argv[1]).write_text(body)
