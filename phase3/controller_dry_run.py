import csv
from pathlib import Path

base = Path("results/topology_jitter01_full")

checkpoint_file = base / "frozen_model_checkpoint_150.csv"
audit_file = base / "ai_relay_audit_140_150.csv"

output = Path("phase3/output/dry_run_decision_150.csv")

# Read saved AI predictions
with checkpoint_file.open(newline="") as f:
    predictions = list(csv.DictReader(f))

# Read routing activity
with audit_file.open(newline="") as f:
    audits = list(csv.DictReader(f))

if len(predictions) != 250:
    raise SystemExit("STOP: Expected 250 checkpoint rows")

if any(float(r["time"]) != 150 for r in predictions):
    raise SystemExit("STOP: Checkpoint time mismatch")

# Identify predicted future low-energy nodes
predicted_positive = sorted(
    int(r["node_id"])
    for r in predictions
    if int(r["predicted"]) == 1
)

audit_by_node = {
    int(r["node_id"]): r
    for r in audits
}

# Check evidence completeness
missing = [
    n for n in predicted_positive
    if n not in audit_by_node
]

mismatch = [
    n for n in predicted_positive
    if n in audit_by_node
    and int(audit_by_node[n]["predicted_risk"]) != 1
]

# Identify observed forwarding relays
active = []

for node in predicted_positive:
    if node in audit_by_node:
        row = audit_by_node[node]

        if (
            int(row["rtr_forward_events"]) > 0
            or int(row["unique_relay_tx_packets"]) > 0
        ):
            active.append(node)

# Conservative decision logic
if missing or mismatch:
    decision = "INSUFFICIENT_EVIDENCE"
elif active:
    decision = "REVIEW_REQUIRED"
else:
    decision = "NO_ACTION"

summary = {
    "checkpoint_s": "150",
    "predicted_positive_nodes": ";".join(
        map(str, predicted_positive)
    ),
    "predicted_positive_count": len(predicted_positive),
    "active_relay_nodes": ";".join(map(str, active)),
    "observed_active_relays": len(active),
    "missing_audit_nodes": ";".join(map(str, missing)),
    "decision": decision,
    "automatic_shutdown": "False",
    "mac_evidence": "UNAVAILABLE_TRACE_OFF"
}

output.parent.mkdir(parents=True, exist_ok=True)

if output.exists():
    raise SystemExit("STOP: Output already exists")

with output.open("w", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=summary.keys()
    )
    writer.writeheader()
    writer.writerow(summary)

print("\n===== PHASE 3 AI CONTROLLER =====")
print("Checkpoint: 150 seconds")
print("Predicted low-energy nodes:", predicted_positive)
print("Observed active CBR relays:", active)
print("AI Decision:", decision)
print("Automatic shutdown: NO")
print("MAC-layer evidence: unavailable")
print("\nSaved:", output)
print("Original simulation files unchanged")

