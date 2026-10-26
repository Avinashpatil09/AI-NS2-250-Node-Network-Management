#!/usr/bin/env bash
# Run inside your existing AI_NS2_250_Node_Project. NEVER overwrites baseline.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p results/preventive_158
case "${1:-}" in
 smoke)
   echo 'Quick compatibility check: 250 nodes for 40 simulated seconds; disable node 158 at 20 seconds'
   ns preventive_158/route_intervention_158.tcl 250 40 > results/preventive_158/smoke.log 2>&1 || { tail -n 25 results/preventive_158/smoke.log; exit 1; }
   tail -n 12 results/preventive_158/smoke.log
   echo 'SMOKE CHECK PASSED. Short trial output will be replaced by the full intervention run.'
   ;;
 full)
   echo 'Running original 250-node 50-flow experiment to 200 seconds with node 158 OFF at 155s.'
   echo 'Output under results/preventive_158/; baseline results/ stays unchanged.'
   ns preventive_158/route_intervention_158.tcl 250 200 > results/preventive_158/full.log 2>&1 || { tail -n 25 results/preventive_158/full.log; exit 1; }
   tail -n 15 results/preventive_158/full.log
   echo 'FULL INTERVENTION COMPLETED.'
   ;;
 compare)
   python3 preventive_158/compare_route_158.py
   ;;
 *) echo 'Usage: bash preventive_158/run.sh smoke | full | compare'; exit 2;;
esac
