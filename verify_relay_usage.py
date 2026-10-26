#!/usr/bin/env python3
"""Summarise CBR network-routing activity for selected NS-2 nodes.

Inputs: results/network250.tr from the existing 250-node NS-2 project.
Outputs: console table and results/relay_usage_140_150.csv.
Does not modify NS-2 simulation or routing.
"""
import csv
from collections import Counter
from pathlib import Path

TRACE = Path('results/network250.tr')
OUTPUT = Path('results/relay_usage_140_150.csv')
NODES = (119, 136, 103, 137)
START = 140.0
STOP = 150.0

if not TRACE.is_file():
    raise SystemExit(f'Missing {TRACE}. Run this script from your AI_NS2_250_Node_Project folder.')

forwarded = Counter()
received = Counter()
sent = Counter()
matched = 0
routing_lines = 0

with TRACE.open('r', encoding='utf-8', errors='replace') as handle:
    for line in handle:
        parts = line.split()
        if not parts or parts[0] not in ('s', 'r', 'f'):
            continue
        # NS-2 tagged wireless traces include fields such as -t, -Ni, -Nl, -It.
        attributes = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1)
                      if parts[i].startswith('-') and parts[i] in ('-t', '-Ni', '-Nl', '-It')}
        if attributes.get('-Nl', '').upper() != 'RTR':
            continue
        routing_lines += 1
        if attributes.get('-It', '').lower() != 'cbr':
            continue
        try:
            when = float(attributes['-t'])
            node = int(attributes['-Ni'].strip('_'))
        except (ValueError, KeyError):
            continue
        if not START <= when < STOP:
            continue
        matched += 1
        event = parts[0]
        if event == 'f':
            forwarded[node] += 1
        elif event == 'r':
            received[node] += 1
        elif event == 's':
            sent[node] += 1

OUTPUT.parent.mkdir(exist_ok=True, parents=True)
with OUTPUT.open('w', newline='', encoding='utf-8') as handle:
    writer = csv.writer(handle)
    writer.writerow(['node_id', 'role', 'rtr_received', 'rtr_forwarded', 'rtr_sent'])
    for node in NODES:
        writer.writerow([node, 'HIGH RISK' if node in (119, 136) else 'ALTERNATIVE',
                         received[node], forwarded[node], sent[node]])

print('\nROUTING ACTIVITY: 140 TO 150 SECONDS')
print('Node | Role        | RTR received | RTR forwarded | RTR sent')
for node in NODES:
    role = 'HIGH RISK' if node in (119, 136) else 'ALTERNATIVE'
    print(f'{node:4} | {role:11} | {received[node]:12} | {forwarded[node]:13} | {sent[node]:8}')
print(f'\nMatching CBR routing events in window: {matched}')
print(f'Saved table: {OUTPUT}')
if not routing_lines:
    print('WARNING: No tagged RTR lines found. Your NS-2 trace may use a different format.')
elif not matched:
    print('NOTE: No CBR routing events matched this time window. Zero counts do not establish that a node cannot relay.')
print('Note: This measures logged activity; it does not demonstrate actual rerouting.')
