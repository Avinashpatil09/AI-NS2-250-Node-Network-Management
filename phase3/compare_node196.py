"""Compare genuine NS2 baseline and Node 196 intervention."""

import csv
import hashlib
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path.cwd()

baseline_runs = list(Path("/tmp").glob(
    "ns2-phase3-live250-*/results/phase3_decision.json"
))

if not baseline_runs:
    raise SystemExit("STOP: Baseline experiment missing")

baseline = max(
    baseline_runs,
    key=lambda p: p.stat().st_mtime
).parent

path_file = ROOT / "phase3/output/node196_experiment_path.txt"

if not path_file.is_file():
    raise SystemExit("STOP: Intervention path missing")

intervention = (
    Path(path_file.read_text().strip()) / "results"
)

output = ROOT / "phase3/output/node196_comparison.csv"

if output.exists():
    raise SystemExit("STOP: Comparison output already exists")

for folder in [baseline, intervention]:
    for name in [
        "energy250.csv",
        "network250.tr",
        "positions250.csv"
    ]:
        if not (folder / name).is_file():
            raise SystemExit(f"STOP: Missing {folder / name}")

print("\n===== PHASE 3: NETWORK COMPARISON =====")
print("Baseline:", baseline)
print("Intervention:", intervention)

# Confirm that both experiments use identical node positions.
def checksum(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

if checksum(baseline / "positions250.csv") != checksum(
    intervention / "positions250.csv"
):
    raise SystemExit("STOP: Node positions do not match")

print("\nNetwork positions: MATCH")
print("Controlled shutdown: Node 196 at 155.1 seconds")


# Extract application-layer packet delivery information.
def read_packets(trace):
    sent = {}
    received = {}

    print("\nReading:", trace)

    with trace.open("rb", buffering=1024 * 1024) as f:
        for line in f:
            if not line.startswith((b"s ", b"r ")):
                continue

            if b"-Nl AGT" not in line:
                continue

            if b"-It cbr" not in line:
                continue

            parts = line.split()

            fields = {
                parts[i]: parts[i + 1]
                for i in range(1, len(parts) - 1)
                if parts[i].startswith(b"-")
            }

            try:
                time = float(fields[b"-t"])
                uid = int(fields[b"-Ii"])
                src = int(float(fields[b"-Is"]))
                dst = int(float(fields[b"-Id"]))
            except (KeyError, ValueError):
                continue

            if line.startswith(b"s "):
                if uid in sent:
                    raise SystemExit(
                        f"STOP: Duplicate AGT send UID {uid}"
                    )
                sent[uid] = (time, src, dst)

            elif line.startswith(b"r "):
                if uid not in received or time < received[uid]:
                    received[uid] = time

    if not sent:
        raise SystemExit(
            "STOP: No application-layer CBR sends found. "
            "Trace format needs checking."
        )

    records = []

    for uid, (time, src, dst) in sent.items():
        receive_time = received.get(uid)

        delivered = (
            receive_time is not None
            and receive_time >= time
        )

        records.append({
            "source": src,
            "destination": dst,
            "send_time": time,
            "delivered": int(delivered),
            "delay_ms": (
                (receive_time - time) * 1000
                if delivered else None
            )
        })

    return pd.DataFrame(records)


base_packets = read_packets(baseline / "network250.tr")
test_packets = read_packets(intervention / "network250.tr")

# Verify that traffic generation is comparable.
def traffic_counts(df):
    return Counter(
        zip(df["source"], df["destination"])
    )

if traffic_counts(base_packets) != traffic_counts(test_packets):
    raise SystemExit(
        "STOP: Generated traffic differs between experiments"
    )

print("\nTraffic generation: MATCHED")
print("Generated packets:", len(base_packets))


def metrics(df):
    sent = len(df)
    delivered = int(df["delivered"].sum())

    delays = df.loc[df.delivered == 1, "delay_ms"]

    return {
        "sent": sent,
        "delivered": delivered,
        "pdr_percent": (
            delivered / sent * 100 if sent else 0
        ),
        "mean_delay_ms": (
            float(delays.mean()) if len(delays) else None
        )
    }


def select(df, flow=None, post=False):
    result = df

    if flow is not None:
        result = result[
            (result.source == flow[0])
            & (result.destination == flow[1])
        ]

    if post:
        result = result[result.send_time >= 155.1]

    return result


comparisons = [
    ("Entire network", None, False),
    ("Network after 155.1 s", None, True),
    ("Flow 180 -> 198", (180, 198), False),
    ("Flow 180 -> 198 after 155.1 s", (180, 198), True),
    ("Flow 170 -> 188", (170, 188), False)
]

rows = []

for label, flow, post in comparisons:
    before = metrics(select(base_packets, flow, post))
    after = metrics(select(test_packets, flow, post))

    print(f"\n===== {label.upper()} =====")

    for key in [
        "sent",
        "delivered",
        "pdr_percent",
        "mean_delay_ms"
    ]:
        b = before[key]
        a = after[key]

        if b is None or a is None:
            change = None
            display = "N/A"
        else:
            change = a - b
            display = f"{b:.3f} -> {a:.3f} ({change:+.3f})"

        print(f"{key}: {display}")

        rows.append({
            "scope": label,
            "metric": key,
            "baseline": b,
            "node196_intervention": a,
            "change": change
        })


# Compare remaining energy at the last common timestamp.
def read_final_energy(folder):
    df = pd.read_csv(folder / "energy250.csv")
    last = df.time.max()
    final = df[df.time == last]

    if final.node_id.nunique() != 250:
        raise SystemExit("STOP: Incomplete final energy records")

    return last, final


t1, e1 = read_final_energy(baseline)
t2, e2 = read_final_energy(intervention)

if t1 != t2:
    raise SystemExit("STOP: Final energy times differ")

energy_before = e1.energy.sum()
energy_after = e2.energy.sum()

print("\n===== REMAINING NETWORK ENERGY =====")
print("Measurement time:", t1, "seconds")
print("Baseline:", round(energy_before, 3), "J")
print("Node 196 intervention:", round(energy_after, 3), "J")
print(
    "Change:",
    round(energy_after - energy_before, 3),
    "J"
)

rows.append({
    "scope": "Entire network",
    "metric": "remaining_energy_j",
    "baseline": energy_before,
    "node196_intervention": energy_after,
    "change": energy_after - energy_before
})

# Save a small summary without modifying the original runs.
with output.open("w", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=rows[0].keys()
    )
    writer.writeheader()
    writer.writerows(rows)

print("\n===== COMPARISON COMPLETE =====")
print("Saved:", output)
print("No new NS2 simulation executed")
print("Original experiment files unchanged")
print("Node 196 intervention: EXPERIMENTER-DEFINED")
