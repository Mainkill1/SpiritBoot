# SPDX-License-Identifier: MIT
"""Verify cumulative observer patch against public Git objects, without edits."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def verify(repository):
    record = json.loads((HERE / 'xemu-source-provenance.json').read_text())
    patch = HERE / record['patch']
    digest = lambda data: hashlib.sha256(data).hexdigest()
    if digest(patch.read_bytes()) != record['patch_sha256']:
        raise ValueError('Cumulative patch hash mismatch')
    with tempfile.TemporaryDirectory(prefix='forza-observer-clean-') as temporary:
        root = Path(temporary)
        for name, expected in record['base_sha256'].items():
            data = subprocess.check_output([
                'git', '-C', str(repository), 'show',
                record['base_commit'] + ':' + name])
            if digest(data) != expected:
                raise ValueError('Base source hash mismatch: ' + name)
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=root, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=root, check=True)
        actual = {name: digest((root / name).read_bytes())
                  for name in record['result_sha256']}
        if actual != record['result_sha256']:
            raise ValueError('Patched source differs from captured source')
    return {'base_commit': record['base_commit'], 'clean_apply': True,
            'exact_captured_source_hashes': actual, 'rebuild_performed': False,
            'repository_unchanged': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.repository), indent=2))
