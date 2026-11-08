"""Real model predictions with clearly labelled synthetic relay tests."""

import sys
from pathlib import Path

ROOT = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(ROOT))

import joblib
import pandas as pd

from create_ml_dataset import features
from train_model import FEATURES
from safety_policy import evaluate_decision

CHECKPOINT = 150.0

base = ROOT / "results/topology_jitter01_full"
energy_file = base / "baseline/energy250.csv"
saved_file = base / "frozen_model_checkpoint_150.csv"
audit_file = base / "ai_relay_audit_140_150.csv"

# STEP 1: Use real NS2 energy data up to 150 s.
energy = pd.read_csv(energy_file)
energy = energy[energy["time"] <= CHECKPOINT].copy()

current = features(energy)
current = current[
    (current["time"] - CHECKPOINT).abs() < 1e-7
].sort_values("node_id")

assert len(current) == 250
assert current["node_id"].nunique() == 250

# STEP 2: Execute the real saved Random Forest.
model = joblib.load(
    ROOT / "results/failure_prediction_model.pkl"
)

current["predicted"] = model.predict(
    current[FEATURES]
).astype(int)

positive_nodes = sorted(
    current.loc[
        current["predicted"] == 1, "node_id"
    ].astype(int).tolist()
)

# STEP 3: Verify predictions against saved evidence.
saved = pd.read_csv(saved_file)

comparison = current[
    ["node_id", "predicted"]
].merge(
    saved[["node_id", "predicted"]],
    on="node_id",
    suffixes=("_new", "_saved"),
    validate="one_to_one"
)

assert len(comparison) == 250
assert (
    comparison["predicted_new"]
    == comparison["predicted_saved"]
).all()

if not positive_nodes:
    raise SystemExit(
        "STOP: No positive nodes available for replay."
    )

target = positive_nodes[0]

# STEP 4: Inspect real routing-audit evidence.
audit = pd.read_csv(audit_file)

print("\n===== REAL MODEL PREDICTIONS =====")
print("Checkpoint:", CHECKPOINT, "seconds")
print("Nodes evaluated:", len(current))
print("Predicted low-energy nodes:", positive_nodes)
print("Saved predictions match: YES")

print("\n===== EXISTING ROUTING AUDIT =====")
print("Audit rows:", len(audit))
print(
    "Recorded forwarding events in selected audit rows:",
    int(audit["rtr_forward_events"].sum())
)
print(
    "Complete network-wide routing evidence:",
    "NOT ESTABLISHED"
)

# STEP 5: Exercise the safety policy with test fixtures.
# The forwarding counts below are SYNTHETIC, not
# observed traffic from the original simulation.

scenarios = [
    (
        "REAL SAVED AUDIT — incomplete network coverage",
        dict(
            predicted_positive_nodes=positive_nodes,
            forwarding_counts={
                int(row.node_id): int(row.rtr_forward_events)
                for row in audit.itertuples()
            },
            rtr_cbr_events=0,
            audit_complete=False
        ),
        "INSUFFICIENT_EVIDENCE"
    ),
    (
        "SYNTHETIC — predicted node actively forwarding",
        dict(
            predicted_positive_nodes=positive_nodes,
            forwarding_counts={target: 5},
            rtr_cbr_events=5,
            audit_complete=True
        ),
        "REVIEW_REQUIRED"
    ),
    (
        "SYNTHETIC — forwarding node is not predicted positive",
        dict(
            predicted_positive_nodes=positive_nodes,
            forwarding_counts={8: 3},
            rtr_cbr_events=3,
            audit_complete=True
        ),
        "NO_MATCH_IN_OBSERVED_WINDOW"
    ),
    (
        "SYNTHETIC — no routing evidence",
        dict(
            predicted_positive_nodes=positive_nodes,
            forwarding_counts={},
            rtr_cbr_events=0,
            audit_complete=False
        ),
        "INSUFFICIENT_EVIDENCE"
    ),
    (
        "SYNTHETIC — incomplete forwarding audit",
        dict(
            predicted_positive_nodes=positive_nodes,
            forwarding_counts={target: 5},
            rtr_cbr_events=5,
            audit_complete=False
        ),
        "INSUFFICIENT_EVIDENCE"
    )
]

print("\n===== SAFETY POLICY REPLAY =====")

for name, inputs, expected in scenarios:
    result = evaluate_decision(**inputs)

    assert result["decision"] == expected, name
    assert result["action"] == "NO_ACTION", name
    assert result["automatic_shutdown"] is False, name

    print("\nScenario:", name)
    print("Decision:", result["decision"])
    print("Matched relays:", result["matched_relays"])
    print("Permitted action:", result["action"])
    print("Result: PASSED")

print("\n======================================")
print("POSITIVE-PREDICTION POLICY REPLAY: PASSED")
print("Real Random Forest predictions verified")
print("Synthetic forwarding scenarios labelled")
print("Automatic shutdown: DISABLED")
print("Original project files unchanged")
