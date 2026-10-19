# SPDX-License-Identifier: MIT
"""Separate exact instruction-start vectors and REP body observations."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import analyze_prefix as prefix
import join_prefix
import qualify as qualification

PREBIND = ('entry_to_ready', 'ready_to_bind')


def vector_summary(reads, apis, interrupt_symbols):
    selected = [row for row in reads if row['api'] in apis]
    if {row['api'] for row in selected} != set(apis):
        raise ValueError('Cohort refers to missing call')
    groups = defaultdict(list)
    for row in selected:
        vector = tuple((phase, symbol, count) for phase in PREBIND
                       for symbol, count in sorted(row['phase_symbols'].get(phase, {}).items()) if count)
        if 'prebind_begun' in row and sum(item[2] for item in vector) != row['prebind_begun']:
            raise ValueError('Prebind vector does not conserve joined count')
        groups[vector].append(row['api'])
    vectors = [{'apis': sorted(ids), 'calls': len(ids), 'begun': sum(item[2] for item in key),
                'vector': [{'phase': p, 'linked_symbol': s, 'begun': n} for p,s,n in key]}
               for key,ids in sorted(groups.items(), key=lambda item:(sum(x[2] for x in item[0]),item[0]))]
    minimum = min((row['begun'] for row in vectors), default=None)
    floors = [row for row in vectors if row['begun'] == minimum]
    unique = len(floors) == 1
    deltas = []
    if unique:
        base = {(item['phase'],item['linked_symbol']):item['begun'] for item in floors[0]['vector']}
        for row in selected:
            current = {(p,s):n for p in PREBIND for s,n in row['phase_symbols'].get(p,{}).items()}
            delta = {key:current.get(key,0)-base.get(key,0) for key in sorted(set(base)|set(current))}
            phases = defaultdict(dict)
            for (phase,symbol), count in delta.items():
                if count: phases[phase][symbol] = count
            change = sum(current.values()) - minimum
            if sum(delta.values()) != change:
                raise ValueError('Vector subtraction lost instruction starts')
            deltas.append({'api':row['api'],'instruction_delta':change,
                           'componentwise_additive':all(n>=0 for n in delta.values()),
                           'delta_by_phase':dict(phases),
                           'interrupt_entry_delta':sum(n for (_,s),n in delta.items() if s in interrupt_symbols)})
    return {'calls':len(selected), 'minimum_begun':minimum, 'unique_floor':unique,
            'floor_apis':sorted(api for row in floors for api in row['apis']),
            'floor_calls':sum(row['calls'] for row in floors), 'minimum_vectors':floors,
            'exact_vectors':vectors,'deltas':deltas,
            'interrupt_entry_symbols':sorted(interrupt_symbols)}


def decode_rep_scalar(text):
    """Return mnemonic/width only; never publish operands or instruction bytes."""
    match = re.search(r'\b(rep(?:z|nz|e|ne)?)\s+(movs|stos|lods|cmps|scas|ins|outs)([bwldq]?)(?=\s|$)',text)
    if not match:
        return None
    width = {'b':1,'w':2,'l':4,'d':4,'q':8}.get(match[3])
    if width is None and match[2] in ('stos','lods','scas'):
        register = re.search(r'%(al|ax|eax|rax)\b',text[match.end():])
        if register: width = {'al':1,'ax':2,'eax':4,'rax':8}[register[1]]
    return {'mnemonic':match[1]+' '+match[2]+match[3], 'element_width_bytes':width}


def extract_rep_metadata(image, symbols, pcs):
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    if digest != symbols['image_sha256']:
        raise ValueError('Owned image differs from symbol map image')
    listing = subprocess.check_output(['objdump','-d',str(image)],text=True)
    instructions = {}
    for line in listing.splitlines():
        match = re.match(r'^\s*([0-9a-fA-F]+):\s+((?:[0-9a-fA-F]{2}\s+)+)\s*(\S.*)?$',line)
        if match and match[3]:
            pc = f'{int(match[1],16):08x}'
            if pc in pcs:
                if pc in instructions: raise ValueError('Ambiguous owned instruction PC')
                scalar = decode_rep_scalar(match[3])
                if scalar is None: raise ValueError('Recorder REP PC is not a decoded REP string instruction')
                instructions[pc] = {**scalar,'linked_symbol':symbols['instruction_owners'].get(pc)}
    if set(instructions) != set(pcs):
        raise ValueError('Owned image lacks a requested decoded REP PC')
    return {'image_sha256':digest,'instructions':instructions}


def rep_summary(capture, symbols, phases, metadata):
    if metadata is not None and metadata['image_sha256'] != symbols['image_sha256']:
        raise ValueError('REP metadata image differs from symbol map')
    records = []
    known = unknown = 0
    unselected_known = unselected_unknown = 0
    unambiguous = ambiguous = excluded = 0
    for row in capture['rows'] + capture.get('excluded',[]):
        key = (row['api'],row['identity_seq'])
        if key not in phases:
            unselected_known += row.get('rep_iterations',0)
            unselected_unknown += 'rep_iterations' not in row
            continue
        phase = phases[key]
        iterations = row.get('rep_iterations',0)
        known += iterations
        unknown += 'rep_iterations' not in row
        if 'tb' not in row:
            pcs = []
            scope, symbol, starts = 'excluded',None,None
            excluded += iterations
        else:
            desc = capture['descriptors'][row['tb']]
            pcs = [f'{desc["instructions"][n]["pc"]:08x}' for n in range(row['first'],row['last']+1)
                   if desc['instructions'][n]['rep']]
            if not pcs:
                if iterations: raise ValueError('REP iterations without marked instruction')
                continue
            starts = row['executions'] * len(pcs)
            symbol = symbols['instruction_owners'].get(pcs[0]) if len(pcs)==1 else None
            scope = 'owned' if len(pcs)==1 and symbol is not None else 'unmapped_owned' if len(pcs)==1 else 'ambiguous_owned'
            if len(pcs)==1: unambiguous += iterations
            else: ambiguous += iterations
        pc = pcs[0] if len(pcs)==1 else None
        scalar = metadata['instructions'].get(pc,{}) if metadata is not None and pc is not None else {}
        width = scalar.get('element_width_bytes')
        records.append({'api':row['api'],'identity_seq':row['identity_seq'],'phase':phase,
                        'scope':scope,'linked_symbol':symbol,'pc':pc,'candidate_pcs':pcs,
                        'instruction_starts':starts,'iterations':iterations,
                        'unknown_rows':int('rep_iterations' not in row),
                        'mnemonic':scalar.get('mnemonic'),'element_width_bytes':width,
                        'body_byte_operations':iterations*width if width is not None and 'rep_iterations' in row else None})
    if sum(row['iterations'] for row in records) != known or unambiguous+ambiguous+excluded != known:
        raise ValueError('REP attribution lost iteration counts')
    functions = defaultdict(lambda: {'iterations':0,'unknown_rows':0,'body_byte_operations':0,'bytes_known':True})
    for row in records:
        key = (row['api'],row['phase'],row['scope'],row['linked_symbol'])
        group=functions[key]; group['iterations']+=row['iterations'];group['unknown_rows']+=row['unknown_rows']
        if row['body_byte_operations'] is None: group['bytes_known']=False
        else: group['body_byte_operations']+=row['body_byte_operations']
    grouped=[]
    for (api,phase,scope,symbol),group in sorted(functions.items(),key=lambda item:str(item[0])):
        grouped.append({'api':api,'phase':phase,'scope':scope,'linked_symbol':symbol,
                        'iterations':group['iterations'],'unknown_rows':group['unknown_rows'],
                        'body_byte_operations':group['body_byte_operations'] if group['bytes_known'] else None})
    return {'known_iterations':known,'unknown_iteration_rows':unknown,
            'unselected_known_iterations':unselected_known,'unselected_unknown_rows':unselected_unknown,
            'owned_unambiguous_iterations':unambiguous,'owned_ambiguous_iterations':ambiguous,
            'excluded_iterations':excluded,'records':records,'per_call_phase_function':grouped}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('prefix','identity','receipts','identity-tools','symbol-map','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--owned-image',type=Path)
    parser.add_argument('--interrupt-entry-symbol',action='append',default=[])
    args=parser.parse_args()
    sys.path.insert(0,str(args.identity_tools.resolve()))
    import analyze_identity as identity
    import analyze_timeline as timeline
    import analyze_prebind as prebind
    inputs={name:getattr(args,name).read_bytes()for name in ('prefix','identity','receipts','symbol_map')}
    qualified=qualification.qualify(inputs['prefix'].decode(),inputs['identity'].decode(),inputs['receipts'].decode(),identity)
    capture=prefix.parse(inputs['prefix'].decode());symbols=json.loads(inputs['symbol_map'])
    _,events=identity.parse(inputs['identity'].decode());start,end=identity.bounds(inputs['receipts'].decode())
    events=[event for event in events if event['seq']<=qualified['selected_drain_seq']]
    trace=timeline.timeline(events,start,end)
    joined=join_prefix.join(capture,symbols,events,trace,prebind.analyze(events,start,end))
    begins={event['api']:event for event in events if event['kind']==1}
    returns={event['api']:event for event in events if event['kind']==2}
    lives={row['api']:row['lifecycle'][0] for row in trace['reads']}
    ready={event['api']:event['seq'] for event in events if event['kind']==12 and event['api']in begins and event['iosb']==begins[event['api']]['iosb']}
    phases={}
    for row in capture['rows']+capture['excluded']:
        api=row['api'];life=lives[api]
        phases[(api,row['identity_seq'])]=join_prefix.classify(row['identity_seq'],begins[api]['seq'],ready[api],life['bind']['seq'],life['starts'][0]['seq'],returns[api]['seq'])
    pcs={f'{instruction["pc"]:08x}' for desc in capture['descriptors'].values()for instruction in desc['instructions'].values()if instruction['rep']}
    metadata=extract_rep_metadata(args.owned_image,symbols,pcs)if args.owned_image else None
    cohorts={name:vector_summary(joined['reads'],set(cohort['apis']),set(args.interrupt_entry_symbol))
             for name,cohort in joined['cohorts_512_extent_hits'].items()}
    reps=rep_summary(capture,symbols,phases,metadata)
    if (sum(row['begun'] for row in joined['reads']) != qualified['instruction_starts']['total'] or
            sum(row['rep_iterations_known'] for row in joined['reads']) != reps['known_iterations'] or
            sum(row['rows_with_unknown_rep'] for row in joined['reads']) != reps['unknown_iteration_rows']):
        raise ValueError('Independent joined totals disagree with work summary')
    for cohort in cohorts.values():
        cohort['floor_rep_by_phase_function']=[row for row in reps['per_call_phase_function']if row['api']in cohort['floor_apis'] and row['phase']in PREBIND]
    result={'qualification':qualified,'cohorts':cohorts,'rep':reps,'rep_metadata':metadata,
            'hashes':{name:hashlib.sha256(data).hexdigest()for name,data in inputs.items()},
            'image_sha256':symbols['image_sha256'],
            'tool_hashes':{Path(module.__file__).name:hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                for module in (prefix,join_prefix,identity,timeline,prebind,qualification)},
            'limits':['A floor is the minimum observed exact vector, not a theoretical minimum or a performance control.',
                      'Empty nearby cohorts remain absent controls; no counterfactual speed claim.',
                      'Instruction starts, REP body iterations, and byte operations are distinct; none is CPU time or architectural retirement.',
                      'Explicit interrupt-entry labels annotate only those linked-symbol deltas, not ownership of all extra work.',
                      'Phase work can serve other requests. Static width binding does not prove runtime bytes or unique memory locations.',
                      'Excluded TB entries have no per-instruction-PC attribution; ambiguous multi-REP prefixes retain unsplit iterations.']}
    result['tool_hashes'][Path(__file__).name]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')


if __name__=='__main__': main()
