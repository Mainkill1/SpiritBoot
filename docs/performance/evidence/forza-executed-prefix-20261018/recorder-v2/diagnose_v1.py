# SPDX-License-Identifier: MIT
"""Reproduce only structural findings from the rejected v1 capture."""
from pathlib import Path
from collections import Counter
import hashlib,json
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--prefix',type=Path,required=True);parser.add_argument('--identity',type=Path,required=True)
parser.add_argument('--output',type=Path)
args=parser.parse_args();PREFIX=args.prefix;IDENTITY=args.identity
rows=Counter();descriptors=[];begins=[];meta={}
for line in PREFIX.read_text().splitlines():
 words=line.split();d=dict(w.split('=') for w in words[1:])
 if words[0]=='prefix_meta':meta={k:int(v) for k,v in d.items()}
 elif words[0]=='prefix_row':rows[int(d['api'])]+=1
 elif words[0]=='prefix_tb':descriptors.append(d)
for line in IDENTITY.read_text().splitlines():
 words=line.split()
 if words[0]!='identity_event':continue
 d=dict(w.split('=') for w in words[1:])
 if int(d['kind'])==1:begins.append(d)
assert sum(rows.values())==meta['rows']<262144
out={'status':'REJECTED; no work attribution or firmware conclusion',
 'prefix_sha256':hashlib.sha256(PREFIX.read_bytes()).hexdigest(),
 'identity_sha256':hashlib.sha256(IDENTITY.read_bytes()).hexdigest(),
 'prefix_meta':meta,'histogram_load':meta['rows']/262144,
 'overflow_deduction':'Not histogram-full: the monotone table has free slots and v1 probes every slot. Overflow must come from descriptor and/or instruction metadata allocation, which include inactive translations.',
 'invalid_deduction':'Exact invalid reason cannot be recovered from the aggregate. Counts are validation invocations, not necessarily unique bad TBs.',
 'maximum_emitted_descriptor':max(int(d['id']) for d in descriptors),
 'emitted_instructions':sum(int(d['count']) for d in descriptors),
 'metadata_limit':'Emitted subset omits unused inactive descriptors and therefore does not reveal total allocations.',
 'handles':dict(Counter(d['value0'] for d in begins)),
 'first64_handles':dict(Counter(d['value0'] for d in begins[:64])),
 'cumulative_rows':{str(n):sum(v for k,v in rows.items() if k<=n) for n in [16,32,48,64,96,128,160,192,212]}}
if args.output: args.output.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
