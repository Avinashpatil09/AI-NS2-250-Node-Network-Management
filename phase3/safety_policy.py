"""Fail-closed policy; evaluates evidence, never operates on NS2."""

def evaluate_decision(predicted_positive_nodes, forwarding_counts,
                      rtr_cbr_events, unparsed_forward_records=0,
                      audit_complete=True):

    positive = {int(n) for n in predicted_positive_nodes}

    forwarding = {
        int(n): int(count)
        for n, count in forwarding_counts.items()
    }

    matched = sorted(
        n for n in positive
        if forwarding.get(n, 0) > 0
    )

    if (
        not audit_complete
        or rtr_cbr_events <= 0
        or unparsed_forward_records > 0
        or any(count < 0 for count in forwarding.values())
    ):
        decision = "INSUFFICIENT_EVIDENCE"

    elif not positive:
        decision = "NO_PREDICTED_LOW_ENERGY_NODES"

    elif matched:
        decision = "REVIEW_REQUIRED"

    else:
        decision = "NO_MATCH_IN_OBSERVED_WINDOW"

    return {
        "decision": decision,
        "matched_relays": matched,
        "action": "NO_ACTION",
        "automatic_shutdown": False,
    }
