from pathlib import Path
from statistics import mean
import csv

root = Path("results/robustness_phase01")

def analyze(scenario):
    folder = root / scenario
    trace = folder / "network250.tr"

    sent = {}
    received = {}

    with trace.open("rb", buffering=1024*1024) as f:
        for line in f:
            if b"-Nl AGT" not in line or b"-It cbr" not in line:
                continue

            p = line.split()
            if p[0] not in (b"s", b"r"):
                continue

            try:
                t = float(p[p.index(b"-t")+1])
                if not 156 <= t < 180:
                    continue

                src = int(float(p[p.index(b"-Is")+1]))
                dst = int(float(p[p.index(b"-Id")+1]))
                node = int(float(p[p.index(b"-Hs")+1]))
                pid = int(p[p.index(b"-Ii")+1])
            except (ValueError, IndexError):
                continue

            if (src, dst) != (125, 143):
                continue

            if p[0] == b"s" and node == 125 and t < 175:
                sent.setdefault(pid, t)

            if p[0] == b"r" and node == 143:
                received[pid] = min(received.get(pid, t), t)

    delivered = [
        pid for pid, st in sent.items()
        if pid in received and st <= received[pid] < 180
    ]

    count = len(sent)
    if count == 0:
        raise ValueError("No matching packets in " + scenario)

    pdr = 100 * len(delivered) / count

    delay = (
        mean((received[p] - sent[p]) * 1000 for p in delivered)
        if delivered else 0
    )

    energy_path = folder / "energy250.csv"
    first = {}
    last = {}
    first_time = None
    last_time = None

    with energy_path.open() as f:
        for row in csv.DictReader(f):
            t = float(row["time"])
            node = int(row["node_id"])
            energy = float(row["energy"])

            if first_time is None:
                first_time = t

            if t == first_time:
                first[node] = energy

            if last_time is None or t > last_time:
                last_time = t
                last = {}

            if t == last_time:
                last[node] = energy

    if len(first) != 250 or len(last) != 250:
        raise ValueError("Incomplete energy snapshot")

    consumed = sum(first[n] - last[n] for n in first)

    return [
        scenario,
        count,
        len(delivered),
        count - len(delivered),
        round(pdr, 2),
        round(delay, 3),
        round(consumed, 3),
        last_time
    ]

rows = [analyze("baseline"), analyze("preventive")]

headers = [
    "scenario", "sent", "received", "lost",
    "pdr_percent", "mean_delay_ms",
    "total_energy_consumed_j", "energy_snapshot_s"
]

print("\nROBUSTNESS PHASE 01 - START SHIFT +0.10s")
print(" | ".join(headers))

for row in rows:
    print(" | ".join(map(str, row)))

out = root / "performance_energy_125_143.csv"

with out.open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(headers)
    writer.writerows(rows)

print("\nSaved:", out)
