"""Generate Phase 3 comparison graphs from verified CSV results."""

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path.cwd()

comparison_file = ROOT / "phase3/output/node196_comparison.csv"
review_file = ROOT / "phase3/output/node196_safety_review.json"

output = ROOT / "phase3/final_figures"

if not comparison_file.is_file():
    raise SystemExit("STOP: Comparison CSV missing")

if not review_file.is_file():
    raise SystemExit("STOP: Safety review missing")

with comparison_file.open(newline="") as f:
    rows = list(csv.DictReader(f))

review = json.loads(review_file.read_text())

if review["safety_assessment"] != "BLOCK_AUTO_SHUTDOWN":
    raise SystemExit("STOP: Unexpected safety assessment")

def get_metric(scope, metric):
    matches = [
        r for r in rows
        if r["scope"] == scope and r["metric"] == metric
    ]

    if len(matches) != 1:
        raise SystemExit(
            f"STOP: Missing metric {scope} / {metric}"
        )

    row = matches[0]

    return (
        float(row["baseline"]),
        float(row["node196_intervention"])
    )


def comparison_chart(title, ylabel, values, filename):
    fig, ax = plt.subplots(figsize=(9, 6))

    labels = [
        "Baseline",
        "Node 196 disabled"
    ]

    bars = ax.bar(labels, values, width=0.55)

    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=11
        )

    ax.set_title(title, fontsize=14, weight="bold")
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, max(values) * 1.25)
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(output / filename, dpi=200)
    plt.close(fig)

    print("CREATED:", filename)


# Check output files before creating any figures.
filenames = [
    "01_network_pdr.png",
    "02_affected_flow_pdr.png",
    "03_remaining_energy_change.png",
    "04_network_delay.png"
]

if any((output / name).exists() for name in filenames):
    raise SystemExit(
        "STOP: Existing figures detected. No files overwritten."
    )

print("\n===== PHASE 3: FINAL GRAPHS =====")

output.mkdir(parents=True, exist_ok=True)

# GRAPH 1: Overall PDR
baseline, intervention = get_metric(
    "Entire network",
    "pdr_percent"
)

comparison_chart(
    "Overall Network Packet Delivery Ratio",
    "Packet Delivery Ratio (%)",
    [baseline, intervention],
    filenames[0]
)

# GRAPH 2: Affected flow after intervention
flow_before, flow_after = get_metric(
    "Flow 180 -> 198 after 155.1 s",
    "pdr_percent"
)

comparison_chart(
    "Flow 180 to 198: PDR After 155.1 Seconds",
    "Packet Delivery Ratio (%)",
    [flow_before, flow_after],
    filenames[1]
)

# GRAPH 3: Change in remaining energy
energy_before, energy_after = get_metric(
    "Entire network",
    "remaining_energy_j"
)

energy_change = energy_after - energy_before

fig, ax = plt.subplots(figsize=(9, 6))

ax.bar(
    ["Node 196 intervention"],
    [energy_change],
    width=0.5
)

ax.set_title(
    "Change in Total Remaining Network Energy",
    fontsize=14,
    weight="bold"
)

ax.set_ylabel("Change relative to baseline (J)")
ax.axhline(0, linewidth=1)

ax.text(
    0,
    energy_change,
    f"{energy_change:+.3f} J",
    ha="center",
    va="bottom" if energy_change >= 0 else "top",
    fontsize=12
)

ax.set_ylim(
    min(0, energy_change * 1.3) - 1,
    max(0, energy_change * 1.3) + 1
)

ax.grid(axis="y", alpha=0.25)

fig.tight_layout()
fig.savefig(output / filenames[2], dpi=200)
plt.close(fig)

print("CREATED:", filenames[2])

# GRAPH 4: Overall mean end-to-end delay
delay_before, delay_after = get_metric(
    "Entire network",
    "mean_delay_ms"
)

comparison_chart(
    "Overall Mean End-to-End Delay",
    "Mean delay of delivered packets (ms)",
    [delay_before, delay_after],
    filenames[3]
)

print("\n===== FINAL SUMMARY =====")

print(
    "Overall PDR change:",
    round(intervention - baseline, 3),
    "percentage points"
)

print(
    "Affected-flow PDR change:",
    round(flow_after - flow_before, 3),
    "percentage points"
)

print(
    "Remaining energy change:",
    round(energy_change, 3),
    "J"
)

print(
    "Overall delay change:",
    round(delay_after - delay_before, 3),
    "ms"
)

print("\nSafety decision: BLOCK_AUTO_SHUTDOWN")
print("Intervention type: Experimenter-defined")
print("Automatic AI shutdown: NOT AUTHORIZED")

print("\nGraphs saved in:", output)
print("Original results unchanged")
print("\nFINAL GRAPH GENERATION: PASSED")
