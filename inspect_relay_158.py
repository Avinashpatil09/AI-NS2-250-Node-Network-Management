#!/usr/bin/env python3
"""Inspect actual NS-2 RTR/CBR flows through relay 158 at 140-150s.

Uses seek to avoid reading an entire multi-GB wireless trace.
No NS2 re-run; no route modification. Outputs stay under results/.
"""
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRACE = ROOT / 'results/network250.tr'
OUT = ROOT / 'results'
RELAY = 158
CANDIDATE = 159
START, END, EXTRATIME = 140.0, 150.0, 1.0
TIME = re.compile(rb'(?:^|\s)-t\s+([0-9]+(?:\.[0-9]+)?)')


def get_time(line):
    m = TIME.search(line)
    return float(m.group(1)) if m else None


def seek_to_time(stream, target):
    stream.seek(0, 2)
    low, high = 0, stream.tell()
    while high - low > 65536:
        mid = (low + high) // 2
        stream.seek(mid)
        stream.readline()
        line = stream.readline()
        t = get_time(line)
        if t is None or t >= target:
            high = mid
        else:
            low = stream.tell()
    stream.seek(max(0, low - 65536))
    if stream.tell():
        stream.readline()
    while True:
        pos = stream.tell()
        line = stream.readline()
        if not line:
            return
        t = get_time(line)
        if t is not None and t >= target:
            stream.seek(pos)
            return


def fields(parts):
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1)
            if parts[i].startswith(b'-')}


def host(address):
    try:
        return int(address.split(b'.', 1)[0])
    except (ValueError, IndexError):
        return -1


def events(stream, stop):
    for raw in stream:
        t = get_time(raw)
        if t is None:
            continue
        if t >= stop:
            break
        if raw[:1] not in (b's', b'r', b'f', b'D', b'd'):
            continue
        parts = raw.split()
        if not parts:
            continue
        attr = fields(parts)
        if attr.get(b'-It', b'').lower() != b'cbr':
            continue
        try:
            uid = int(attr[b'-Ii'])
            node = int(attr[b'-Ni'])
        except (ValueError, KeyError):
            continue
        yield t, parts[0].decode(), node, uid, attr


def main():
    if not TRACE.is_file():
        raise SystemExit('Missing results/network250.tr. Do not rerun NS2 just for this check.')
    ids = {}
    candidate_fwd = 0
    with TRACE.open('rb') as f:
        seek_to_time(f, START)
        for t, ev, node, uid, att in events(f, END):
            if ev == 'f' and att.get(b'-Nl') == b'RTR':
                if node == RELAY:
                    ids[uid] = (host(att.get(b'-Is', b'')), host(att.get(b'-Id', b'')))
                if node == CANDIDATE:
                    candidate_fwd += 1

    if not ids:
        print('No RTR CBR forwarding packets found for relay 158 at 140-150 seconds.')
        print('Check the original relay selection CSV and trace timestamps.')
        return

    packet_events = defaultdict(list)
    with TRACE.open('rb') as f:
        seek_to_time(f, START)
        for t, ev, node, uid, att in events(f, END + EXTRATIME):
            if uid not in ids:
                continue
            layer = att.get(b'-Nl', b'').decode('ascii', errors='replace')
            packet_events[uid].append((t, ev, node, layer))

    flows = defaultdict(lambda: {'count': 0, 'delivered': 0})
    examples = []
    for uid, (src, dst) in ids.items():
        path = sorted(packet_events[uid])
        # Forwarding sequence by network layer (not a verified hop-by-hop route).
        forwards = [node for t, ev, node, layer in path if ev == 'f' and layer == 'RTR']
        delivered = any(ev == 'r' and layer == 'AGT' for t, ev, node, layer in path)
        flows[(src, dst)]['count'] += 1
        flows[(src, dst)]['delivered'] += int(delivered)
        examples.append({'packet_uid': uid, 'source': src, 'destination': dst,
                         'rtr_forwarding_nodes': ' -> '.join(map(str, forwards)),
                         'agt_received_by_151s': int(delivered),
                         'candidate_159_in_forwarders': int(CANDIDATE in forwards)})

    OUT.mkdir(parents=True, exist_ok=True)
    flowfile = OUT / 'relay158_flows_140_150.csv'
    with flowfile.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['source', 'destination', 'packets_forwarded_via_158', 'agt_received_by_151s'])
        for (src, dst), data in sorted(flows.items(), key=lambda x: -x[1]['count']):
            w.writerow([src, dst, data['count'], data['delivered']])
    examplefile = OUT / 'relay158_packet_examples.csv'
    with examplefile.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(examples[0]))
        w.writeheader()
        w.writerows(sorted(examples, key=lambda d: d['packet_uid']))

    print(f'Node {RELAY} actually forwarded {len(ids)} distinct CBR packet IDs during {START:g}-{END:g}s.')
    print(f'Node {CANDIDATE} forwarded {candidate_fwd} RTR CBR events in the same period.')
    print('\nACTUAL SOURCE/DESTINATION FLOWS USING NODE 158:')
    print(' source -> dest | packets via 158 | delivered by 151 s')
    for (src, dst), data in sorted(flows.items(), key=lambda x: -x[1]['count']):
        print(f' {src:4} -> {dst:<4} | {data["count"]:15} | {data["delivered"]:18}')
    print('\nEXAMPLE FORWARDING-NODE SEQUENCES (observations, not validated routes):')
    for row in sorted(examples, key=lambda x: x['packet_uid'])[:5]:
        print(f' packet {row["packet_uid"]}: {row["source"]}->{row["destination"]} | {row["rtr_forwarding_nodes"] or "none recorded"}')
    print(f'\nSaved {flowfile.name} and {examplefile.name} inside results/.')
    print('IMPORTANT: proximity of node 159 does NOT yet establish a working replacement route.')


if __name__ == '__main__':
    main()
