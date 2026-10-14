#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Freeze a short ordinary inline PowerShell call to the exact owned module.

Runtime placeholders belong only to runner-provided context. All expectations
are immutable literals. The loader executes the same source bytes it hashes;
it changes no execution policy and opens no monitor connection.
"""
import argparse
import json
from pathlib import PureWindowsPath
import re


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def make_arguments(expected, module_sha256, stage):
    required = {'expected_package', 'expected_job', 'expected_device',
                'expected_xemu_sha256', 'expected_config_sha256',
                'expected_recorder_sha256', 'expected_target_sha256'}
    if set(expected) != required or stage not in ('initial', 'final'):
        raise ValueError('exact frozen expectations and stage are required')
    for field in (*sorted(key for key in required if key.endswith('_sha256')),):
        if not isinstance(expected[field], str) or not re.fullmatch('[0-9a-f]{64}', expected[field]):
            raise ValueError('invalid frozen hash: ' + field)
    if not re.fullmatch('[0-9a-f]{64}', module_sha256):
        raise ValueError('invalid module SHA256')
    package = expected['expected_package']
    if (not isinstance(package, str) or not PureWindowsPath(package).is_absolute()
            or any(part == '..' for part in PureWindowsPath(package).parts)
            or any(char in package for char in "\r\n{}'")):
        raise ValueError('pin a literal absolute owned Windows package')
    if not re.fullmatch('pr248-native-[a-z0-9-]+', expected['expected_job']):
        raise ValueError('invalid owned job identity')
    if expected['expected_device'] != 'ide0-cd1':
        raise ValueError('unsupported predeclared device hypothesis')
    context = "stage=" + literal(stage) + ";wrapper_pid=[int]'{pid}';package='{packageDir}';result='{resultDir}'"
    pinned = ';'.join(key + '=' + literal(expected[key]) for key in sorted(expected))
    command = (
        "$ErrorActionPreference='Stop';"
        "$Pr248Source=[IO.File]::ReadAllBytes('{packageDir}\\dvd-route-windows-guard.ps1');"
        "$Pr248Hash=[Security.Cryptography.SHA256]::Create();"
        "try{$Pr248Actual=[BitConverter]::ToString($Pr248Hash.ComputeHash($Pr248Source)).Replace('-','').ToLowerInvariant()}"
        "finally{$Pr248Hash.Dispose()};"
        "if($Pr248Actual -cne " + literal(module_sha256) + "){throw 'Frozen DVD guard source differs'};"
        ". ([scriptblock]::Create([Text.Encoding]::UTF8.GetString($Pr248Source)));"
        "Invoke-Pr248DvdGuard @{" + context + ';' + pinned + '}')
    # Leave substantial space for runner expansion and CreateProcess quoting.
    if len(command) > 12000:
        raise ValueError('owned inline command exceeds bounded size')
    return ['-NoProfile', '-NonInteractive', '-Command', command]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected', required=True)
    parser.add_argument('--module-sha256', required=True)
    parser.add_argument('--stage', required=True, choices=('initial', 'final'))
    args = parser.parse_args()
    with open(args.expected, encoding='utf-8') as stream:
        expected = json.load(stream)
    print(json.dumps(make_arguments(expected, args.module_sha256, args.stage)))


if __name__ == '__main__':
    main()
