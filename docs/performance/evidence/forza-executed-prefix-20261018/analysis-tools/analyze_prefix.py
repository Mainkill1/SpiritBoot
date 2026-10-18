# SPDX-License-Identifier: MIT
"""Validate bounded instruction-prefix observations; no elapsed CPU estimate."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess


SCHEMA = {
    'prefix_meta': ({'version', 'descriptors', 'rows', 'translations', 'overflow',
                     'reentry', 'thread_mismatch', 'invalid_prefix', 'open_api'}, {'excluded_rows'}),
    'prefix_tb': ({'id', 'pc', 'count', 'generation', 'born_api', 'born_identity_seq'},
                  {'flags', 'cflags', 'cs_base'}),
    'prefix_insn': ({'tb', 'ordinal', 'pc', 'rep'}, set()),
    'prefix_row': ({'api', 'identity_seq', 'tb', 'first', 'last', 'executions', 'begun'},
                   {'rep_iterations'}),
    'prefix_translation': ({'api', 'identity_seq', 'tb'}, set()),
    'prefix_end': ({'rows'}, {'excluded_rows'}),
    'prefix_limits': ({'handle','max_api','admitted','returned','admission_closed','range_count'}, set()),
    'prefix_range': ({'id','start','end'}, set()),
    'prefix_health': ({'allocated_descriptors','allocated_instructions','descriptor_overflow',
        'instruction_overflow','row_overflow','excluded_overflow','max_probe','max_excluded_probe'}, set()),
    'prefix_invalid': ({'reason','count'}, set()),
    'prefix_bad': ({'index','reason','api','identity_seq','tb','segment_tb','first','last','rep',
        'rep_base','actual_pc','expected_pc','type','segment_type'}, set()),
    'prefix_excluded': ({'api','identity_seq','pc','first','last','executions','begun','rep_iterations'},set()),
}


def parse(text):
    """Fail closed on malformed, incomplete, ambiguous or overflowed captures."""
    meta = None
    end = None
    descriptors = {}
    rows = []
    translations = []
    row_keys = set()
    translation_keys = set()
    excluded = []
    excluded_keys = set()
    limits = health = None
    ranges = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        words = line.split()
        kind = words[0]
        if kind not in SCHEMA or end is not None:
            raise ValueError('Unknown record or content after footer')
        pairs = [word.split('=', 1) for word in words[1:]]
        if any(len(pair) != 2 for pair in pairs):
            raise ValueError('Malformed field')
        raw = dict(pairs)
        required, optional = SCHEMA[kind]
        if len(raw) != len(pairs) or not required <= raw.keys() or raw.keys() - required - optional:
            raise ValueError('Duplicate, missing or unknown field: '+kind)
        values = {key: int(value, 16 if key in {'pc', 'flags', 'cflags', 'cs_base',
                  'handle','start','end','actual_pc','expected_pc'} else 10)
                  for key, value in raw.items()}
        if any(value < 0 for value in values.values()):
            raise ValueError('Negative counter/address')
        if kind == 'prefix_meta':
            if meta is not None or descriptors or rows:
                raise ValueError('Duplicate or late header')
            meta = values
            if meta['version'] not in (1, 2) or any(meta[key] for key in
                    ['overflow', 'reentry', 'thread_mismatch', 'invalid_prefix', 'open_api']):
                raise ValueError('Unsupported or incomplete capture')
        elif meta is None:
            raise ValueError('Missing header')
        elif kind == 'prefix_tb':
            key = values['id']
            if key == 0 or key in descriptors or not 0 < values['count'] <= 512 or values['pc'] > 0xffffffff:
                raise ValueError('Invalid or duplicate TB descriptor')
            descriptors[key] = {**values, 'instructions': {}}
        elif kind == 'prefix_insn':
            desc = descriptors.get(values['tb'])
            if (desc is None or not 0 < values['ordinal'] <= desc['count'] or
                    values['ordinal'] in desc['instructions'] or values['rep'] not in (0, 1) or
                    values['pc'] > 0xffffffff):
                raise ValueError('Invalid instruction descriptor')
            desc['instructions'][values['ordinal']] = values
        elif kind == 'prefix_row':
            key = tuple(values[name] for name in ('api', 'identity_seq', 'tb', 'first', 'last'))
            if key in row_keys or values['api'] == 0 or values['identity_seq'] == 0 or values['executions'] == 0:
                raise ValueError('Invalid or duplicate histogram key')
            row_keys.add(key)
            rows.append(values)
        elif kind == 'prefix_translation':
            key = (values['api'], values['identity_seq'], values['tb'])
            if key in translation_keys or values['api'] == 0 or values['identity_seq'] == 0:
                raise ValueError('Invalid or duplicate translation')
            translation_keys.add(key)
            translations.append(values)
        elif kind == 'prefix_end':
            end = values
        elif kind in {'prefix_invalid','prefix_bad'}:
            raise ValueError('Recorder reported an invalid observation')
        elif kind == 'prefix_limits':
            if limits is not None:
                raise ValueError('Duplicate limits record')
            limits = values
        elif kind == 'prefix_health':
            if health is not None:
                raise ValueError('Duplicate health record')
            health = values
        elif kind == 'prefix_range':
            if values['id'] in ranges or not 0 <= values['start'] < values['end'] <= 0x100000000:
                raise ValueError('Duplicate or invalid owned address range')
            ranges[values['id']] = values
        elif kind == 'prefix_excluded':
            key = tuple(values[name] for name in ('api','identity_seq','pc','first','last'))
            if (key in excluded_keys or not values['api'] or not values['identity_seq'] or
                    not values['executions'] or not 1 <= values['first'] <= values['last'] <= 512 or
                    values['pc'] > 0xffffffff or
                    values['begun'] != values['executions']*(values['last']-values['first']+1)):
                raise ValueError('Invalid or duplicate excluded prefix')
            excluded_keys.add(key)
            excluded.append(values)
    if meta is None or end is None:
        raise ValueError('Truncated capture')
    if (meta['descriptors'] != len(descriptors) or meta['rows'] != len(rows) or
            meta['translations'] != len(translations) or end['rows'] != len(rows)):
        raise ValueError('Header/footer count mismatch')
    for desc in descriptors.values():
        if len(desc['instructions']) != desc['count'] or desc['instructions'][1]['pc'] != desc['pc']:
            raise ValueError('Incomplete descriptor or inconsistent first PC')
    for row in rows:
        desc = descriptors.get(row['tb'])
        if desc is None or not 1 <= row['first'] <= row['last'] <= desc['count']:
            raise ValueError('Prefix outside descriptor')
        if row['begun'] != row['executions'] * (row['last'] - row['first'] + 1):
            raise ValueError('Begun count does not match executed prefix')
        if row.get('rep_iterations', 0) and not any(desc['instructions'][n]['rep']
                for n in range(row['first'], row['last'] + 1)):
            raise ValueError('REP iterations outside a marked string instruction')
    for translation in translations:
        desc = descriptors.get(translation['tb'])
        if desc is None or translation['api'] != desc['born_api'] or translation['identity_seq'] != desc['born_identity_seq']:
            raise ValueError('Translation does not match immutable descriptor')
    if meta['version'] == 1:
        if excluded or limits is not None or health is not None or ranges or 'excluded_rows' in meta or 'excluded_rows' in end:
            raise ValueError('Version two fields in version one capture')
    else:
        if (limits is None or health is None or meta.get('excluded_rows') != len(excluded) or
                end.get('excluded_rows') != len(excluded) or limits['range_count'] != len(ranges) or not ranges):
            raise ValueError('Missing or inconsistent version two accounting')
        if (not 0 < limits['max_api'] or not 0 <= limits['admitted'] <= limits['max_api'] or
                limits['returned'] != limits['admitted'] or limits['admission_closed'] not in (0,1) or
                bool(limits['admission_closed']) != (limits['admitted'] == limits['max_api'])):
            raise ValueError('Admission cohort incomplete or outside its bounds')
        observed_apis = {record['api'] for record in rows + excluded + translations}
        if len(observed_apis) > limits['admitted']:
            raise ValueError('Observed APIs exceed declared admitted cohort')
        if (any(health[name] for name in ['descriptor_overflow','instruction_overflow','row_overflow','excluded_overflow']) or
                health['allocated_descriptors'] < len(descriptors) or
                health['allocated_instructions'] < sum(d['count'] for d in descriptors.values()) or
                max(health['max_probe'],health['max_excluded_probe']) > 128):
            raise ValueError('Invalid recorder capacity/probe accounting')
        ordered = sorted(ranges.values(), key=lambda r:r['start'])
        if any(a['end'] > b['start'] for a,b in zip(ordered,ordered[1:])):
            raise ValueError('Owned ranges overlap')
        def owned(pc):
            return any(r['start'] <= pc < r['end'] for r in ordered)
        if any(not owned(i['pc']) for d in descriptors.values() for i in d['instructions'].values()):
            raise ValueError('Owned descriptor outside declared ranges')
        if any(owned(row['pc']) for row in excluded):
            raise ValueError('Excluded runtime TB entry lies inside owned range')
    return {'meta': meta, 'descriptors': descriptors, 'rows': rows, 'translations': translations,
            'excluded': excluded, 'limits': limits, 'health': health, 'ranges': ranges}


def build_symbol_map(image):
    """Own built image only. Export symbols and PC boundaries, never code bytes."""
    text = subprocess.check_output(['objdump', '-d', str(image)], text=True)
    owner = None
    instructions = {}
    symbols = {}
    for line in text.splitlines():
        if line.startswith('Disassembly of section '):
            owner = None
        match = re.fullmatch(r'([0-9a-fA-F]+) <(.+)>:', line)
        if match:
            owner = match[2]
            symbols[owner] = int(match[1], 16)
            continue
        match = re.match(r'^\s*([0-9a-fA-F]+):\s+((?:[0-9a-fA-F]{2}\s+)+)\s*(\S.*)?$', line)
        if match and owner and match[3] and '(bad)' not in match[3]:
            pc = int(match[1], 16)
            if pc in instructions:
                raise ValueError('Ambiguous disassembly instruction PC')
            instructions[pc] = owner
    if not instructions:
        raise ValueError('Image contains no decoded instructions')
    return {'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
            'symbols': symbols, 'instruction_owners': {format(pc, '08x'): name
                for pc, name in sorted(instructions.items())},
            'limits': 'Linked enclosing symbol, not source inline attribution. Unmatched PCs stay unknown.'}


def counts_by_api(capture, symbol_map):
    result = {}
    owners = symbol_map['instruction_owners']
    for row in capture['rows'] + capture.get('excluded', []):
        api = result.setdefault(row['api'], {'begun': 0, 'prefix_executions': 0,
            'rep_iterations_known': 0, 'rows_with_unknown_rep': 0, 'symbols': Counter(),
            'unknown_pcs': Counter(), 'phases_by_identity_seq': {}, 'excluded_begun': 0})
        api['begun'] += row['begun']
        api['prefix_executions'] += row['executions']
        api['rep_iterations_known'] += row.get('rep_iterations', 0)
        api['rows_with_unknown_rep'] += 'rep_iterations' not in row
        phase = api['phases_by_identity_seq'].setdefault(row['identity_seq'], Counter())
        if 'tb' not in row:
            api['excluded_begun'] += row['begun']
            api['symbols']['<excluded>'] += row['begun']
            phase['<excluded>'] += row['begun']
            continue
        desc = capture['descriptors'][row['tb']]
        for ordinal in range(row['first'], row['last'] + 1):
            pc = format(desc['instructions'][ordinal]['pc'], '08x')
            name = owners.get(pc, '<unknown>')
            api['symbols'][name] += row['executions']
            phase[name] += row['executions']
            if name == '<unknown>':
                api['unknown_pcs'][pc] += row['executions']
    for api in result.values():
        if sum(api['symbols'].values()) != api['begun']:
            raise ValueError('Lost instructions during attribution')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--symbol-map', type=Path)
    parser.add_argument('--write-symbol-map', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if bool(args.image) == bool(args.symbol_map):
        parser.error('Provide exactly one of --image and --symbol-map')
    symbols = build_symbol_map(args.image) if args.image else json.loads(args.symbol_map.read_text())
    if args.write_symbol_map:
        args.write_symbol_map.write_text(json.dumps(symbols, indent=2, sort_keys=True)+'\n')
    capture = parse(args.capture.read_text())
    output = {'meta': capture['meta'], 'image_sha256': symbols['image_sha256'],
        'capture_sha256': hashlib.sha256(args.capture.read_bytes()).hexdigest(),
        'apis': counts_by_api(capture, symbols),
        'limitations': ['Begun instruction observations include a faulting instruction; not architectural retirement.',
            'REP iterations are separate and unknown when absent. Instruction counts are not cycles or CPU time.',
            'Instrumentation can change deadline and queue outcomes. Reclassify each capture independently.',
            'Symbol attribution is the linked enclosing function, without source-inline attribution.']}
    encoded = json.dumps(output, indent=2, sort_keys=True)+'\n'
    if args.output:
        args.output.write_text(encoded)
    else:
        print(encoded, end='')


if __name__ == '__main__':
    main()
