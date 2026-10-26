# AI-Driven Predictive & Preventive Maintenance for a 250-Node NS-2 Network

## What this is

A **reconstructed, runnable project starter** based on the user's earlier *AI_NS2_Project_In_Depth_File_Explanation.pdf*. The shared ChatGPT URL did not provide downloadable original source files. This is therefore **not a byte-for-byte copy** of those original scripts or results. It reproduces the documented architecture: **AODV wireless NS2 simulation → sampled node energy / packet trace → ML dataset → Random Forest → node risk levels → conceptual maintenance decisions → graphs**.

Uses NS2 2.35, Ubuntu 24.04 (WSL2), NAM 1.15, Python 3.

**Important scientific limitation:** `failure_risk` is a label built from **future simulated remaining energy below 45 J**, not an observed hardware failure. Predictive accuracy against this label does not establish accuracy against real hardware failures. `preventive_simulation.py` generates **suggested alternate nodes**; it does **not** change AODV routing or perform a second NS2 run. The simulation parameters here are reasoned replacements because the exact original source code was unavailable.

## Installation and launch (copy/paste one command at a time)

Run in the **Ubuntu terminal** (not Windows PowerShell). First extract `AI_NS2_250_Node_Project.zip` so this project folder is in your Ubuntu home directory.

```bash
cd ~/AI_NS2_250_Node_Project
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

If NS2 and NAM are already installed (as in the earlier chat), **do not reinstall them**.

### Stage A. Fast smoke test (25 nodes, 35 simulated seconds)

```bash
cd ~/AI_NS2_250_Node_Project
source .venv/bin/activate
bash run_all.sh 25 35
```

Expected: `NS2 completed: 25 nodes, 35 seconds`, then printed packet counts, ML dataset rows, model metrics and `DONE`. **A short 35-second test may not produce positive risk labels**, because all batteries can be above 45 J; that is expected and is reported in `model_metrics.json`.

Open animation (your NAM compatibility fix already proved to work):

```bash
TK_LIBRARY="$HOME/tk8.6-nam-fixed" nam results/network250.nam
```

Click Play and adjust the speed. An NS2 mobile-wireless topology shows nodes/traffic differently from your earlier two-node wired example; node animations may be busy at larger counts. A small test is recommended for NAM.

### Stage B. Full project (250 nodes, 250 simulated seconds)

```bash
cd ~/AI_NS2_250_Node_Project
source .venv/bin/activate
bash run_all.sh 250 250
```

The scripts overwrite `results/*` files with **new** measurements from your computer. Full-scale AODV traces may become large and full simulations can take substantial compute.

### Where to view results

```bash
ls -lh results
ls -lh results/graphs
cat results/network_summary.csv
cat results/model_metrics.json
```

Open the folder in Windows Explorer while inside Ubuntu:

```bash
explorer.exe .
```

## File-by-file explanations

| File | What it does | Main input → output |
|---|---|---|
| `simulation250.tcl` | Creates 250 static wireless nodes, AODV routing, CBR/UDP traffic, NS2 EnergyModel, tracks energy every 5 s | Parameters → `results/energy250.csv`, `network250.tr`, `network250.nam`, `positions250.csv` |
| `node_network_analysis.py` | Counts app-layer CBR sent/received packet IDs, computes packet loss and mean end-to-end delay | `network250.tr` → `node_network_analysis.csv`, `network_summary.csv` |
| `create_ml_dataset.py` | Computes energy decay and consumption; labels whether remaining energy goes below 45 J three samples (15 s) later | `energy250.csv` → `ml_dataset.csv` |
| `train_model.py` | Trains 200-tree Random Forest and evaluates against *held-out nodes* (not an independently validated physical failure set) | `ml_dataset.csv` → `failure_prediction_model.pkl`, `model_metrics.json` |
| `predict_nodes.py` | Estimates the probability of crossing the project's threshold using most recent measured energy state | energy CSV + model → `final_node_predictions.csv` |
| `preventive_simulation.py` | Suggests nearest lower-risk node for each high-risk node; **does not reroute simulated packets** | predictions + actual node coordinates → `preventive_actions.csv` |
| `integrate_results.py` | Joins node energy, predicted risk, packet statistics and suggested action | inputs above → `final_integrated_results.csv` |
| `generate_graphs.py` | Generates nine matplotlib PNG plots (energy, loss, delay, node scatter, risk) | CSV outputs → `graphs/*.png` |
| `energy_time_graph.py` | Standalone helper to replot only average energy over time | energy CSV → energy-versus-time PNG |
| `network_topology.py` | Standalone helper to replot NS2 node positions | positions CSV → node-position PNG |
| `run_all.sh` | Single orchestrator that runs all stages in order | node count and duration → all outputs |
| `requirements.txt` | Python package requirements | pip → Python virtual environment |

**Why the filenames say 250 during the smoke test:** They stay constant so the same downstream scripts work regardless of whether you run 25 or 250 nodes; the CSV rows reflect the **actual** node count used.

## Expected outputs / how to interpret them

- **`energy250.csv`**: columns `time,node_id,energy`. With exactly 250 nodes, 250 s, sampled every 5 s beginning at 0, this code records **50 × 250 = 12,500 data rows + header**.
- **`network250.tr`**: raw NS2 new-format wireless events. `-Nl AGT` and `-It cbr` identify the application-layer packets counted in the analyzer.
- **`network250.nam`**: display-oriented animation data; **not** a CSV dataset.
- **`node_network_analysis.csv`**: only source nodes that injected CBR packets. Other nodes will have zero in the final integrated table if they did not inject traffic; this does not mean they did no forwarding.
- **`ml_dataset.csv`**: with 250 nodes and 50 measurements each, three future rows per node are reserved for labels, giving **250 × 47 = 11,750 rows**.
- **`failure_prediction_model.pkl`**: serialized learned model; treat as executable code and only load files you trust.
- **`model_metrics.json`**: reported accuracy, train/test sample sizes, confusion matrix and a warning about simulated labels. Your numbers **will not necessarily equal** the old project's reported 99.83%.
- **`final_node_predictions.csv`**: exactly one prediction per simulated node, with predicted probabilities and LOW/MEDIUM/HIGH labels.
- **`preventive_actions.csv`**: decision-layer suggestions, not observed re-routing.
- **`final_integrated_results.csv`**: 1 row per node aggregating main metrics.
- **`results/graphs/`**: nine PNG graphs (e.g., `energy_vs_time.png`, `risk_distribution.png`).

## Main simulation assumptions / limitations

- Grid of static nodes; **not** a dynamic moving mesh.
- AODV route discovery with UDP/CBR traffic, 512-byte data packets, 0.2-s CBR interval, 50 flows at 250 nodes.
- `EnergyModel` uses 100 J initial energy, 0.43 W transmit, 0.34 W receive, 0.222 W idle; these are illustrative, not recovered original constants.
- Every 5 s energy sample begins at simulation time 0 and runs to 245 s in the full setup.
- Label: future energy **below 45 J** at +15 s; threshold **not** a physical node death criterion.
- Prediction LOW <0.35, MEDIUM 0.35–0.70, HIGH >=0.70; decision thresholds are configurable and not calibrated probabilities.
- Model testing holds out entire nodes, unlike naively shuffling many snapshots of the same nodes.
- Links on a plotted node-position map are **not** guaranteed AODV next-hop routes. The actual simulated network events are in `.tr` and NAM.
- Suggested "lower-risk alternative" does **not** guarantee a reachable end-to-end replacement AODV path.

## Troubleshooting

**NS2 says no CBR packets found:** Check that `results/network250.tr` contains AGT CBR events and that the simulation ran to completion. Inspect `head -n 12 results/network250.tr`. The parser expects NS2's **new wireless trace** format (`$ns use-newtrace`).

**NAM `wrong # args: should be "source fileName"`:** Use the previously working named compatibility directory `TK_LIBRARY="$HOME/tk8.6-nam-fixed" nam results/network250.nam`. Do not overwrite system Tcl/Tk files.

**Model reports one class (0 only):** The smoke test is too short for future energy to cross 45 J. The full duration is 250 s.

**Slow 250-node simulation:** Use the 25-node smoke test to verify environment and scripts before the larger experiment. NS2 runtime will differ by computer.

**No packets visible in NAM:** Click Play, slow the speed, zoom. The 250-node wireless view is crowded; test NAM using the 25-node run.

## Recommended sequence to study

1. Read `simulation250.tcl`: NS2 environment, nodes, traffic, energy, raw results.
2. View `energy250.csv` and `network250.tr` to understand what NS2 measured.
3. Run `node_network_analysis.py`: from individual events to packet summary.
4. Read `create_ml_dataset.py`: understand future-energy threshold **labels**.
5. Read `train_model.py`: distinguish simulated labels from physical failures.
6. Run `predict_nodes.py` and `preventive_simulation.py`: predictions vs actions.
7. Open nine graphs and final integrated CSV.

## Old vs newly computed measurements

Prior descriptive documentation reported 15,712 sent / 5,059 received, 11,750 ML samples, 99.83% test accuracy, and 205 HIGH / 1 MEDIUM / 44 LOW. These were **previous runs**, not values this package has reproduced or guaranteed. Use the generated CSV and JSON files for results from **your** new run.
