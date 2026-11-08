"""Safe AI inference and routing audit during an NS2 simulation."""

import json
import sys
from collections import Counter
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(ROOT))

from create_ml_dataset import features
from train_model import FEATURES
from safety_policy import evaluate_decision


def main():
    if len(sys.argv) != 5:
        raise SystemExit(
            "Usage: handoff_routing.py ENERGY TRACE OUTPUT TIME"
        )

    energy_path = Path(sys.argv[1])
    trace_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])
    checkpoint = float(sys.argv[4])

    if output_path.exists():
        raise SystemExit("STOP: Output already exists")

    # 1. Read energy measurements up to the checkpoint.
    energy = pd.read_csv(energy_path)
    energy = energy[energy.time <= checkpoint].copy()

    current = features(energy)
    current = current[
        (current.time - checkpoint).abs() < 1e-7
    ].sort_values("node_id")

    if len(current) != 250 or current.node_id.nunique() != 250:
        raise SystemExit("STOP: Expected 250 distinct nodes")

    # 2. Execute the trained Random Forest.
    model = joblib.load(
        ROOT / "results/failure_prediction_model.pkl"
    )

    classes = list(model.classes_)
    if 1 not in classes:
        raise SystemExit("STOP: Positive class unavailable")

    predictions = model.predict(
        current[FEATURES]
    ).astype(int)

    probabilities = model.predict_proba(
        current[FEATURES]
    )[:, classes.index(1)]

    positive_nodes = set(
        current.loc[
            predictions == 1, "node_id"
        ].astype(int)
    )

    # 3. Examine routing events from the previous 5 seconds.
    start = checkpoint - 5.0

    forwarding = Counter()
    routing_events = 0
    unparsed_forwards = 0

    with trace_path.open(errors="replace") as stream:
        for line in stream:
            parts = line.split()

            if not parts or parts[0] not in ("f", "r", "s"):
                continue

            fields = {
                parts[i]: parts[i + 1]
                for i in range(1, len(parts) - 1)
                if parts[i].startswith("-")
            }

            try:
                t = float(fields["-t"])
            except (KeyError, ValueError):
                continue

            if not start <= t <= checkpoint:
                continue

            if fields.get("-Nl") != "RTR":
                continue

            if fields.get("-It", "").lower() != "cbr":
                continue

            routing_events += 1

            if parts[0] == "f":
                try:
                    node = int(fields["-Ni"])
                    forwarding[node] += 1
                except (KeyError, ValueError):
                    unparsed_forwards += 1

    active_relays = sorted(
        positive_nodes.intersection(forwarding)
    )


    # 4. Apply the tested safety policy.
    policy = evaluate_decision(
        predicted_positive_nodes=sorted(positive_nodes),
        forwarding_counts=dict(forwarding),
        rtr_cbr_events=routing_events,
        unparsed_forward_records=unparsed_forwards,
        audit_complete=True
    )

    decision = policy["decision"]
    action = policy["action"]

    if action != "NO_ACTION":
        raise SystemExit("STOP: Unexpected controller action.")

    report = {
        "policy_engine": "safety_policy.evaluate_decision",
        "checkpoint_s": checkpoint,
        "nodes_evaluated": len(current),
        "predicted_positive_nodes": sorted(positive_nodes),
        "high_probability_count": int(
            (probabilities >= 0.70).sum()
        ),
        "routing_window_s": [start, checkpoint],
        "rtr_cbr_events": routing_events,
        "forwarding_events": sum(forwarding.values()),
        "observed_forwarders": sorted(forwarding),
        "positive_forwarding_relays": active_relays,
        "unparsed_forward_records": unparsed_forwards,
        "decision": decision,
        "action": action,
        "automatic_shutdown": False,
        "mac_evidence": "UNAVAILABLE_TRACE_OFF"
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path.write_text(
        json.dumps(report, indent=2) + "\n"
    )

    # Send the permitted action back to NS2.
    print(action)


if __name__ == "__main__":
    main()
