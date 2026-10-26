#!/usr/bin/env python3
"""Read-only follow-up audit: NS2 flow 125 -> 143 in the 156-175 s window.

Uses the fast-seek helpers from the user's existing preventive_158/compare_route_158.py.
Does NOT modify simulations, models, packet traces, or routing decisions.
"""
from collections import Counter, defaultdict
from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'preventive_158'))
from compare_route_158 import skip_to, time_of, node_address

START, STOP = 156.0, 175.0
OUT = ROOT / 'results' / 'preventive_158'
TRACES = {
    'baseline': ROOT / 'results' / 'network250.tr',
    'node158_off_at_155': OUT / 'network250.tr',
}


def inspect(path):
    event_uids = defaultdict(set)
    mac_source_hops = defaultdict(set)
    router_nodes = defaultdict(set)
    examples = []
    with path.open('rb') as file:
        skip_to(file, START)
        for raw in file:
            t = time_of(raw)
            if t is None:
                continue
            if t >= STOP:
                break
            if t < START:
                continue
            parts = raw.split()
            if not parts or parts[0] not in (b's', b'r', b'f', b'd', b'D'):
                continue
            attrs = {parts[i]: parts[i + 1]
                     for i in range(1, len(parts) - 1)
                     if parts[i].startswith(b'-')}
            if attrs.get(b'-It', b'').lower() != b'cbr':
                continue
            if node_address(attrs.get(b'-Is')) != 125 or node_address(attrs.get(b'-Id')) != 143:
                continue
            try:
                uid = int(attrs[b'-Ii'])
                node = int(attrs[b'-Ni'])
            except (KeyError, ValueError):
                continue
            layer = attrs.get(b'-Nl', b'').decode('utf-8', errors='replace')
            event = parts[0].decode('ascii')
            event_uids[(layer, event, node)].add(uid)
            if layer == 'RTR' and event == 'f':
                router_nodes[node].add(uid)
            if layer == 'MAC' and event == 'r' and node == 143:
                hop = node_address(attrs.get(b'-Hs'))
                mac_source_hops[hop].add(uid)
                if len(examples) < 5:
                    examples.append((uid, hop, attrs.get(b'-Hd', b'').decode(errors='replace')))
    return event_uids, mac_source_hops, router_nodes, examples


def show():
    required = [ROOT / 'results' / 'positions250.csv', *TRACES.values()]
    for p in required:
        if not p.is_file():
            raise SystemExit(f'Missing: {p}')
    with (ROOT / 'results' / 'positions250.csv').open(newline='') as f:
        positions = {int(r['node_id']): r for r in csv.DictReader(f)}
    if 125 in positions and 143 in positions:
        from math import hypot
        a, b = positions[125], positions[143]
        distance = hypot(float(a['x'])-float(b['x']), float(a['y'])-float(b['y']))
        print(f'Node 125 and Node 143 are {distance:.2f} m apart (geometric distance only).')
    print('Audit interval: 156 <= t < 175 simulated seconds.')
    rows = []
    for name, path in TRACES.items():
        events, mac_hops, router_nodes, examples = inspect(path)
        counts = {
            'agt_sent_125': len(events.get(('AGT','s',125), set())),
            'agt_received_143': len(events.get(('AGT','r',143), set())),
            'rtr_sent_125': len(events.get(('RTR','s',125), set())),
            'rtr_received_143': len(events.get(('RTR','r',143), set())),
            'mac_received_143': len(events.get(('MAC','r',143), set())),
            'mac_rx_at_143_hop_125': len(mac_hops.get(125, set())),
            'rtr_forwarding_nodes': len(router_nodes),
        }
        print(f'\nSCENARIO: {name}')
        for key, count in counts.items():
            print(f'  {key}: {count}')
        print('  Intermediate RTR CBR forwarders:',
              ', '.join(f'{n}({len(pkts)})' for n, pkts in sorted(router_nodes.items())) or 'none detected')
        print('  MAC reception at node 143 by -Hs previous-hop value:',
              ', '.join(f'{hop}: {len(uids)}' for hop, uids in sorted(mac_hops.items(), key=lambda v: (v[0] is None, str(v[0])))) or 'none detected')
        if examples:
            print('  Sample destination MAC receptions (packet ID, -Hs, -Hd):', examples)
        rows.extend({'scenario': name, 'metric': metric, 'distinct_packet_ids': number}
                    for metric, number in counts.items())
    destination = OUT / 'route_evidence_125_143.csv'
    with destination.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['scenario', 'metric', 'distinct_packet_ids'])
        writer.writeheader()
        writer.writerows(rows)
    print('\nSaved:', destination)
    print('Interpretation: Zero RTR f events does NOT by itself prove the complete hop sequence.')
    print('Check destination MAC -Hs values and AGT receipts before describing a direct path.')


if __name__ == '__main__':
    show()
