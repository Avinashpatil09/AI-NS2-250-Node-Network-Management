"""Offline Random Forest controller — no NS2 shutdowns."""

from pathlib import Path
import sys

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent)
)

import pandas as pd
import joblib

from create_ml_dataset import features
from train_model import FEATURES

T = 150

base = Path("results/topology_jitter01_full")

energy_file = base / "baseline/energy250.csv"
saved_file = base / "frozen_model_checkpoint_150.csv"
audit_file = base / "ai_relay_audit_140_150.csv"

model_file = Path("results/failure_prediction_model.pkl")

output = Path("phase3/output/model_inference_150.csv")
decision_output = Path("phase3/output/model_decision_150.csv")

if output.exists() or decision_output.exists():
    raise SystemExit("STOP: Output already exists.")

# STEP 1: Load energy data up to 150 seconds only
energy = pd.read_csv(energy_file)
energy = energy[energy["time"] <= T].copy()

# STEP 2: Calculate model features
df = features(energy)

checkpoint = df[df["time"] == T].copy()
checkpoint = checkpoint.sort_values("node_id")

if len(checkpoint) != 250:
    raise SystemExit("STOP: Expected 250 nodes.")

if checkpoint["node_id"].nunique() != 250:
    raise SystemExit("STOP: Duplicate node IDs.")

# STEP 3: Load the existing trained AI model
model = joblib.load(model_file)

classes = list(model.classes_)

if 1 not in classes:
    raise SystemExit("STOP: Model has no Class 1.")

# STEP 4: Generate fresh predictions
checkpoint["predicted"] = model.predict(
    checkpoint[FEATURES]
).astype(int)

checkpoint["probability"] = model.predict_proba(
    checkpoint[FEATURES]
)[:, classes.index(1)]

# STEP 5: Assign probability-based risk categories
checkpoint["risk_level"] = pd.cut(
    checkpoint["probability"],
    [-0.001, 0.35, 0.70, 1.001],
    labels=["LOW", "MEDIUM", "HIGH"],
    right=False
).astype(str)

# STEP 6: Verify against previously saved predictions
saved = pd.read_csv(saved_file)

comparison = checkpoint[
    ["node_id", "predicted"]
].merge(
    saved[["node_id", "predicted"]],
    on="node_id",
    suffixes=("_new", "_saved"),
    validate="one_to_one"
)

if len(comparison) != 250:
    raise SystemExit("STOP: Verification row mismatch.")

if not (
    comparison["predicted_new"]
    == comparison["predicted_saved"]
).all():
    raise SystemExit("STOP: Predictions do not match.")

# STEP 7: Identify predicted future low-energy nodes
positive_nodes = checkpoint.loc[
    checkpoint["predicted"] == 1,
    "node_id"
].astype(int).tolist()

# STEP 8: Read routing activity
audit = pd.read_csv(audit_file)
audit = audit.set_index("node_id", verify_integrity=True)

missing = []
mismatched = []
active_relays = []

for node in positive_nodes:
    if node not in audit.index:
        missing.append(node)
        continue

    row = audit.loc[node]

    if int(row["predicted_risk"]) != 1:
        mismatched.append(node)

    if (
        int(row["rtr_forward_events"]) > 0
        or int(row["unique_relay_tx_packets"]) > 0
    ):
        active_relays.append(node)

# STEP 9: Make a conservative decision
if missing or mismatched:
    decision = "INSUFFICIENT_EVIDENCE"
elif active_relays:
    decision = "REVIEW_REQUIRED"
else:
    decision = "NO_ACTION"

# STEP 10: Save new results
output.parent.mkdir(parents=True, exist_ok=True)

checkpoint[
    [
        "time",
        "node_id",
        *FEATURES,
        "predicted",
        "probability",
        "risk_level"
    ]
].to_csv(output, index=False)

pd.DataFrame([{
    "checkpoint_s": T,
    "predicted_positive_nodes": ";".join(
        map(str, positive_nodes)
    ),
    "positive_count": len(positive_nodes),
    "high_probability_count": int(
        (checkpoint["probability"] >= 0.70).sum()
    ),
    "active_relay_nodes": ";".join(
        map(str, active_relays)
    ),
    "missing_audit_nodes": ";".join(map(str, missing)),
    "audit_mismatch_nodes": ";".join(
        map(str, mismatched)
    ),
    "decision": decision,
    "automatic_shutdown": False,
    "audit_window": "140-150s (recorded RTR CBR only)",
    "mac_evidence": "UNAVAILABLE_TRACE_OFF"
}]).to_csv(decision_output, index=False)

print("\n===== PHASE 3: DIRECT AI INFERENCE =====")
print("Checkpoint:", T, "seconds")
print("Nodes evaluated:", len(checkpoint))

print("\nPredicted Class 1 nodes:")
print(positive_nodes)

print("\nHIGH probability nodes:",
      int((checkpoint.probability >= 0.70).sum()))

print("\nSaved predictions match: YES")
print("Observed active CBR relays:", active_relays)
print("AI Decision:", decision)
print("Automatic shutdown: NO")

print("\nSaved:", output)
print("Saved:", decision_output)

print("\nOriginal files unchanged")
