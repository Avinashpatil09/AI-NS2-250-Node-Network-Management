#!/usr/bin/env python3
"""Find active NS2 AODV CBR relays that are predicted HIGH risk at t=155 s.

Uses PREVIOUSLY GENERATED simulation files. Does not rerun NS2, write any
simulation inputs, or claim a real route has changed.

Inputs: results/active_forwarders_140_150.csv, energy250.csv,
        failure_prediction_model.pkl, positions250.csv.
Outputs: results/active_relay_risks_155.csv, relay_candidates_155.csv.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import joblib

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from create_ml_dataset import features
from train_model import FEATURES

OUT = ROOT / "results"
CHECKPOINT = 155.0


def require(name):
    path = OUT / name
    if not path.is_file():
        raise SystemExit(f"Missing {path}. Keep the earlier NS2 and Python outputs.")
    return path


def main():
    relay = pd.read_csv(require("active_forwarders_140_150.csv"))
    energy = pd.read_csv(require("energy250.csv"))
    positions = pd.read_csv(require("positions250.csv"))
    model = joblib.load(require("failure_prediction_model.pkl"))

    needed = {"node_id", "rtr_cbr_forwarded"}
    if not needed.issubset(relay):
        raise SystemExit(f"Unexpected relay CSV columns: {list(relay.columns)}")

    snapshot = features(energy)
    snapshot = snapshot[np.isclose(snapshot["time"], CHECKPOINT)].copy()
    if len(snapshot) != 250 or snapshot.node_id.nunique() != 250:
        raise SystemExit(f"At t={CHECKPOINT:g}, expected one row for each of 250 nodes; got {len(snapshot)}.")

    classes = list(model.classes_)
    probabilities = model.predict_proba(snapshot[FEATURES])
    snapshot["failure_probability"] = (
        probabilities[:, classes.index(1)] if 1 in classes
        else np.zeros(len(snapshot), dtype=float)
    )
    snapshot["risk_level"] = np.select(
        [snapshot.failure_probability >= 0.70, snapshot.failure_probability >= 0.35],
        ["HIGH", "MEDIUM"], default="LOW"
    )

    # Forwarding occurred DURING 140-150 s; risk is assessed at 155 s.
    active = relay.loc[relay.rtr_cbr_forwarded > 0, ["node_id", "rtr_cbr_forwarded"]].copy()
    audit = active.merge(snapshot[["node_id", "time", "energy", "failure_probability", "risk_level"]],
                         on="node_id", how="left", validate="one_to_one")
    audit = audit.sort_values(["rtr_cbr_forwarded", "node_id"], ascending=[False, True])
    audit.to_csv(OUT / "active_relay_risks_155.csv", index=False)
    high = audit.loc[audit.risk_level.eq("HIGH")].copy()

    pos = positions.set_index("node_id")
    low = snapshot.loc[snapshot.risk_level.eq("LOW"), ["node_id", "energy"]].copy()
    low = low.merge(positions, on="node_id", validate="one_to_one")
    used = set()
    recommendations = []
    for row in high.head(20).itertuples(index=False):
        source_id = int(row.node_id)
        px = float(pos.loc[source_id, "x"])
        py = float(pos.loc[source_id, "y"])
        possibilities = low[~low.node_id.isin(used | {source_id})].copy()
        if possibilities.empty:
            replacement, distance = "", ""
        else:
            possibilities["distance_m"] = np.hypot(possibilities.x - px, possibilities.y - py)
            best = possibilities.sort_values(["distance_m", "node_id"]).iloc[0]
            replacement, distance = int(best.node_id), round(float(best.distance_m), 2)
            used.add(replacement)
        recommendations.append({
            "high_risk_active_relay": source_id,
            "forwarded_140_150": int(row.rtr_cbr_forwarded),
            "risk_at_155": "HIGH",
            "probability_at_155": round(float(row.failure_probability), 4),
            "suggested_low_risk_node": replacement,
            "distance_m": distance,
            "action_status": "UNVERIFIED_CANDIDATE_NOT_REROUTED",
        })
    cols = ["high_risk_active_relay", "forwarded_140_150", "risk_at_155",
            "probability_at_155", "suggested_low_risk_node", "distance_m", "action_status"]
    pd.DataFrame(recommendations, columns=cols).to_csv(OUT / "relay_candidates_155.csv", index=False)

    print("\nRISK AT 155 SECONDS (all nodes):")
    for name in ("LOW", "MEDIUM", "HIGH"):
        print(f"  {name:6}: {(snapshot.risk_level == name).sum():3d}")
    print(f"\nActive CBR relay nodes during 140-150 s: {len(active)}")
    print(f"Of those, predicted HIGH risk at 155 s: {len(high)}")
    if high.empty:
        print("No HIGH-risk active relays found at this checkpoint. Do not claim AI-controlled rerouting.")
    else:
        print("\nTOP HIGH-RISK ACTIVE RELAYS (observed forwarding, then risk):")
        print(high[["node_id", "rtr_cbr_forwarded", "energy", "failure_probability"]].head(12).to_string(index=False))
        print("\nCANDIDATE LOWER-RISK NODES (NEARBY ONLY; NOT VERIFIED ROUTES):")
        print(pd.DataFrame(recommendations, columns=cols).head(10).to_string(index=False))
    print("\nSaved results/active_relay_risks_155.csv")
    print("Saved results/relay_candidates_155.csv")
    print("IMPORTANT: Nearest-node suggestions are NOT proof of connectivity, route usage, or improved delivery.")


if __name__ == "__main__":
    main()
