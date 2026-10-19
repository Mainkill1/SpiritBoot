#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Reproduce the owned 0168/0169 linked dispatch comparison; never modify builds."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[4]
inputs = {
    'baseline0168': ('artifacts/forza-bookkeeping-release64',
                     '2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6',
                     '2716b75a7159254904b4c7a9282f2c51961ee510'),
    'candidate0169': ('artifacts/forza-static-ports-release64',
                      'c7dcfe9214d422ef0477e10a2ff552e08f6c78db0675085ad6cf88eef44a5527',
                      '261b24f5a7ae667cc8f39670b706112aafe3c285'),
}
results = {}
for name, (directory, flash_hash, tree) in inputs.items():
    directory = root / directory
    build = json.loads((directory / 'build.json').read_text())
    assert build['status'] == 'built' and build['source_tree'] == tree
    assert build['flash_sha256'] == flash_hash
    assert hashlib.sha256((directory / 'flash.bin').read_bytes()).hexdigest() == flash_hash
    image = root / build['build_directory'].removeprefix('/work/') / 'ntoskrnl/xboxkrnl.unstripped.exe'
    assembly = subprocess.check_output(['objdump', '-d', str(image)], text=True)
    prefix = '_port_' if name == 'baseline0168' else '_nx_native_port_'
    names = ['_run_pump', '_lock', '_unlock', '_pending'] + [prefix + suffix for suffix in
             ('enter', 'leave', 'prepare', 'submit', 'retire', 'cancel', 'complete')]
    functions = {}
    for function in names:
        matches = list(re.finditer(r'^([0-9a-f]+) <' + re.escape(function) +
                                  r'>:\n(.*?)(?=\n[0-9a-f]+ <|\Z)', assembly, re.M | re.S))
        assert len(matches) <= 1, function
        if not matches:
            functions[function] = None
            continue
        match = matches[0]
        calls = [line.strip() for line in match[2].splitlines() if re.search(r'\b(?:call|jmp)\s', line)]
        indirect = [line for line in calls if re.search(r'\b(?:call|jmp)\s+\*', line)]
        functions[function] = {'address': match[1], 'indirect_sites': len(indirect),
                               'call_sites': sum(bool(re.search(r'\bcall\s', line)) for line in calls),
                               'indirect_instructions': indirect,
                               'calls': [line for line in calls if re.search(r'\bcall\s', line)]}
    results[name] = {'flash_sha256': flash_hash, 'source_tree': tree,
                     'owned_image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
                     'functions': functions}

old = results['baseline0168']['functions']
new = results['candidate0169']['functions']
assert old['_run_pump']['indirect_sites'] == 7
assert old['_lock']['indirect_sites'] == old['_unlock']['indirect_sites'] == 1
assert old['_pending']['indirect_sites'] == 1
assert new['_run_pump']['indirect_sites'] == new['_pending']['indirect_sites'] == 0
assert new['_lock'] is None and new['_unlock'] is None
assert all(new['_nx_native_port_' + name] for name in
           ('enter', 'leave', 'prepare', 'submit', 'retire', 'cancel', 'complete'))
print(json.dumps({'scope': 'owned linked code shape; not latency evidence', 'builds': results}, indent=2))
