#!/usr/bin/env python3
"""Read-only audit for cohort-aligned packet delivery of NS2 CBR flow 125 -> 143.

Reads the 156 <= t < 180 portion of two existing 200-second traces.
Counts AGT sends in [156,175), AGT receptions in [156,175), and
cohort-matched AGT receptions through 175 and through 180.
Does NOT edit traces, simulations, models or previous result files.
"""
from pathlib import Path
import csv
import sys

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT / 'preventive_158'))
from compare_route_158 import skip_to, time_of, node_address

START = 156.0
END = 175.0
GRACE_END = 180.0
TRACES = {
    'baseline': PROJECT / 'results' / 'network250.tr',
    'node158_off_at_155': PROJECT / 'results' / 'preventive_158' / 'network250.tr',
}
OUTPUT = PROJECT / 'results' / 'preventive_158' / 'reconciled_delivery_125_143.csv'


def process_trace(filename):
    sends = {}
    receives = {}
    raw_arrivals = set()
    lines = 0
    with filename.open('rb') as f:
        skip_to(f, START)
        for raw in f:
            t = time_of(raw)
            if t is None or t < START:
                continue
            if t >= GRACE_END:
                break
            lines += 1
            if raw[:2] not in (b's ', b'r '):
                continue
            parts = raw.split()
            attrs = {parts[i]: parts[i + 1]
                     for i in range(1, len(parts)-1)
                     if parts[i].startswith(b'-')}
            if attrs.get(b'-Nl') != b'AGT' or attrs.get(b'-It', b'').lower() != b'cbr':
                continue
            if node_address(attrs.get(b'-Is')) != 125 or node_address(attrs.get(b'-Id')) != 143:
                continue
            try:
                node = int(attrs[b'-Ni'])
                uid = int(attrs[b'-Ii'])
            except (KeyError, ValueError):
                continue
            if raw.startswith(b's ') and node == 125 and START <= t < END:
                sends.setdefault(uid, t)
            if raw.startswith(b'r ') and node == 143:
                receives.setdefault(uid, t)
                if START <= t < END:
                    raw_arrivals.add(uid)
    matches_by_end = {uid: receives[uid] - sent for uid, sent in sends.items()
                      if uid in receives and sent <= receives[uid] < END}
    matches_by_grace = {uid: receives[uid] - sent for uid, sent in sends.items()
                        if uid in receives and sent <= receives[uid] < GRACE_END}
    delayed = set(matches_by_grace) - set(matches_by_end)
    other_cohort = raw_arrivals - set(sends)
    return {
        'sent_in_window': len(sends),
        'raw_receipts_in_window': len(raw_arrivals),
        'raw_receipts_not_in_send_cohort': len(other_cohort),
        'matched_delivered_by_175': len(matches_by_end),
        'matched_delivered_by_180': len(matches_by_grace),
        'matched_delivered_175_to_180': len(delayed),
        'pdr_by_175_pct': round(100*len(matches_by_end)/len(sends),2) if sends else 0,
        'pdr_by_180_pct': round(100*len(matches_by_grace)/len(sends),2) if sends else 0,
        'mean_delay_by_180_ms': round(1000*sum(matches_by_grace.values())/len(matches_by_grace),3) if matches_by_grace else 0,
        'trace_lines_examined': lines,
    }


def main():
    for name, path in TRACES.items():
        if not path.is_file():
            sys.exit(f'MISSING TRACE for {name}: {path}')
    rows=[]
    print('Packet-delivery reconciliation for source 125 -> destination 143')
    print('Send cohort: 156 <= send time < 175 s; late-arrival allowance: before 180 s')
    for name, path in TRACES.items():
        print(f'\nReading {name} ...', flush=True)
        result = process_trace(path)
        result={'scenario':name, **result}
        rows.append(result)
        for key, value in result.items():
            if key != 'scenario':
                print(f'  {key}: {value}')
    OUTPUT.parent.mkdir(exist_ok=True,parents=True)
    with OUTPUT.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys())
        w.writeheader();w.writerows(rows)
    print(f'\nSaved reconciled counts to {OUTPUT}')
    print('Different receipt counts use different packet cohorts or arrival cutoffs.')
    print('This script does not reconstruct packet hops; MAC tracing was disabled in this experiment.')

if __name__ == '__main__':
    main()
