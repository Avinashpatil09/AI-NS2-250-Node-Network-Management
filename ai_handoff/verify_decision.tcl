source "ai_handoff/decision_150.tcl"
if {$aiDecision ne "NO_ACTION" || $aiCandidate != -1} {
    error "Intervention not authorised"
}
puts "AI-NS2 HANDOFF VERIFIED"
puts "Decision: $aiDecision"
puts "Checkpoint: $aiCheckpoint s"
puts "Node shutdown: NONE"
exit 0
