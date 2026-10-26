CONTROLLED EXPERIMENT: Node 158 interruption (NOT automatic AI rerouting)

Based on your 250-node AODV/CBR energy simulation.
Your earlier offline Random Forest classified Node 158 HIGH risk at 155s.
At 140–150s Node 158 forwarded 38 distinct CBR packets on flow 125 -> 143,
all observed delivered by 151s. Node 159 is a proposed lower-risk candidate,
not a verified replacement route.

The new Tcl file was derived from the supplied simulation250.tcl and preserves:
- 250 stationary grid nodes, AODV, 50 CBR streams and energy configuration
- Source 125 -> destination 143, configured flow f=25

The only experimental action is to turn Node 158 OFF at 155 simulated seconds
(or at 20s in a 40-second smoke test). Routing is still chosen by AODV.
There is NO forced routing through Node 159, no live ML feedback, and no
proof of improvement without comparing actual traces.

All intervention outputs are in results/preventive_158/.
Original simulation250.tcl and results/network250.tr are not modified.

Inside Ubuntu:
cd ~/AI_NS2_250_Node_Project
python3 -m zipfile -e '/mnt/c/Users/Avinash Patil/Downloads/Preventive_Node158_Experiment.zip' .
bash preventive_158/run.sh smoke
bash preventive_158/run.sh full
bash preventive_158/run.sh compare

IMPORTANT: run full only after smoke succeeds. The full NS2 test generates a
large trace and may take substantial compute/disk resources. Do not use the
smoke trace for before/after comparisons (comparison expects 200s run).

Files:
- route_intervention_158.tcl: cloned NS2 wireless experiment with scheduled off
- run.sh: smoke/full/compare commands; saves logs for debugging
- compare_route_158.py: reads only the 140–150 and 156–175-second windows of
  the original baseline and the new intervention trace, matches actual app-
  layer CBR packet IDs, calculates PDR, delay, packet traversals via 158/159
- comparison_125_143.csv: generated comparison inside results/preventive_158/

CAVEAT: Node 158 being switched off mimics removal from the network. This is a
controlled consequence test, NOT proof that the model acted on the network at
runtime. The node-off event may reduce deliveries or trigger new AODV routes;
report observed rather than assumed outcomes.
