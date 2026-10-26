#!/usr/bin/env python3
"""Find genuine NS-2 wireless routing-layer CBR forwarding activity.

Fast audit of a large, time-ordered, *new-format* NS-2 trace. Rather than
scanning the entire multi-gigabyte file, binary-search to the 140-150 s window.

Run from any directory:
    python fast_relay_audit.py

Reads (in same project directory as this program):
    results/network250.tr
    results/checkpoint_150_predictions.csv (optional)
Writes:
    results/active_forwarders_140_150.csv

This does not modify NS-2, change routes, or prove an alternative route.
"""
import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRACE = ROOT / "results" / "network250.tr"
RISK_CSV = ROOT / "results" / "checkpoint_150_predictions.csv"
OUTPUT = ROOT / "results" / "active_forwarders_140_150.csv"
START, END = 140.0, 150.0
TIME_RE = re.compile(rb"(?:^|\s)-t\s+([0-9]+(?:\.[0-9]+)?)")


def timestamp(line):
    match = TIME_RE.search(line)
    return float(match.group(1)) if match else None


def find_start(stream, target):
    """Binary search because NS-2 trace events are in time order."""
    stream.seek(0, 2)
    file_size = stream.tell()
    low, high = 0, file_size
    while high - low > 65536:
        middle = (low + high) // 2
        stream.seek(middle)
        stream.readline()                 # advance beyond a partial line
        line = stream.readline()
        t = timestamp(line)
        if t is None:
            high = middle
        elif t < target:
            low = stream.tell()
        else:
            high = middle
    stream.seek(max(0, low - 65536))
    if stream.tell():
        stream.readline()
    while True:
        pos = stream.tell()
        line = stream.readline()
        if not line:
            return pos
        t = timestamp(line)
        if t is not None and t >= target:
            stream.seek(pos)
            return pos


def parse_fields(parts):
    result = {}
    for i in range(1, len(parts)-1):
        if parts[i].startswith(b"-"):
            result[parts[i]] = parts[i+1]
    return result


def main():
    if not TRACE.is_file():
        raise SystemExit(f"Missing trace: {TRACE}")

    risk = {}
    if RISK_CSV.is_file():
        with RISK_CSV.open(newline="") as inp:
            for row in csv.DictReader(inp):
                risk[int(row["node_id"])] = row
    else:
        print("Risk snapshot not found: counts will be shown without predictions.")

    forwards = Counter()
    receives = Counter()
    sends = Counter()
    scanned = 0
    last_time = None
    with TRACE.open("rb") as stream:
        offset = find_start(stream, START)
        for line in stream:
            t = timestamp(line)
            if t is None or t < START:
                continue
            if t >= END:
                break
            scanned += 1
            last_time = t
            if not line or line[:1] not in (b"f", b"r", b"s"):
                continue
            parts = line.split()
            if not parts:
                continue
            fields = parse_fields(parts)
            if fields.get(b"-Nl") != b"RTR" or fields.get(b"-It", b"").lower() != b"cbr":
                continue
            try:
                node = int(fields[b"-Ni"])
            except (KeyError, ValueError):
                continue
            if parts[0] == b"f":
                forwards[node] += 1
            elif parts[0] == b"r":
                receives[node] += 1
            elif parts[0] == b"s":
                sends[node] += 1

    nodes = sorted(set(forwards) | set(receives) | set(sends) | {119, 136, 103, 137})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["node_id", "rtr_cbr_forwarded", "rtr_cbr_received", "rtr_cbr_sent", "risk_at_150", "energy_at_150_J"])
        for n in nodes:
            item = risk.get(n, {})
            writer.writerow([n, forwards[n], receives[n], sends[n], item.get("risk_level", ""), item.get("energy", "")])

    print(f"Time window: {START:g} to {END:g} simulated seconds")
    print(f"Fast scan started at byte offset: {offset:,}")
    print(f"Events checked in window: {scanned:,}; latest time checked: {last_time}")
    print(f"RTR CBR forwarding events: {sum(forwards.values()):,}")
    print("\nAI-selected nodes (source/destination/relay are different roles):")
    print(" Node | Risk   | RTR forwards | RTR receives | RTR sends")
    for n in (119, 136, 103, 137):
        status = risk.get(n, {}).get("risk_level", "unknown")
        print(f" {n:4} | {status:6} | {forwards[n]:12} | {receives[n]:12} | {sends[n]:9}")

    print("\nTop 12 *actual* RTR CBR forwarding nodes:")
    if not forwards:
        print(" No forwarding events detected in this window. Check trace configuration before claiming rerouting.")
    else:
        print(" Node | Forwarded | Risk at 150 s")
        for n, count in forwards.most_common(12):
            print(f" {n:4} | {count:9} | {risk.get(n, {}).get('risk_level', 'unknown')}")

    high_relays = [(n, c) for n, c in forwards.most_common() if risk.get(n, {}).get("risk_level") == "HIGH"]
    print("\nHIGH-risk nodes that actually forwarded during this window:", high_relays[:10] if high_relays else "none identified")
    print(f"\nSaved {OUTPUT}")
    print("NOTE: A forwarding count is not a complete hop-by-hop route. No routing change has been applied.")


if __name__ == "__main__":
    main()
