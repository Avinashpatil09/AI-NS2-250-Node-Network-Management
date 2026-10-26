# AI-Driven Predictive Maintenance: reproducible NS-2.35 wireless experiment
# Usage: ns simulation250.tcl [number_of_nodes=250] [duration_seconds=250]
# Outputs: results/topology_jitter01_full/preventive/energy250.csv, results/topology_jitter01_full/preventive/network250.tr, results/topology_jitter01_full/preventive/network250.nam,
#          results/topology_jitter01_full/preventive/positions250.csv

set nn 250
set simTime 250.0
if {$argc >= 1} { set nn [lindex $argv 0] }
if {$argc >= 2} { set simTime [lindex $argv 1] }
if {![string is integer -strict $nn] || $nn < 8} { error "nodes must be an integer >= 8" }
if {![string is double -strict $simTime] || $simTime < 25} { error "duration must be >= 25 seconds" }

file mkdir results/preventive_158
set ns [new Simulator]
# Use the documented wireless trace format with named fields (-Nl, -Ni, -Ii, ...).
$ns use-newtrace
set tf [open "results/topology_jitter01_full/preventive/network250.tr" w]
$ns trace-all $tf
set nf [open "results/topology_jitter01_full/preventive/network250.nam" w]
$ns namtrace-all-wireless $nf 1200 1200
set ef [open "results/topology_jitter01_full/preventive/energy250.csv" w]
puts $ef "time,node_id,energy"
set pf [open "results/topology_jitter01_full/preventive/positions250.csv" w]
puts $pf "node_id,x,y"

set topo [new Topography]
$topo load_flatgrid 1200 1200
create-god $nn
set channel [new Channel/WirelessChannel]

# NS-2 EnergyModel: Joules = Watts x seconds. These are simulation assumptions,
# not measured device power requirements.
$ns node-config -adhocRouting AODV \
    -llType LL \
    -macType Mac/802_11 \
    -ifqType Queue/DropTail/PriQueue \
    -ifqLen 50 \
    -antType Antenna/OmniAntenna \
    -propType Propagation/TwoRayGround \
    -phyType Phy/WirelessPhy \
    -channel $channel \
    -topoInstance $topo \
    -agentTrace ON \
    -routerTrace ON \
    -macTrace OFF \
    -movementTrace OFF \
    -energyModel EnergyModel \
    -initialEnergy 100.0 \
    -txPower 0.43 \
    -rxPower 0.34 \
    -idlePower 0.222

set cols [expr {int(ceil(sqrt(double($nn))))}]
set spacing 65.0
for {set i 0} {$i < $nn} {incr i} {
    set node($i) [$ns node]
    $node($i) random-motion 0
    set x [expr {50.0 + ($i % $cols)*$spacing}]
    set y [expr {50.0 + int($i / $cols)*$spacing}]
    set x [expr {$x + ((($i * 37 + 11) % 41) - 20)}]
    set y [expr {$y + ((($i * 29 + 7) % 41) - 20)}]
    $node($i) set X_ $x
    $node($i) set Y_ $y
    $node($i) set Z_ 0.0
    $ns initial_node_pos $node($i) 12
    puts $pf "$i,$x,$y"
}
close $pf

# OFFLINE PREVENTIVE ROUTE TEST: the AI risk signal came from the already-run
# baseline simulation at t=155s. This does NOT implement live ML feedback.
# 40s smoke test uses a 20s failure to check ns-2's node-off command quickly.
if {$nn != 250} { error "Preventive trial requires exactly 250 nodes" }
set interventionTime 155.0
if {$simTime < 160.0} { set interventionTime 20.0 }
proc disable_node158 {} {
    global ns node
    puts "INTERVENTION: disabling node 158 at simulation time [$ns now] s"
    [$node(158) set netif_(0)] NodeOff
}
$ns at $interventionTime "disable_node158"

# Constant-Bit-Rate UDP streams make AODV discover routes and drain energy.
set flows [expr {int(ceil($nn / 5.0))}]
for {set f 0} {$f < $flows} {incr f} {
    set src [expr {($f*5) % $nn}]
    set dst [expr {($src + $cols + 2) % $nn}]
    if {$src == $dst} { set dst [expr {($src + 1) % $nn}] }
    set udp($f) [new Agent/UDP]
    $udp($f) set fid_ [expr {1 + ($f % 6)}]
    $ns attach-agent $node($src) $udp($f)
    set sink($f) [new Agent/Null]
    $ns attach-agent $node($dst) $sink($f)
    $ns connect $udp($f) $sink($f)
    set traffic($f) [new Application/Traffic/CBR]
    $traffic($f) set packetSize_ 512
    $traffic($f) set interval_ 0.20
    $traffic($f) set random_ false
    $traffic($f) attach-agent $udp($f)
    set start [expr {5.0 + 0.03 * $f}]
    set stop [expr {$simTime - 2.0}]
    if {$start < $stop} {
        $ns at $start "$traffic($f) start"
        $ns at $stop "$traffic($f) stop"
    }
}

proc record_energy {} {
    global ns node nn ef
    set now [$ns now]
    for {set i 0} {$i < $nn} {incr i} {
        # Do not synthesize energy; these values are read from NS-2's model.
        set joules [$node($i) energy]
        puts $ef [format "%.2f,%d,%.6f" $now $i $joules]
    }
}
for {set t 0.0} {$t < $simTime} {set t [expr {$t+5.0}]} {
    $ns at $t "record_energy"
}
proc finish {} {
    global ns tf nf ef nn simTime
    $ns flush-trace
    close $tf
    close $nf
    close $ef
    puts "PREVENTIVE NS2 completed: $nn nodes, $simTime seconds"
    puts "Saved results/topology_jitter01_full/preventive/energy250.csv, network250.tr, network250.nam, positions250.csv"
    exit 0
}
$ns at $simTime "finish"
$ns run
