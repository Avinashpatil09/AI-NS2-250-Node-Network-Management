#!/usr/bin/env python3
"""Audit CBR endpoints and source performance for the reconstructed 250-node NS2 experiment.

Run from the AI_NS2_250_Node_Project directory after the completed 200-second analysis:
    python3 audit_active_flows.py

Inputs: results/positions250.csv and results/node_network_analysis.csv.
Output: results/traffic_flow_audit.csv.
No large trace scan; no NS2 rerun or routing changes.
"""
from pathlib import Path
import math
import pandas as pd

root = Path(__file__).resolve().parent
out = root / "results"
pos = pd.read_csv(out / "positions250.csv").set_index("node_id")
performance = pd.read_csv(out / "node_network_analysis.csv").set_index("node_id")
nn = len(pos)
cols = math.ceil(math.sqrt(nn))
flows = math.ceil(nn / 5)
rows = []
for f in range(flows):
    src = (f * 5) % nn
    dst = (src + cols + 2) % nn
    if dst == src:
        dst = (src + 1) % nn
    a, b = pos.loc[src], pos.loc[dst]
    dist = math.hypot(float(a['x']) - float(b['x']), float(a['y']) - float(b['y']))
    stats = performance.loc[src] if src in performance.index else None
    sent = int(stats['packets_sent']) if stats is not None else 0
    received = int(stats['packets_received']) if stats is not None else 0
    rows.append({
        'flow_id': f,
        'source_node': src,
        'destination_node': dst,
        'distance_m': round(dist, 1),
        'packets_sent': sent,
        'packets_delivered': received,
        'delivery_pct': round(received / sent * 100, 2) if sent else 0,
    })
df = pd.DataFrame(rows)
path = out / 'traffic_flow_audit.csv'
df.to_csv(path, index=False)
print(f'Configured flows: {len(df)}; sources with packets: {(df.packets_sent > 0).sum()}')
print('\nFIRST TEN TRAFFIC FLOWS:')
print(df.head(10).to_string(index=False))
print('\nFIVE LONGEST CONFIGURED FLOWS:')
print(df.sort_values('distance_m', ascending=False).head(5).to_string(index=False))
print('\nPROPOSED RISK/ALTERNATIVE NODES:')
for node in (119, 136, 103, 137):
    print(f'Node {node}: source={node in set(df.source_node)}, destination={node in set(df.destination_node)}')
print('\nThis audits configured endpoints and AGT delivery only, NOT AODV forwarding paths.')
print(f'Saved {path}')
