"""Read-only audit of a completed NS2 integration test."""

import json
import sys
from collections import Counter
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit(
        "Usage: python audit_runtime_trace.py TEST_DIR"
    )

folder = Path(sys.argv[1])

trace_file = folder / "results/network250.tr"
decision_file = folder / "results/phase3_decision.json"

if not trace_file.is_file():
    raise SystemExit("STOP: NS2 trace not found")

if not decision_file.is_file():
    raise SystemExit("STOP: AI decision file not found")

report = json.loads(decision_file.read_text())

checkpoint = float(report["checkpoint_s"])
start = checkpoint - 5.0

positive_nodes = set(
    map(int, report["predicted_positive_nodes"])
)

forwarding = Counter()
routing_events = 0
unparsed_nodes = 0

with trace_file.open(errors="replace") as f:
    for line in f:
        parts = line.split()

        if not parts or parts[0] not in ("f", "r", "s"):
            continue

        fields = {
            parts[i]: parts[i + 1]
            for i in range(1, len(parts) - 1)
            if parts[i].startswith("-")
        }

        try:
            event_time = float(fields["-t"])
        except (KeyError, ValueError):
            continue

        if not (start <= event_time <= checkpoint):
            continue

        if fields.get("-Nl") != "RTR":
            continue

        if fields.get("-It", "").lower() != "cbr":
            continue

        routing_events += 1

        if parts[0] == "f":
            try:
                node = int(fields["-Ni"])
            except (KeyError, ValueError):
                unparsed_nodes += 1
                continue

            forwarding[node] += 1

active_relays = set(forwarding)

matched = sorted(
    positive_nodes.intersection(active_relays)
)

if not positive_nodes:
    assessment = "NO_PREDICTED_LOW_ENERGY_NODES"
elif routing_events == 0 or unparsed_nodes:
    assessment = "INSUFFICIENT_EVIDENCE"
elif matched:
    assessment = "REVIEW_REQUIRED"
else:
    assessment = "NO_MATCH_IN_OBSERVED_WINDOW"

print("\n===== PHASE 3 ROUTING AUDIT =====")

print("Observation window:", start, "to", checkpoint, "s")
print("Nodes evaluated by AI:", report["nodes_evaluated"])

print("\nPredicted low-energy nodes:")
print(sorted(positive_nodes))

print("\nRTR CBR events:", routing_events)
print("Forwarding records with unparsed nodes:", unparsed_nodes)

print("\nObserved forwarding nodes:")
print(sorted(active_relays))

print("\nPredicted nodes observed forwarding:")
print(matched)

print("\n===== SAFETY ASSESSMENT =====")
print("Assessment:", assessment)
print("Permitted action: NO_ACTION")
print("Automatic shutdown: NO")

print("\nNOTE:")
print("This audit covers only the selected time window.")
print("MAC-layer activity is not evaluated.")
print("No routing changes have been applied.")
