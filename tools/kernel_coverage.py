#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""A pinned test-source inventory, deliberately not a native execution oracle."""
import argparse
import ast
from bisect import bisect_right
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

LEVELS = ('direct_invocation', 'symbol_reference', 'manual_contract', 'untested')
IDENTIFIER = re.compile(r'^[A-Za-z_][A-Za-z_0-9]*$')


def parse_exports(text):
    """Parse the small supported CC0 .def dialect; reject ambiguity."""
    rows, names, ordinals = [], set(), set()
    started = False
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split(';', 1)[0].strip()
        if not line or line.startswith('LIBRARY '):
            continue
        if line == 'EXPORTS' and not started:
            started = True
            continue
        if not started:
            raise ValueError('unexpected export preamble')
        match = re.fullmatch(r'(@?[A-Za-z_][A-Za-z_0-9]*(?:@\d+)?)\s+@\s+(\d+)\s+NONAME(?:\s+(DATA))?', line)
        if not match:
            raise ValueError(f'malformed export declaration at line {number}')
        decorated, ordinal, data = match.groups()
        ordinal = int(ordinal)
        if decorated.startswith('@'):
            part = re.fullmatch(r'@([A-Za-z_][A-Za-z_0-9]*)@(\d+)', decorated)
            if not part:
                raise ValueError('malformed fastcall declaration')
            name, width = part.groups()
            convention, width = 'fastcall', int(width)
        elif '@' in decorated:
            name, width = decorated.rsplit('@', 1)
            convention, width = 'stdcall', int(width)
        else:
            name, convention, width = decorated, 'cdecl', 0
        if ordinal <= 0 or ordinal > 65535 or name in names or ordinal in ordinals or (data and '@' in decorated):
            raise ValueError('duplicate/invalid export identity')
        names.add(name)
        ordinals.add(ordinal)
        rows.append({'ordinal': ordinal, 'name': name, 'kind': 'data' if data else 'callable',
                     'calling_convention': None if data else convention,
                     'argument_bytes': None if data else width})
    if not rows:
        raise ValueError('empty export inventory')
    return sorted(rows, key=lambda row: row['ordinal'])


def _clean_c(text):
    # Keep line/offset identity while removing comments and literal contents.
    out = list(text)
    i = 0
    while i < len(text):
        if text.startswith('//', i):
            end = text.find('\n', i)
            while end >= 0 and text[i:end].rstrip('\r').endswith('\\'):
                end = text.find('\n', end + 1)
            end = len(text) if end < 0 else end
        elif text.startswith('/*', i):
            close = text.find('*/', i + 2)
            if close < 0:
                raise ValueError('unterminated C comment')
            end = close + 2
        elif text[i] in ('"', "'"):
            # #error/#warning tokens are diagnostic prose, not C literals.
            # Comments still use the ordinary scanner, including across lines.
            prefix = text[text.rfind('\n', 0, i) + 1:i]
            if re.match(r'^\s*#\s*(?:error|warning)\b', prefix):
                i += 1
                continue
            quote, end = text[i], i + 1
            while end < len(text):
                if text[end] == '\\':
                    end += 2
                elif text[end] == quote:
                    end += 1
                    break
                elif text[end] == '\n':
                    raise ValueError('unterminated C literal')
                else:
                    end += 1
            else:
                raise ValueError('unterminated C literal')
        else:
            i += 1
            continue
        for index in range(i, min(end, len(out))):
            if out[index] != '\n':
                out[index] = ' '
        i = end
    return ''.join(out)


def scan_c(text, exports):
    """Lexical call sites in ordinary function bodies, never execution proof.

    All conditional regions are downgraded because no compiler flags are inferred.
    This is a bounded C lexer, not a semantic C parser or a call graph.
    """
    clean = _clean_c(text)
    lines = clean.splitlines(keepends=True)
    conditional, depth, continued = {}, 0, False
    for number, line in enumerate(lines, 1):
        directive = re.match(r'^\s*#\s*([A-Za-z_]+)', line)
        conditional[number] = depth > 0
        if directive or continued:
            if directive:
                word = directive.group(1)
                if word in ('if', 'ifdef', 'ifndef'):
                    depth += 1
                elif word in ('else', 'elif') and depth == 0:
                    raise ValueError('unmatched conditional directive')
                elif word == 'endif':
                    depth -= 1
                    if depth < 0:
                        raise ValueError('unmatched endif')
            continued = line.rstrip('\r\n').rstrip().endswith('\\')
            lines[number - 1] = ''.join('\n' if char == '\n' else ' ' for char in line)
    if depth or continued:
        raise ValueError('unterminated preprocessor region')
    clean = ''.join(lines)
    newline_offsets = [-1] + [m.start() for m in re.finditer('\n', clean)]
    tokens = [(m.group(), bisect_right(newline_offsets, m.start()))
              for m in re.finditer(r'[A-Za-z_][A-Za-z_0-9]*|->|[^\s]', clean)]
    pairs, stack = {}, []
    closing = {')': '(', '}': '{', ']': '['}
    for index, (value, _) in enumerate(tokens):
        if value in ('(', '{', '['):
            stack.append(index)
        elif value in closing:
            if not stack or tokens[stack[-1]][0] != closing[value]:
                raise ValueError('unbalanced C delimiters')
            first = stack.pop()
            pairs[index], pairs[first] = first, index
    if stack:
        raise ValueError('unbalanced C delimiters')
    bodies, braces = [], 0
    for index, (value, _) in enumerate(tokens):
        if value == '{':
            if braces == 0 and index and tokens[index - 1][0] == ')':
                opening = pairs[index - 1]
                if opening and IDENTIFIER.fullmatch(tokens[opening - 1][0]):
                    name = tokens[opening - 1][0]
                    if name not in ('if', 'while', 'for', 'switch'):
                        bodies.append((index, pairs[index], name))
            braces += 1
        elif value == '}':
            braces -= 1
    sites = []
    for index, (name, line) in enumerate(tokens):
        if name not in exports:
            continue
        body = next((b for b in bodies if b[0] < index < b[1]), None)
        previous = tokens[index - 1][0] if index else ''
        following = tokens[index + 1][0] if index + 1 < len(tokens) else ''
        # Export function declarations/definitions at file scope are not tests.
        if body is None and following == '(':
            continue
        declaration_like = bool(IDENTIFIER.fullmatch(previous)) and previous != 'return'
        direct = (exports[name] == 'callable' and body is not None and following == '(' and
                  previous not in ('.', '->') and not declaration_like and not conditional.get(line, False))
        sites.append({'name': name, 'line': line, 'function': body[2] if body else None,
                      'level': 'direct_invocation' if direct else 'symbol_reference',
                      'conditional_context': conditional.get(line, False),
                      'native_execution_qualified': False})
    return sites


def _pinned(descriptor, roots):
    if set(descriptor) != {'scope', 'path', 'sha256'} or descriptor['scope'] not in roots:
        raise ValueError('invalid source descriptor/scope')
    relative = PurePosixPath(descriptor['path'])
    if relative.is_absolute() or not relative.parts or any(p in ('', '.', '..') for p in relative.parts) or '\\' in str(relative):
        raise ValueError('unsafe source path')
    root = roots[descriptor['scope']].resolve()
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root) or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('missing/unsafe/bounded source input: ' + str(relative))
    data = path.read_bytes()
    if not re.fullmatch(r'[0-9a-f]{64}', descriptor['sha256']) or hashlib.sha256(data).hexdigest() != descriptor['sha256']:
        raise ValueError('source SHA-256 differs: ' + str(relative))
    return data.decode('utf-8')


def build_report(manifest, source_root, product_root):
    required = {'schema_version', 'source_identity', 'exports', 'expected_counts', 'test_sources',
                'supporting_sources', 'manual_contracts', 'exclusions'}
    if set(manifest) != required or manifest['schema_version'] != 1:
        raise ValueError('unsupported coverage manifest schema')
    roots = {'assembled': Path(source_root), 'product': Path(product_root)}
    descriptors = [manifest['exports']] + manifest['test_sources'] + manifest['supporting_sources']
    sources = {}
    for descriptor in descriptors:
        key = descriptor['scope'] + ':' + descriptor['path']
        if key in sources:
            raise ValueError('duplicate source descriptor')
        sources[key] = _pinned(descriptor, roots)
    export_key = manifest['exports']['scope'] + ':' + manifest['exports']['path']
    exports = parse_exports(sources[export_key])
    counts = {'total': len(exports), 'callable': sum(x['kind'] == 'callable' for x in exports),
              'data': sum(x['kind'] == 'data' for x in exports)}
    if counts != manifest['expected_counts']:
        raise ValueError('export inventory counts differ')
    by_name = {row['name']: dict(row, evidence=[]) for row in exports}
    tests = set()
    for descriptor in manifest['test_sources']:
        key = descriptor['scope'] + ':' + descriptor['path']
        tests.add(key)
        if key.endswith('.py'):
            ast.parse(sources[key])
            continue  # Manual host-invoker mapping; never scan Python strings for calls.
        if not key.endswith(('.c', '.h')):
            raise ValueError('unsupported test-source language')
        try:
            sites = scan_c(sources[key], {row['name']: row['kind'] for row in exports})
        except ValueError as error:
            raise ValueError(key + ': ' + str(error)) from error
        for site in sites:
            name = site.pop('name')
            by_name[name]['evidence'].append(dict(site, source=key))
    contracts, ids = [], set()
    contract_keys = {'id', 'description', 'exports', 'evidence', 'test_sources', 'gaps'}
    for contract in manifest['manual_contracts']:
        if set(contract) != contract_keys or not contract['id'] or contract['id'] in ids:
            raise ValueError('invalid/duplicate manual contract or unsupported execution claim')
        ids.add(contract['id'])
        if not contract['evidence'] or not contract['test_sources'] or not contract['gaps']:
            raise ValueError('manual contracts require evidence, tests and explicit remaining gaps')
        if any(key not in sources for key in contract['evidence']) or any(key not in tests for key in contract['test_sources']):
            raise ValueError('unbound manual contract evidence/test source')
        for name in contract['exports']:
            if name not in by_name:
                raise ValueError('unknown manually mapped export')
            by_name[name]['evidence'].append({'level': 'manual_contract', 'contract_id': contract['id'],
                                             'native_execution_qualified': False})
        contracts.append(dict(contract, level='manual_contract', native_execution_qualified=False))
    rows = []
    for export in exports:
        row = by_name[export['name']]
        row['evidence'].sort(key=lambda e: (LEVELS.index(e['level']), e.get('source', ''), e.get('line', 0), e.get('contract_id', '')))
        row['level'] = min((e['level'] for e in row['evidence']), key=LEVELS.index, default='untested')
        row['native_execution_qualified'] = False
        rows.append(row)
    histogram = Counter(row['level'] for row in rows)
    canonical = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
    return {'schema_version': 1, 'kind': 'pinned-kernel-test-source-inventory',
            'source_identity': manifest['source_identity'],
            'input_manifest_semantic_sha256': hashlib.sha256(canonical).hexdigest(),
            'all_kernel_covered': False,
            'summary': dict(counts, by_level={level: histogram[level] for level in LEVELS},
                            native_execution_qualified_exports=0, test_source_files=len(tests),
                            manual_contracts=len(contracts)),
            'limitations': ['Direct invocation means a lexical callsite in a test function body, not proven symbol binding, reachability or execution.',
                            'Conditional regions, address-taken references and declaration-like sites receive symbol-reference evidence only.',
                            'Compiler preprocessing, local shadowing, macro expansion, call graphs, function pointers, internal paths and line/branch coverage are not resolved.',
                            'No native receipts are imported or authenticated. Historical documents remain manual evidence only.',
                            'Missing source evidence means untested in this inventory, not proof that no test exists elsewhere.'],
            'inputs': descriptors, 'exports': rows, 'internal_contracts': contracts,
            'exclusions': manifest['exclusions']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--manifest', type=Path, default=Path('sources/kernel-coverage-inputs.json'))
    parser.add_argument('--output', type=Path, default=Path('sources/kernel-coverage-report.json'))
    parser.add_argument('--check', action='store_true', help='reject stale committed report without rewriting it')
    args = parser.parse_args(argv)
    try:
        product = Path(__file__).resolve().parents[1]
        manifest = json.loads(args.manifest.read_text())
        report = build_report(manifest, args.source_root, product)
        output = json.dumps(report, indent=2, sort_keys=True) + '\n'
        if args.check:
            if args.output.read_text() != output:
                raise ValueError('coverage report is stale')
        else:
            args.output.write_text(output)
        print(json.dumps(report['summary'], sort_keys=True))
        return 0
    except (ValueError, OSError, UnicodeError, TypeError, KeyError) as error:
        print('kernel coverage inventory rejected: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
