#!/usr/bin/env python3
"""Generate the fixture's public optical bytes independently of guest output."""
import hashlib
from pathlib import Path
root = Path(__file__).resolve().parent
payload = bytes(((offset * 37) ^ (offset >> 8) ^ (offset >> 17) ^ 0xa7) & 255
                for offset in range(4 * 1024 * 1024))
(root / 'bin').mkdir(exist_ok=True)
(root / 'bin' / 'owned-data.bin').write_bytes(payload)
print(hashlib.sha256(payload).hexdigest())
