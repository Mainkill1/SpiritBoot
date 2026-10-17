#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Print one frozen external recipe for the supported Windows USER runner job.

Only emits metadata. Runtime ownership is checked by the exact hashed guards;
this builder does not launch, attach, submit, or prove declared expectations.
"""
import argparse
import json
from pathlib import Path, PureWindowsPath
import re

SOURCE_NAMES = {'allocation_ledger.py', 'support.py', 'capture_owned_fixture.py',
                'operation_boundaries.py', 'rsp_transport.py', 'selected-binding.json',
                'fixture-binding.json', 'dvd-route-windows-guard.ps1', 'windows-allocation-guard.ps1'}
EXPECTED_NAMES = {'expected_config_sha256', 'expected_flash_sha256', 'expected_iso_sha256',
                  'expected_job', 'expected_launcher_sha256', 'expected_package',
                  'expected_xemu_sha256', 'gdb_port', 'kernel_sha256', 'python_executable', 'source_pins'}


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def make_recipe(expected, stage):
    if set(expected) != EXPECTED_NAMES or stage not in ('before-gdb', 'capture'):
        raise ValueError('exact frozen expectations and supported stage required')
    if not isinstance(expected['source_pins'], dict) or set(expected['source_pins']) != SOURCE_NAMES:
        raise ValueError('complete exact source/profile pins required')
    hashes = [expected[key] for key in EXPECTED_NAMES if key.endswith('_sha256')]
    hashes += list(expected['source_pins'].values())
    if any(not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value) for value in hashes):
        raise ValueError('literal SHA256 expectations required')
    job = expected['expected_job']
    if not isinstance(job, str) or not re.fullmatch('pr248-native-[a-z0-9-]+', job):
        raise ValueError('literal owned job identity required')
    for key in ('expected_package', 'python_executable'):
        value = expected[key]
        if (not isinstance(value, str) or not PureWindowsPath(value).is_absolute() or
                '..' in PureWindowsPath(value).parts or any(char in value for char in '\r\n{}')):
            raise ValueError('literal absolute Windows path required: ' + key)
    if PureWindowsPath(expected['expected_package']).name != 'agent-' + job:
        raise ValueError('package must identify the declared owned job')
    if PureWindowsPath(expected['python_executable']).suffix.lower() != '.exe':
        raise ValueError('explicit observed Python executable required')
    if type(expected['gdb_port']) is not int or not 1024 <= expected['gdb_port'] <= 65535:
        raise ValueError('explicit loopback diagnostic port required')
    command = "$ErrorActionPreference='Stop';"
    for name in ('dvd-route-windows-guard.ps1', 'windows-allocation-guard.ps1'):
        command += (
            "$Pr248Bytes=[IO.File]::ReadAllBytes('{packageDir}\\" + name + "');"
            "$Pr248Hasher=[Security.Cryptography.SHA256]::Create();"
            "try{$Pr248Digest=[BitConverter]::ToString($Pr248Hasher.ComputeHash($Pr248Bytes)).Replace('-','').ToLowerInvariant()}"
            "finally{$Pr248Hasher.Dispose()};"
            "if($Pr248Digest -cne " + literal(expected['source_pins'][name]) + "){throw 'Frozen allocation guard source differs'};"
            ". ([scriptblock]::Create([Text.Encoding]::UTF8.GetString($Pr248Bytes)));"
        )
    values = [key + '=' + literal(str(expected[key])) for key in sorted(EXPECTED_NAMES - {'source_pins'})]
    pins = ';'.join(literal(name) + '=' + literal(expected['source_pins'][name]) for name in sorted(SOURCE_NAMES))
    command += ("Invoke-Pr248AllocationGuard @{wrapper_pid=[int]'{pid}';package='{packageDir}';result='{resultDir}';"
                + ';'.join(values) + ';source_pins=@{' + pins + '};stage=' + literal(stage) + '}')
    if len(command) > 12000:
        raise ValueError('bounded inline command size exceeded')
    return dict(id='allocation-' + stage + '-guard', type='external', durationMs=100000,
                pauseBefore=False, pauseAfter=False, resumeDuring=False,
                toolExecutable='C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
                toolArguments=['-NoProfile', '-NonInteractive', '-Command', command], toolWorkingDirectory='.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected', type=Path, required=True)
    parser.add_argument('--stage', choices=['before-gdb', 'capture'], required=True)
    args = parser.parse_args()
    print(json.dumps(make_recipe(json.loads(args.expected.read_text()), args.stage), indent=2))
