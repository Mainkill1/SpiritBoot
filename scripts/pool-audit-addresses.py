#!/usr/bin/env python3
"""Pin the owned diagnostic guest to its compiled kernel symbols and header."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("build", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
manifest = json.loads(args.build.read_text())
if manifest.get("status") != "built" or not manifest.get("pool_audit"):
    raise SystemExit("a successful --pool-audit build is required")
kernel = Path(manifest["build_directory"]) / "ntoskrnl/xboxkrnl.unstripped.exe"
symbols = subprocess.check_output(["i686-w64-mingw32-nm", "-n", str(kernel)], text=True)
addresses = {}
for line in symbols.splitlines():
    fields = line.split()
    if len(fields) == 3 and fields[2] in ("_NxpPoolCensusData", "_NxpPoolAudit"):
        if fields[2] in addresses:
            raise SystemExit("ambiguous owned diagnostic symbol")
        addresses[fields[2]] = int(fields[0], 16)
if set(addresses) != {"_NxpPoolCensusData", "_NxpPoolAudit"}:
    raise SystemExit("compiled diagnostic symbols are missing")
header = Path(manifest["source_directory"]) / "ntoskrnl/xb/mm/pool-census.h"
args.output.write_text("#define CENSUS_ADDRESS 0x%xU\n#define AUDIT_ADDRESS 0x%xU\n" %
                       (addresses["_NxpPoolCensusData"], addresses["_NxpPoolAudit"]))
receipt = {"source_tree": manifest["source_tree"], "flash_sha256": manifest["flash_sha256"],
           "kernel_sha256": hashlib.sha256(kernel.read_bytes()).hexdigest(),
           "header_sha256": hashlib.sha256(header.read_bytes()).hexdigest(),
           "addresses": addresses}
args.output.with_suffix(".json").write_text(json.dumps(receipt, indent=2) + "\n")
