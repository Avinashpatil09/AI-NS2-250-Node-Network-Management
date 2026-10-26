#!/usr/bin/env bash
# Usage: bash run_all.sh [node_count=25] [duration_seconds=35]
# For the full 250-node experiment: bash run_all.sh 250 250
set -euo pipefail
cd "$(dirname "$0")"
NODES="${1:-25}"
DURATION="${2:-35}"
mkdir -p results
command -v ns >/dev/null || { echo 'NS2 executable not found; install ns2 first.'; exit 1; }
python3 -c 'import pandas, sklearn, matplotlib, joblib' || { echo 'Activate .venv and install requirements.txt first.'; exit 1; }
rm -f results/preventive_actions.csv results/final_integrated_results.csv
printf '\n[1/8] NS-2: %s nodes, %s simulated seconds\n' "$NODES" "$DURATION"
ns simulation250.tcl "$NODES" "$DURATION"
printf '\n[2/8] Packet trace analysis\n'
python3 node_network_analysis.py
printf '\n[3/8] Machine-learning dataset\n'
python3 create_ml_dataset.py
printf '\n[4/8] Train Random Forest\n'
python3 train_model.py
printf '\n[5/8] Predict latest node risks\n'
python3 predict_nodes.py
printf '\n[6/8] Preventive decision illustration\n'
python3 preventive_simulation.py
printf '\n[7/8] Integrated results\n'
python3 integrate_results.py
printf '\n[8/8] Graph generation\n'
python3 generate_graphs.py
printf '\nDONE. See results/ for CSV, traces, NAM, model, graphs.\n'
printf 'To view NAM: TK_LIBRARY="$HOME/tk8.6-nam-fixed" nam results/network250.nam\n'
