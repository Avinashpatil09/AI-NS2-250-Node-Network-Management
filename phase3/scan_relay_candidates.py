"""Read-only analysis of genuine low-energy relay candidates."""

from pathlib import Path
from collections import Counter
import csv
import json
import math
import sys

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from create_ml_dataset import features
from train_model import FEATURES

print("\n===== STEP 16: REAL RELAY CANDIDATE AUDIT =====")

# Locate the completed 250-node simulation.
runs = list(Path("/tmp").glob(
    "ns2-phase3-live250-*/results/phase3_decision.json"
))

if not runs:
    raise SystemExit("STOP: Live simulation not found")

decision_file = max(runs, key=lambda p: p.stat().st_mtime)
result_dir = decision_file.parent

energy_file = result_dir / "energy250.csv"
trace_file = result_dir / "network250.tr"

if not energy_file.is_file() or not trace_file.is_file():
    raise SystemExit("STOP: Required simulation evidence missing")

output = ROOT / "phase3/output/real_relay_candidates.csv"

if output.exists():
    raise SystemExit("STOP: Output already exists; not overwriting")

print("Experiment:", result_dir)
print("Trace size:", round(trace_file.stat().st_size / 1024**3, 2), "GiB")

# Checkpoints with a future measurement available.
checkpoints = list(range(120, 181, 5))

energy = pd.read_csv(energy_file)
history = energy[energy.time <= max(checkpoints)].copy()

data = features(history)
data = data[data.time.isin(checkpoints)].copy()

model = joblib.load(
    ROOT / "results/failure_prediction_model.pkl"
)

data["predicted"] = model.predict(
    data[FEATURES]
).astype(int)

positive_by_time = {}

for t in checkpoints:
    rows = data[data.time == t]

    if len(rows) != 250 or rows.node_id.nunique() != 250:
        raise SystemExit(f"STOP: Incomplete energy data at {t}s")

    positive_by_time[t] = set(
        rows.loc[rows.predicted == 1, "node_id"].astype(int)
    )

# Confirm compatibility with the completed live checkpoint.
saved_decision = json.loads(decision_file.read_text())

if positive_by_time[150] != set(
    map(int, saved_decision["predicted_positive_nodes"])
):
    raise SystemExit("STOP: 150-second predictions do not match")

print("\n150-second predictions verified")
print("Scanning recorded routing trace...")

forwarding = {t: Counter() for t in checkpoints}
routing_events = Counter()
unparsed_forwards = Counter()

# Stream the trace rather than loading it into RAM.
with trace_file.open("rb", buffering=1024 * 1024) as stream:
    for line in stream:

        if not line.startswith((b"f ", b"r ", b"s ")):
            continue

        if b"-Nl RTR" not in line or b"-It cbr" not in line:
            continue

        parts = line.split()

        try:
            timestamp = float(
                parts[parts.index(b"-t") + 1]
            )
        except (ValueError, IndexError):
            continue

        # Each checkpoint audits (t-5, t].
        checkpoint = int(math.ceil(timestamp / 5.0) * 5)

        if checkpoint not in forwarding:
            continue

        routing_events[checkpoint] += 1

        if parts[0] != b"f":
            continue

        try:
            node = int(parts[parts.index(b"-Ni") + 1])
        except (ValueError, IndexError):
            unparsed_forwards[checkpoint] += 1
            continue

        forwarding[checkpoint][node] += 1

rows_out = []

print("\n===== GENUINE CHECKPOINT COMPARISON =====")
print("Time | Predicted | Forwarders | Matches | RTR CBR events")

for t in checkpoints:

    positives = positive_by_time[t]
    forwarders = set(forwarding[t])

    matched = sorted(positives & forwarders)

    row = {
        "checkpoint_s": t,
        "predicted_positive_count": len(positives),
        "observed_forwarder_count": len(forwarders),
        "matched_relay_count": len(matched),
        "matched_relay_ids": ";".join(map(str, matched)),
        "rtr_cbr_events": routing_events[t],
        "unparsed_forward_records": unparsed_forwards[t]
    }

    rows_out.append(row)

    print(
        f"{t:4} | "
        f"{len(positives):9} | "
        f"{len(forwarders):10} | "
        f"{len(matched):7} | "
        f"{routing_events[t]}"
    )

total_matches = sum(
    row["matched_relay_count"] for row in rows_out
)

with output.open("w", newline="") as stream:
    writer = csv.DictWriter(
        stream,
        fieldnames=rows_out[0].keys()
    )
    writer.writeheader()
    writer.writerows(rows_out)

print("\n===== FINAL FINDING =====")

if total_matches:
    print("Observed low-energy relay matches:", total_matches)
    print("NEXT: Investigate connectivity and alternative routes")
else:
    print("No matching CBR forwarding relays in sampled windows")
    print("NEXT: Review routing evidence and possible alternatives")

print("\nSaved:", output)
print("No node shutdown performed")
print("Original NS2 files unchanged")
print("ANALYSIS COMPLETE")
