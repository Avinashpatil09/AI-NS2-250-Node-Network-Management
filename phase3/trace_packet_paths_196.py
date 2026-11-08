"""Inspect genuine CBR packet delivery after Node 196 shutdown."""

from pathlib import Path
from collections import defaultdict, Counter
import csv

ROOT = Path.cwd()

path_file = ROOT / "phase3/output/node196_experiment_path.txt"
output = ROOT / "phase3/output/node196_packet_paths.csv"

if output.exists():
    raise SystemExit("STOP: Output already exists")

run = Path(path_file.read_text().strip())
trace = run / "results/network250.tr"

if not trace.is_file():
    raise SystemExit("STOP: Intervention trace missing")

START = 155.1
SRC = 180
DST = 198

sent = {}
received = {}
forwarding = defaultdict(list)

print("\n===== PHASE 3: PACKET PATH ANALYSIS =====")
print("Flow: 180 -> 198")
print("Analysis starts:", START, "seconds")
print("Reading intervention trace...")

with trace.open("rb", buffering=1024 * 1024) as stream:
    for raw in stream:
        if not raw.startswith((b"s ", b"r ", b"f ")):
            continue

        if b"-It cbr" not in raw:
            continue

        parts = raw.split()

        fields = {
            parts[i]: parts[i + 1]
            for i in range(1, len(parts) - 1)
            if parts[i].startswith(b"-")
        }

        try:
            t = float(fields[b"-t"])
            uid = int(fields[b"-Ii"])
            src = int(float(fields[b"-Is"]))
            dst = int(float(fields[b"-Id"]))
            node = int(fields[b"-Ni"])
        except (KeyError, ValueError, IndexError):
            continue

        if t < START - 1e-6:
            continue

        if (src, dst) != (SRC, DST):
            continue

        layer = fields.get(b"-Nl")
        event = parts[0]

        if event == b"s" and layer == b"AGT" and node == SRC:
            sent[uid] = t

        elif event == b"r" and layer == b"AGT" and node == DST:
            received[uid] = min(
                t, received.get(uid, t)
            )

        elif event == b"f" and layer == b"RTR":
            forwarding[uid].append((t, node))

print("\n===== PACKET DELIVERY =====")

delivered = [
    uid for uid, start in sent.items()
    if uid in received and received[uid] >= start
]

print("Packets generated after shutdown:", len(sent))
print("Packets delivered:", len(delivered))

pdr = 100 * len(delivered) / len(sent) if sent else 0
print("PDR:", round(pdr, 3), "%")

print("\n===== FORWARDING SEQUENCES =====")

sequences = Counter()
records = []

for uid, start in sorted(sent.items(), key=lambda x: x[1]):
    events = sorted(forwarding.get(uid, []))

    path = []

    for _, node in events:
        if not path or path[-1] != node:
            path.append(node)

    arrived = uid in received and received[uid] >= start

    if arrived:
        sequences[tuple(path)] += 1

    records.append({
        "packet_uid": uid,
        "send_time": start,
        "delivered": int(arrived),
        "receive_time": received.get(uid, ""),
        "forwarding_sequence": ";".join(map(str, path))
    })

for sequence, count in sequences.most_common(10):
    display = " -> ".join(map(str, sequence))
    print(f"{display or '(none recorded)'} : {count} delivered packets")

print("\n===== SAMPLE DELIVERED PACKETS =====")

shown = 0

for record in records:
    if record["delivered"]:
        print(
            "Packet:", record["packet_uid"],
            "| Forwarders:",
            record["forwarding_sequence"] or "none recorded"
        )
        shown += 1

    if shown == 5:
        break

# Confirm the disabled node does not appear as a forwarder.
remaining_196_events = sum(
    node == 196
    for events in forwarding.values()
    for _, node in events
)

print("\nNode 196 forwarding events after shutdown:",
      remaining_196_events)

if remaining_196_events:
    raise SystemExit(
        "STOP: Unexpected Node 196 forwarding activity"
    )

output.parent.mkdir(parents=True, exist_ok=True)

with output.open("w", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=records[0].keys()
    )
    writer.writeheader()
    writer.writerows(records)

print("\n===== ANALYSIS COMPLETE =====")
print("Saved:", output)
print("No new NS2 simulation executed")
print("Original results unchanged")
print("PACKET-LEVEL ROUTING ANALYSIS: PASSED")
