# SPDX-License-Identifier: MIT
"""Join independently validated prefix counts to identity and state cohorts."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import sys
from analyze_prefix import parse, counts_by_api


def classify(seq, begin, ready, bind, start, returned):
    if not begin < ready < bind < returned or start <= bind or not begin <= seq < returned:
        raise ValueError('Invalid phase boundaries or row outside active call')
    if seq < ready:
        return 'entry_to_ready'
    if seq < bind:
        return 'ready_to_bind'
    if start >= returned:
        return 'bind_to_return'
    return 'bind_to_start' if seq < start else 'start_to_return'


def summary(values):
    values = list(values)
    return {'n': len(values), 'sum': sum(values),
            'median': statistics.median(values) if values else None,
            'min': min(values) if values else None, 'max': max(values) if values else None}


def join(capture, symbols, events, timelines, controlled):
    counts = counts_by_api(capture, symbols)
    by_event = {event['seq']: event for event in events}
    begins = {e['api']: e for e in events if e['kind'] == 1}
    returns = {e['api']: e for e in events if e['kind'] == 2}
    # Validate the full capture before receipt filtering: an unknown API must
    # never masquerade as a legitimate call outside the selected interval.
    for observation in capture['rows'] + capture.get('excluded', []) + capture['translations']:
        api, seq = observation['api'], observation['identity_seq']
        if seq not in by_event:
            raise ValueError('Prefix refers to absent identity event')
        if (api not in begins or api not in returns or
                not begins[api]['seq'] <= seq < returns[api]['seq']):
            raise ValueError('Prefix reference outside a known full-capture API')
    starts = {r['api']: r for r in timelines['reads']}
    output = []
    for row in controlled['reads']:
        api = row['api']
        if api not in counts:
            raise ValueError('Selected identity call lacks prefix observations')
        begin = begins[api]
        ready = [e['seq'] for e in events if e['kind'] == 12 and e['api'] == api and e['iosb'] == begin['iosb']]
        life = starts[api]['lifecycle']
        if len(ready) != 1 or len(life) != 1 or len(life[0]['starts']) != 1:
            raise ValueError('Expected one selected mapping/binding/drive start')
        bind = life[0]['bind']['seq']
        start = life[0]['starts'][0]['seq']
        returned = returns[api]['seq']
        data = counts[api]
        phases = defaultdict(Counter)
        for seq, names in data['phases_by_identity_seq'].items():
            if seq not in by_event:
                raise ValueError('Prefix refers to absent identity event')
            phase = classify(seq, begin['seq'], ready[0], bind, start, returned)
            phases[phase].update(names)
        totals = {name: sum(functions.values()) for name, functions in phases.items()}
        if sum(totals.values()) != data['begun']:
            raise ValueError('Phase totals lost observations')
        translations = [tr for tr in capture['translations'] if tr['api'] == api]
        for tr in translations:
            if tr['identity_seq'] not in by_event:
                raise ValueError('Translation refers to absent identity event')
            classify(tr['identity_seq'], begin['seq'], ready[0], bind, start, returned)
        output.append({**row, 'begun': data['begun'],
            'excluded_begun': data.get('excluded_begun', 0),
            'prebind_begun': totals.get('entry_to_ready', 0) + totals.get('ready_to_bind', 0),
            'phase_begun': totals, 'phase_symbols': dict(phases),
            'symbols': data['symbols'], 'unknown_pcs': data['unknown_pcs'],
            'rep_iterations_known': data['rep_iterations_known'],
            'rows_with_unknown_rep': data['rows_with_unknown_rep'],
            'translations_during_api': len(translations)})
    selected = {row['api'] for row in output}
    excluded = sorted(set(counts) - selected)
    direct = 'no_queue_start_before_return'
    previous = 'before_current_entry'
    predicates = {
        'long_gap_direct': lambda r: r['partition'] == direct and r['previous_completion'] == previous and r['intercall_gap_us'] is not None and r['intercall_gap_us'] >= 10000,
        'nearby_direct_already_complete': lambda r: r['partition'] == direct and r['previous_completion'] == previous and r['intercall_gap_us'] is not None and 100 <= r['intercall_gap_us'] < 1000,
        'nearby_queued_later': lambda r: r['partition'] == 'queued_start_after_return' and r['intercall_gap_us'] is not None and 0 <= r['intercall_gap_us'] < 1000,
        'completion_crossing_direct': lambda r: r['partition'] == direct and r['previous_completion'] == 'during_current_before_bind' and r['intercall_gap_us'] is not None and r['intercall_gap_us'] < 100,
    }
    cohorts = {}
    for name, predicate in predicates.items():
        rows = [r for r in output if r['bytes'] == 512 and r['extent_hit'] and predicate(r)]
        functions = sorted({symbol for r in rows for phase in ('entry_to_ready', 'ready_to_bind')
                            for symbol in r['phase_symbols'].get(phase, {})})
        cohorts[name] = {'apis': [r['api'] for r in rows], 'calls': len(rows),
            'prebind_begun': summary(r['prebind_begun'] for r in rows),
            'entry_to_bind_us': summary(r['entry_to_bind_us'] for r in rows),
            'translations_during_api': summary(r['translations_during_api'] for r in rows),
            'prebind_symbols': {symbol: summary(sum(r['phase_symbols'].get(phase, {}).get(symbol, 0)
                 for phase in ('entry_to_ready', 'ready_to_bind')) for r in rows) for symbol in functions}}
    return {'selected_reads': len(output), 'excluded_prefix_apis_outside_selected_identity_cohort': excluded,
            'cohorts_512_extent_hits': cohorts, 'reads': output,
            'limits': ['Same capture only; observation changes timing and can change queue outcomes.',
                'Phase counts describe execution during the selected call, including work on other requests; they do not establish ownership of that work.',
                'Begun instructions are not retired instructions, CPU cycles or elapsed CPU time.',
                'Same-PC translation instances need not be invalidations; flags and translation context may differ.',
                'Static symbol PCs do not independently prove runtime byte identity.',
                'Baseline capture predates selected active-slot and bookkeeping reductions; do not propose those again.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prefix', type=Path, required=True)
    p.add_argument('--identity', type=Path, required=True)
    p.add_argument('--receipts', type=Path, required=True)
    p.add_argument('--identity-tools', type=Path, required=True)
    p.add_argument('--symbol-map', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    sys.path.insert(0, str(args.identity_tools.resolve()))
    import analyze_identity as identity
    import analyze_timeline as timeline
    import analyze_prebind as prebind
    meta, events = identity.parse(args.identity.read_text())
    if meta['open_api'] or meta['map_open']:
        raise ValueError('Identity capture has unfinished calls')
    start, end = identity.bounds(args.receipts.read_text())
    begin_times = {e['api']: e['host_ns'] for e in events if e['kind'] == 1}
    return_times = {e['api']: e['host_ns'] for e in events if e['kind'] == 2}
    for api, begin_time in begin_times.items():
        return_time = return_times[api]
        if (begin_time <= end and return_time >= start and
                not (start <= begin_time <= return_time <= end)):
            raise ValueError('Receipt boundary cuts a selected API interval')
    capture = parse(args.prefix.read_text())
    if capture['limits'] is not None:
        admitted = [e for e in events if e['kind'] == 1]
        if (len(admitted) != capture['limits']['admitted'] or
                any(e['value0'] != capture['limits']['handle'] for e in admitted)):
            raise ValueError('Identity admission differs from prefix limits')
    result = join(capture, json.loads(args.symbol_map.read_text()), events,
                  timeline.timeline(events, start, end), prebind.analyze(events, start, end))
    result['hashes'] = {key: hashlib.sha256(getattr(args, key).read_bytes()).hexdigest()
                        for key in ('prefix', 'identity', 'receipts', 'symbol_map')}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    main()
