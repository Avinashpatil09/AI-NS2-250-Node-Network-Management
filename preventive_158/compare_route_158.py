#!/usr/bin/env python3
"""Compare a packet flow (125->143) from baseline and controlled intervention.
Does not infer working routes from node geometry. Reads only limited time windows
from large NS2 wireless trace files using approximate binary seek.
"""
from pathlib import Path
from collections import defaultdict
import csv, re

PROJECT = Path(__file__).resolve().parent.parent
BASE = PROJECT / 'results/network250.tr'
TRIAL = PROJECT / 'results/preventive_158/network250.tr'
OUT = PROJECT / 'results/preventive_158/comparison_125_143.csv'
RE = re.compile(rb'(?:^|\s)-t\s+([\d.]+)')
WINDOWS = [('before',140.0,150.0),('after',156.0,175.0)]

def time_of(raw):
    match = RE.search(raw)
    return float(match.group(1)) if match else None

def skip_to(stream, target):
    stream.seek(0, 2)
    low, high = 0, stream.tell()
    while high - low > 65536:
        middle=(low+high)//2
        stream.seek(middle)
        stream.readline()
        row=stream.readline()
        t=time_of(row)
        if t is None or t>=target:
            high=middle
        else:
            low=stream.tell()
    stream.seek(max(0,low-65536))
    if stream.tell():stream.readline()
    while True:
        offset=stream.tell()
        line=stream.readline()
        if not line:break
        t=time_of(line)
        if t is not None and t>=target:
            stream.seek(offset)
            break

def node_address(raw):
    try: return int(raw.split(b'.',1)[0])
    except (ValueError,TypeError):return -1

def analyze(path,label):
    if not path.exists():
        raise FileNotFoundError(f'Missing trace file: {path}')
    sends = {}       # unique CBR uid -> first app-layer send time
    receipts = {}    # CBR uid -> first app-layer arrival time
    forwards = defaultdict(set)  # node id -> set of packet IDs (focus flow)
    earliest = WINDOWS[0][1]
    latest = max(end for _,start,end in WINDOWS)+5
    with path.open('rb') as handle:
        skip_to(handle,earliest)
        for raw in handle:
            t=time_of(raw)
            if t is None: continue
            if t>=latest: break
            if raw[:1] not in (b's',b'r',b'f'): continue
            toks=raw.split()
            if not toks:continue
            vals={toks[i]:toks[i+1] for i in range(1,len(toks)-1) if toks[i].startswith(b'-')}
            if vals.get(b'-It',b'').lower()!=b'cbr':continue
            if node_address(vals.get(b'-Is'))!=125 or node_address(vals.get(b'-Id'))!=143:continue
            try:
                uid=int(vals[b'-Ii'])
                node=int(vals[b'-Ni'])
            except (KeyError,ValueError):continue
            layer=vals.get(b'-Nl',b'')
            if toks[0]==b's' and layer==b'AGT' and node==125:
                sends.setdefault(uid,t)
            elif toks[0]==b'r' and layer==b'AGT' and node==143:
                receipts.setdefault(uid,t)
            elif toks[0]==b'f' and layer==b'RTR':
                forwards[node].add((uid,t))
    rows=[]
    for name,start,end in WINDOWS:
        ids={uid:sent for uid,sent in sends.items() if start<=sent<end}
        delivered={uid:receipts[uid]-sent for uid,sent in ids.items() if uid in receipts and sent<=receipts[uid]<=end+5}
        via158={uid for uid,t in forwards[158] if start<=t<end and uid in ids}
        via159={uid for uid,t in forwards[159] if start<=t<end and uid in ids}
        n=len(ids); d=len(delivered)
        rows.append({'scenario':label,'window':name,'start_s':start,'end_s':end,
             'source':125,'destination':143,'sent':n,'delivered':d,
             'delivery_percent':round(d/n*100,2) if n else None,
             'mean_delay_ms':round(sum(delivered.values())/d*1000,3) if d else None,
             'packets_via_158':len(via158),'packets_via_159':len(via159)})
    return rows

def main():
    rows=analyze(BASE,'baseline')+analyze(TRIAL,'node158_off_at_155')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]))
        wr.writeheader();wr.writerows(rows)
    print('\nSOURCE 125 -> DESTINATION 143: REAL NS2 TRACE COMPARISON')
    print('scenario               window   sent delivered PDR%  delay_ms via158 via159')
    for r in rows:
        print(f"{r['scenario']:<22} {r['window']:<8} {r['sent']:>4} {r['delivered']:>9} "
              f"{str(r['delivery_percent']):>5} {str(r['mean_delay_ms']):>9} "
              f"{r['packets_via_158']:>6} {r['packets_via_159']:>6}")
    print(f'\nSaved comparison to {OUT}')
    if all(r['packets_via_158']==0 for r in rows if r['scenario']=='baseline' and r['window']=='after'):
        print('NOTE: The original baseline did NOT use 158 in the after-window; there is no evidence this flow needed its replacement then.')
    print('No forced selection of node 159: AODV is allowed to choose its own route.')
    print('Do not claim traffic successfully rerouted unless trace behavior supports it.')

if __name__=='__main__':main()
