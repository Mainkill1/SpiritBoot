#!/usr/bin/env python3
"""Build the optional plugin against the exact xemu tree used for profiling."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--xemu-source", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
header = args.xemu_source.resolve() / "include/qemu/qemu-plugin.h"
source = Path(__file__).resolve().parents[1] / "tools/profiling/tb_frequency.c"
if not header.is_file():
    parser.error("pinned xemu plugin header not found")
args.output.mkdir(parents=True, exist_ok=False)
flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs", "glib-2.0"], text=True))
command = ["cc", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Wno-unused-parameter", "-Werror",
           "-I" + str(header.parent), str(source), "-o", str(args.output / "tb_frequency.so"), *flags]
subprocess.run(command, check=True)
manifest = {"schema": 1, "xemu_source_revision": subprocess.check_output(
    ["git", "-C", str(args.xemu_source), "rev-parse", "HEAD"], text=True).strip(),
    "command": command, "inputs": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (header, source)},
    "plugin_sha256": hashlib.sha256((args.output / "tb_frequency.so").read_bytes()).hexdigest()}
(args.output / "build.json").write_text(json.dumps(manifest, indent=2) + "\n")
