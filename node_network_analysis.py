"""Parse NS-2 new-format wireless AGT CBR events to calculate true app-layer PDR/delay."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results'


def record(line):
    s = line.strip().split()
    if not s or s[0] not in ('s', 'r', 'D', 'd') or '-Nl' not in s:
        return None
    try:
        attrs = {s[i]: s[i+1] for i in range(1, len(s)-1) if s[i].startswith('-')}
        if attrs.get('-Nl') != 'AGT' or attrs.get('-It', '').lower() != 'cbr':
            return None
        return (s[0], float(attrs['-t']), int(attrs['-Ni']), int(attrs['-Ii']))
    except (ValueError, KeyError):
        return None


def main():
    trace = OUT / 'network250.tr'
    if not trace.exists():
        raise SystemExit('Missing network250.tr — run NS2 first.')
    sends, receipts = {}, {}
    for line in trace.open(errors='replace'):
        parsed = record(line)
        if not parsed:
            continue
        event, time, node, uid = parsed
        if event == 's':
            sends.setdefault(uid, (node, time))
        elif event == 'r':
            receipts.setdefault(uid, (node, time))
    if not sends:
        raise SystemExit('No CBR packets at AGT layer found. Inspect results/network250.tr.')
    stats = {}
    delays = []
    for uid, (src, sent_at) in sends.items():
        row = stats.setdefault(src, {'node_id':src,'packets_sent':0,'packets_received':0,'packets_lost':0,'mean_delay_s':0.0})
        row['packets_sent'] += 1
        if uid in receipts and receipts[uid][1] >= sent_at:
            row['packets_received'] += 1
            delays.append((src, receipts[uid][1] - sent_at))
        else:
            row['packets_lost'] += 1
    df = pd.DataFrame(list(stats.values())).sort_values('node_id')
    delaydf = pd.DataFrame(delays, columns=['node_id','delay_s'])
    if not delaydf.empty:
        means = delaydf.groupby('node_id')['delay_s'].mean()
        df['mean_delay_s'] = df['node_id'].map(means).fillna(0)
    df['packet_loss_pct'] = df['packets_lost'] / df['packets_sent'] * 100
    df.to_csv(OUT / 'node_network_analysis.csv', index=False)
    sent = len(sends)
    recv = sum(uid in receipts and receipts[uid][1] >= item[1] for uid, item in sends.items())
    summary = pd.DataFrame([{'packets_sent':sent,'packets_received':recv,'packets_lost_or_not_delivered':sent-recv,
                             'packet_delivery_pct':100*recv/sent,
                             'mean_delay_s': sum(v for _,v in delays)/len(delays) if delays else 0}])
    summary.to_csv(OUT / 'network_summary.csv', index=False)
    print('Packet summary (AGT CBR unique IDs):', summary.to_dict('records')[0])


if __name__ == '__main__':
    main()
