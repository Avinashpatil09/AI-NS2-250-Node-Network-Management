from pathlib import Path
import csv
import matplotlib.pyplot as plt

out = Path("results/traffic_sensitivity")
out.mkdir(parents=True, exist_ok=True)

def read_csv(path):
    with open(path, newline="") as f:
        return {r["scenario"]: r for r in csv.DictReader(f)}

low = read_csv(
    "results/validation_load025/performance_125_143.csv"
)

low_energy = read_csv(
    "results/validation_load025/energy_summary.csv"
)

high = read_csv(
    "results/validation_load015/performance_energy_125_143.csv"
)

rows = []

# Original 0.20 s results from previous analysis.
original = {
    "baseline": (95, 61, 64.21, 3494.825),
    "preventive": (95, 84, 88.42, 1450.866)
}

for scenario, (sent, received, pdr, delay) in original.items():
    rows.append({
        "interval_s": "0.20",
        "scenario": scenario,
        "sent": sent,
        "received": received,
        "lost": sent - received,
        "pdr_percent": pdr,
        "mean_delay_ms": delay,
        "total_energy_consumed_j": ""
    })

for scenario in ("baseline", "preventive"):
    r = low[scenario]
    rows.append({
        "interval_s": "0.25",
        "scenario": scenario,
        "sent": r["sent"],
        "received": r["received"],
        "lost": r["lost"],
        "pdr_percent": r["pdr_percent"],
        "mean_delay_ms": r["mean_delay_ms"],
        "total_energy_consumed_j":
            low_energy[scenario]["total_consumed_j"]
    })

    r = high[scenario]
    rows.append({
        "interval_s": "0.15",
        "scenario": scenario,
        "sent": r["sent"],
        "received": r["received"],
        "lost": r["lost"],
        "pdr_percent": r["pdr_percent"],
        "mean_delay_ms": r["mean_delay_ms"],
        "total_energy_consumed_j":
            r["total_energy_consumed_j"]
    })

headers = list(rows[0])

with (out / "combined_results.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)

lookup = {
    (r["interval_s"], r["scenario"]): r
    for r in rows
}

def make_graph(intervals, metric, ylabel, filename):
    x = list(range(len(intervals)))
    width = 0.36

    fig, ax = plt.subplots(figsize=(8, 5))

    for offset, scenario in (
        (-width / 2, "baseline"),
        ( width / 2, "preventive")
    ):
        values = [
            float(lookup[(i, scenario)][metric])
            for i in intervals
        ]
        positions = [p + offset for p in x]

        ax.bar(
            positions, values,
            width=width,
            label=scenario.capitalize()
        )

    ax.set_xticks(x)
    ax.set_xticklabels([i + " s" for i in intervals])
    ax.set_xlabel("Packet interval (lower = higher traffic)")
    ax.set_ylabel(ylabel)
    ax.set_title("250-Node NS2 Traffic Sensitivity")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout()
    fig.savefig(out / filename, dpi=200)
    plt.close(fig)

# All three traffic conditions
intervals = ["0.25", "0.20", "0.15"]

make_graph(
    intervals,
    "pdr_percent",
    "Packet Delivery Ratio (%)",
    "pdr_comparison.png"
)

make_graph(
    intervals,
    "mean_delay_ms",
    "Mean End-to-End Delay (ms)",
    "delay_comparison.png"
)

# Energy data available for 0.25 and 0.15 s only
make_graph(
    ["0.25", "0.15"],
    "total_energy_consumed_j",
    "Total Network Energy Consumed (J)",
    "energy_comparison.png"
)

print("COMBINED ANALYSIS COMPLETED")
print("Saved:", out / "combined_results.csv")
print("Saved: PDR, delay and energy graphs")
