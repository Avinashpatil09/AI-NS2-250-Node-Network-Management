import pandas as pd
import numpy as np
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from create_ml_dataset import features
from train_model import FEATURES

# Load NS2 energy measurements
energy = pd.read_csv("results/energy250.csv")

# Calculate the same features used during training
data = features(energy)

# Select the early-warning checkpoint
checkpoint = 150.0

snapshot = data[
    np.isclose(data["time"], checkpoint)
].copy()

if len(snapshot) != 250:
    raise SystemExit("Expected 250 nodes at 150 seconds.")

# Load the existing trained model
model = joblib.load(
    "results/failure_prediction_model.pkl"
)

# Predict probability of future low-energy risk
prob = model.predict_proba(snapshot[FEATURES])

classes = list(model.classes_)
snapshot["failure_probability"] = (
    prob[:, classes.index(1)]
    if 1 in classes else 0.0
)

# Classify node risk
snapshot["risk_level"] = np.where(
    snapshot["failure_probability"] >= 0.70,
    "HIGH",
    np.where(
        snapshot["failure_probability"] >= 0.35,
        "MEDIUM",
        "LOW"
    )
)

# Save predictions separately
snapshot.to_csv(
    "results/checkpoint_150_predictions.csv",
    index=False
)

print("\nRISK AT 150 SECONDS:")
print(snapshot["risk_level"].value_counts())

# Get actual simulated node positions
positions = pd.read_csv("results/positions250.csv")
network = snapshot.merge(positions, on="node_id")

high = network[network["risk_level"] == "HIGH"]
low = network[network["risk_level"] == "LOW"]

# Suggest nearby LOW-risk nodes
actions = []

for node in high.itertuples():
    candidates = low[
        low["node_id"] != node.node_id
    ]

    if candidates.empty:
        alternative = None
        distance = None
    else:
        distance_squared = (
            (candidates["x"] - node.x) ** 2 +
            (candidates["y"] - node.y) ** 2
        )
        selected = distance_squared.idxmin()
        alternative = int(candidates.loc[selected, "node_id"])
        distance = float(np.sqrt(distance_squared.loc[selected]))

    actions.append({
        "high_risk_node": node.node_id,
        "suggested_alternative": alternative,
        "distance_m": distance,
        "action": "CANDIDATE_ONLY_NOT_REROUTED"
    })

actions_df = pd.DataFrame(actions)

actions_df.to_csv(
    "results/checkpoint_150_actions.csv",
    index=False
)

print("\nPREVENTIVE CANDIDATES:")
print(actions_df.to_string(index=False))

# Generate network risk topology
plt.figure(figsize=(10, 8))

colors = {
    "LOW": "green",
    "MEDIUM": "orange",
    "HIGH": "red"
}

for level in ["LOW", "MEDIUM", "HIGH"]:
    subset = network[
        network["risk_level"] == level
    ]

    plt.scatter(
        subset["x"],
        subset["y"],
        label=level,
        color=colors[level],
        s=30 if level != "HIGH" else 100
    )

plt.title("250-Node Risk Map at 150 Seconds")
plt.xlabel("X Position (m)")
plt.ylabel("Y Position (m)")
plt.legend()
plt.axis("equal")
plt.tight_layout()

plt.savefig(
    "results/graphs/checkpoint_150_topology.png",
    dpi=200
)

plt.close()

print("\nCheckpoint analysis completed.")
