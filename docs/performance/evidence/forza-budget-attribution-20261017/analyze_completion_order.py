# SPDX-License-Identifier: MIT
# Independent public-event scalar analysis; no game/kernel implementation.
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import analyze


def timing(rows):
    return {'calls':len(rows),'api_us':analyze.distribution([(r['returned']-r['begin'])/1000 for r in rows]),
            'return_statuses':dict(Counter(r['result']for r in rows))}


def classify(r):
    return 'before_return'if r['done']<r['returned']else'after_return'if r['done']>r['returned']else'same_timestamp'


def validate(rows):
    required=set('iosb begin thread bytes offset caller done status info complete_count returned result dispatch callback error callback_bytes'.split())
    for r in rows:
        if set(r)!=required:raise ValueError('Unexpected or missing joined scalar fields')
        if r['caller']!='0026741a':raise ValueError('Unexpected native return callsite')
        if not (r['begin']<=r['returned']<=r['callback'] and r['begin']<=r['done']<=r['dispatch']<=r['callback']):
            raise ValueError('Invalid joined event order')
        if r['complete_count']!=1 or r['info']!=r['bytes']or r['callback_bytes']!=r['bytes']:
            raise ValueError('Incomplete/ambiguous request join')
        if r['status']!='00000000'or r['error']!='00000000':raise ValueError('Completion failure requires separate analysis')


def run(records,receipts):
    records,receipts=Path(records),Path(receipts)
    rows=json.loads(records.read_text())
    start,end=analyze.replay_bounds(receipts.read_text())
    selected=[r for r in rows if start<=r['begin']and r['returned']<=end]
    validate(selected)
    if not selected:raise ValueError('No phase-qualified joined reads')
    groups={name:[r for r in selected if classify(r)==name]for name in ['before_return','after_return','same_timestamp']}
    return {'scope':'Joined world-callback reads whose native entry and return both lie inside saved-scene receipt bounds. This is an observed joined-event cohort, not proof of exhaustive capture.',
            'host_start_ns':start,'host_end_ns':end,'all_joined_rows':len(rows),'excluded_rows':len(rows)-len(selected),
            'followthrough_after_phase':sum(r['callback']>end for r in selected),
            'selected':timing(selected),'completion_entry_order':{k:timing(v)for k,v in groups.items()},
            'pending_after_return_size_controls':{size:timing([r for r in groups['after_return']if r['bytes']==size and r['result']=='00000103'])for size in sorted(set(r['bytes']for r in groups['after_return']))},
            'interpretation':['The scalar field done is the observed parent IoCompleteRequest boundary, not proof that all completion work or IOSB publication has finished.',
                'STATUS_PENDING does not establish that parent completion or IOSB publication occurs after API return.',
                'Callbacks are joined by IOSB identity and byte count. Original producer selected callback context 0x001103e0. Raw generic event logs can contain title bytes and are not archived here.',
                'Different restored scenes and instrumented/event-limited populations prevent an uninstrumented or workload-identical performance claim.'],
            'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in [records,receipts]}}


def main():
    p=argparse.ArgumentParser();p.add_argument('records');p.add_argument('receipts');p.add_argument('--output');a=p.parse_args()
    result=json.dumps(run(a.records,a.receipts),indent=2,sort_keys=True)+'\n'
    if a.output:Path(a.output).write_text(result)
    else:print(result,end='')


if __name__=='__main__':main()
