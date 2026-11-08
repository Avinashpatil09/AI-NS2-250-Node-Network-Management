"""Safe AI inference called during an NS2 simulation."""

import json
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from create_ml_dataset import features
from train_model import FEATURES


def main():
    if len(sys.argv) != 4:
        raise SystemExit("Invalid arguments")

    energy_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    checkpoint = float(sys.argv[3])

    if output_file.exists():
        raise SystemExit("STOP: Output already exists")

    # Read energy observed up to the checkpoint
    data = pd.read_csv(energy_file)

    required = {"time", "node_id", "energy"}

    if not required.issubset(data.columns):
        raise SystemExit("Invalid energy CSV")

    data = data[data.time <= checkpoint].copy()

    # Generate features without future observations
    data = features(data)

    current = data[
        data.time == checkpoint
    ].sort_values("node_id")

    if len(current) != 10:
        raise SystemExit("Expected 10 nodes")

    if current.node_id.nunique() != 10:
        raise SystemExit("Duplicate node IDs")

    # Load the existing trained Random Forest
    model = joblib.load(
        ROOT / "results/failure_prediction_model.pkl"
    )

    classes = list(model.classes_)

    if 1 not in classes:
        raise SystemExit("Model missing Class 1")

    predictions = model.predict(
        current[FEATURES]
    ).astype(int)

    probabilities = model.predict_proba(
        current[FEATURES]
    )[:, classes.index(1)]

    positive_nodes = current.loc[
        predictions == 1, "node_id"
    ].astype(int).tolist()

    # No verified routing audit exists for this
    # new small-network checkpoint.
    # Therefore, intervention is not permitted.
    report = {
        "checkpoint_s": checkpoint,
        "nodes_evaluated": len(current),
        "predicted_positive_nodes": positive_nodes,
        "predicted_positive_count": int(
            predictions.sum()
        ),
        "high_probability_count": int(
            (probabilities >= 0.70).sum()
        ),
        "routing_audit": "NOT_AVAILABLE",
        "decision": "INSUFFICIENT_EVIDENCE",
        "action": "NO_ACTION",
        "automatic_shutdown": False
    }

    output_file.parent.mkdir(
        parents=True, exist_ok=True
    )

    output_file.write_text(
        json.dumps(report, indent=2) + "\n"
    )

    # Return the safe action to NS2
    print("NO_ACTION")


if __name__ == "__main__":
    main()
