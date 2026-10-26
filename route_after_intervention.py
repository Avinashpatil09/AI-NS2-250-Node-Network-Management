#!/usr/bin/env python3
"""Audit actual NS2 AODV CBR forwarders for 125 -> 143 after Node 158 shutdown.

Read-only analysis of existing baseline and intervention traces (156 <= t < 175s).
Uses the project's comparison utility to seek into large traces efficiently.
Creates a forwarding comparison CSV and two report-ready PNG charts; NEVER reruns NS2.
"""
from pathlib import Path
from collections import defaultdict
import csv
import sys

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT / "preventive_158"))
from compare_route_158 import skip_to, time_of, node_address

OUTDIR = PROJECT / "results" / "preventive_158"
BASE = PROJECT / "results" / "network250.tr"
TEST = OUTDIR / "network250.tr"
METRICS = OUTDIR / "comparison_125_143.csv"
START, END = 156.0, 175.0


def forwarding_by_node(trace):
    packets_by_node = defaultdict(set)
    with trace.open("rb") as stream:
        skip_to(stream, START)
        for raw in stream:
            t = time_of(raw)
            if t is None:
                continue
            if t >= END:
                break
            if not (START <= t < END and raw.startswith(b"f ")):
                continue
            parts = raw.split()
            values = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1)
                      if parts[i].startswith(b"-")}
            if values.get(b"-Nl") != b"RTR" or values.get(b"-It", b"").lower() != b"cbr":
                continue
            if node_address(values.get(b"-Is")) != 125 or node_address(values.get(b"-Id")) != 143:
                continue
            try:
                node = int(values[b"-Ni"])
                uid = int(values[b"-Ii"])
            except (KeyError, ValueError):
                continue
            packets_by_node[node].add(uid)
    return {node: len(uids) for node, uids in packets_by_node.items()}


def write_forwarders(base, test):
    output = OUTDIR / "forwarders_125_143_after.csv"
    with output.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["node_id", "baseline_unique_packet_forwards", "intervention_unique_packet_forwards", "difference"])
        for node in sorted(base.keys() | test.keys()):
            writer.writerow([node, base.get(node, 0), test.get(node, 0), test.get(node, 0) - base.get(node, 0)])
    print("\nTop CBR forwarding nodes, 125 -> 143, t=156–175 s:")
    print("Node | baseline | intervention")
    for node in sorted(base.keys() | test.keys(), key=lambda n: (-max(base.get(n, 0), test.get(n, 0)), n))[:15]:
        print(f"{node:>4} | {base.get(node, 0):>8} | {test.get(node, 0):>12}")
    print("Node 158:", base.get(158, 0), "baseline;", test.get(158, 0), "intervention")
    print("Node 159:", base.get(159, 0), "baseline;", test.get(159, 0), "intervention")
    print("Saved:", output)


def make_charts():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib unavailable; forwarding CSV was saved, but charts were skipped.")
        return
    with METRICS.open(newline="") as file:
        rows = [row for row in csv.DictReader(file) if row["window"] == "after"]
    baseline = next((r for r in rows if r["scenario"] == "baseline"), None)
    intervention = next((r for r in rows if r["scenario"] != "baseline"), None)
    if not baseline or not intervention:
        print("After-window metrics missing; charts skipped.")
        return
    scenarios = ["Baseline", "Node 158 disabled"]
    charts = [
        ("delivery_percent", "Packet delivery ratio (%)", "pdr_125_143_comparison.png", 100),
        ("mean_delay_ms", "Mean delivered-packet delay (ms)", "delay_125_143_comparison.png", None),
    ]
    for field, ylabel, filename, maximum in charts:
        values = [float(baseline[field]), float(intervention[field])]
        fig, ax = plt.subplots(figsize=(7, 4.5))
        bars = ax.bar(scenarios, values)
        ax.set_ylabel(ylabel)
        ax.set_title("Flow 125 → 143, simulated time 156–175 s")
        if maximum is not None:
            ax.set_ylim(0, maximum)
        else:
            ax.set_ylim(0, max(values) * 1.18)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, val + (2 if maximum else max(values)*0.03),
                    f"{val:.2f}", ha="center", va="bottom")
        fig.tight_layout()
        fig.savefig(OUTDIR / filename, dpi=180)
        plt.close(fig)
        print("Saved:", OUTDIR / filename)


def main():
    for path in (BASE, TEST, METRICS):
        if not path.is_file():
            raise SystemExit(f"Missing required file: {path}")
    print("Auditing observed relay events in the 156–175 s window; simulation is NOT rerun.")
    base = forwarding_by_node(BASE)
    test = forwarding_by_node(TEST)
    write_forwarders(base, test)
    make_charts()
    print("\nA forwarding node in this table is not, by itself, a fully reconstructed end-to-end route.")


if __name__ == "__main__":
    main()
