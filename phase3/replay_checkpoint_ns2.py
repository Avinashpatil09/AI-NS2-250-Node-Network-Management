"""Replay saved 250-node evidence through the NS2 event scheduler."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).absolute().parent.parent
sys.path.insert(0, str(ROOT))

from safety_policy import evaluate_decision


def worker(mode, destination):
    import joblib
    import pandas as pd
    from create_ml_dataset import features
    from train_model import FEATURES

    if mode not in {"recorded", "synthetic"}:
        raise SystemExit("Unknown replay mode")

    if destination.exists():
        raise SystemExit("Output already exists")

    base = ROOT / "results/topology_jitter01_full"

    # Only use energy available up to 150 seconds.
    energy = pd.read_csv(
        base / "baseline/energy250.csv"
    )

    energy = energy[energy.time <= 150].copy()
    energy = features(energy)

    current = energy[
        energy.time == 150
    ].sort_values("node_id").copy()

    if len(current) != 250:
        raise SystemExit("Expected 250 nodes")

    if current.node_id.nunique() != 250:
        raise SystemExit("Duplicate node IDs")

    # Load the original trained Random Forest.
    model = joblib.load(
        ROOT / "results/failure_prediction_model.pkl"
    )

    current["predicted"] = model.predict(
        current[FEATURES]
    ).astype(int)

    # Verify against the original saved predictions.
    saved = pd.read_csv(
        base / "frozen_model_checkpoint_150.csv"
    )

    comparison = current[
        ["node_id", "predicted"]
    ].merge(
        saved[["node_id", "predicted"]],
        on="node_id",
        suffixes=("_new", "_saved"),
        validate="one_to_one"
    )

    if len(comparison) != 250:
        raise SystemExit("Verification row mismatch")

    if not comparison.predicted_new.equals(
        comparison.predicted_saved
    ):
        raise SystemExit("Predictions do not match")

    positive = current.loc[
        current.predicted == 1,
        "node_id"
    ].astype(int).tolist()

    if not positive:
        raise SystemExit("No positive predictions")

    if mode == "recorded":

        # Real saved routing evidence.
        # Coverage is limited to selected nodes.
        audit = pd.read_csv(
            base / "ai_relay_audit_140_150.csv"
        )

        forwarding = dict(zip(
            audit.node_id.astype(int),
            audit.rtr_forward_events.astype(int)
        ))

        result = evaluate_decision(
            predicted_positive_nodes=positive,
            forwarding_counts=forwarding,
            rtr_cbr_events=int(
                audit.rtr_forward_events.sum()
            ),
            audit_complete=False
        )

        evidence = "REAL predictions; PARTIAL saved routing audit"

    else:

        # Deliberately simulated forwarding activity.
        # This is not an observed NS2 event.
        forwarding = {positive[0]: 5}

        result = evaluate_decision(
            predicted_positive_nodes=positive,
            forwarding_counts=forwarding,
            rtr_cbr_events=5,
            audit_complete=True
        )

        evidence = "REAL predictions; SYNTHETIC relay activity"

    report = {
        "mode": mode,
        "evidence": evidence,
        "checkpoint_s": 150,
        "nodes_evaluated": 250,
        "predicted_positive_nodes": positive,
        "matched_relays": result["matched_relays"],
        "decision": result["decision"],
        "action": result["action"],
        "automatic_shutdown": False
    }

    destination.write_text(
        json.dumps(report, indent=2) + "\n"
    )

    # Return only the safe action to NS2.
    print("NO_ACTION")


def run_replay():

    # Preserve the virtual environment's Python path.
    python_exe = ROOT / ".venv/bin/python"

    if not python_exe.is_file():
        raise SystemExit("Virtual environment missing")

    folder = Path(tempfile.mkdtemp(
        prefix="phase3-250-checkpoint-"
    ))

    worker_file = Path(__file__).absolute()

    # NS2 schedules two calls using saved evidence.
    tcl = f'''
set ns [new Simulator]

set py {{{python_exe}}}
set worker {{{worker_file}}}
set outdir {{{folder}}}

proc handoff {{mode}} {{
    global ns py worker outdir

    set output "$outdir/$mode.json"

    if {{[catch {{
        exec $py $worker --worker $mode $output
    }} answer]}} {{
        puts "REPLAY HANDOFF ERROR ($mode): $answer"
        exit 2
    }}

    if {{[string trim $answer] ne "NO_ACTION"}} {{
        puts "REPLAY UNEXPECTED ACTION: $answer"
        exit 3
    }}

    puts "REPLAY CHECKPOINT [$ns now] s ($mode): NO_ACTION"
}}

proc finish {{}} {{
    puts "REPLAY NS2 SCHEDULER COMPLETE"
    exit 0
}}

$ns at 150.1 "handoff recorded"
$ns at 150.2 "handoff synthetic"
$ns at 150.3 "finish"

$ns run
'''

    script = folder / "checkpoint_replay.tcl"
    script.write_text(tcl)

    print("\n===== RUNNING NS2 CHECKPOINT REPLAY =====")

    run = subprocess.run(
        ["ns", str(script)],
        cwd=folder,
        capture_output=True,
        text=True
    )

    print(run.stdout)

    if run.returncode != 0:
        print(run.stderr)
        raise SystemExit("NS2 checkpoint replay failed")

    if "REPLAY HANDOFF ERROR" in run.stdout:
        raise SystemExit("AI handoff error detected")

    print("===== VERIFYING SAFETY DECISIONS =====")

    cases = [
        ("recorded", "INSUFFICIENT_EVIDENCE"),
        ("synthetic", "REVIEW_REQUIRED")
    ]

    for mode, expected in cases:

        path = folder / f"{mode}.json"

        if not path.is_file():
            raise SystemExit(
                f"Missing report: {mode}"
            )

        report = json.loads(path.read_text())

        if report["decision"] != expected:
            raise SystemExit(
                f"Unexpected decision: {report}"
            )

        if report["action"] != "NO_ACTION":
            raise SystemExit("Unsafe action detected")

        if report["automatic_shutdown"]:
            raise SystemExit("Shutdown must remain disabled")

        print(f"\nScenario: {mode.upper()}")
        print("Nodes evaluated:", report["nodes_evaluated"])
        print(
            "Predicted low-energy nodes:",
            report["predicted_positive_nodes"]
        )
        print("Decision:", report["decision"])
        print("Action:", report["action"])
        print("Result: PASSED")

    print("\n====================================")
    print("250-NODE CHECKPOINT REPLAY: PASSED")
    print("No full wireless simulation was executed")
    print("No nodes were disabled")
    print("Original results unchanged")
    print("Temporary evidence:", folder)


if __name__ == "__main__":

    if (
        len(sys.argv) == 4
        and sys.argv[1] == "--worker"
    ):
        worker(
            sys.argv[2],
            Path(sys.argv[3])
        )
    else:
        run_replay()
