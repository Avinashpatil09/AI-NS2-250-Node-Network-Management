import unittest
from safety_policy import evaluate_decision


class SafetyPolicyTests(unittest.TestCase):

    def test_no_positive_nodes(self):
        result = evaluate_decision([], {}, 102)

        self.assertEqual(
            result["decision"],
            "NO_PREDICTED_LOW_ENERGY_NODES"
        )

        self.assertEqual(result["matched_relays"], [])
        self.assertEqual(result["action"], "NO_ACTION")

    def test_positive_active_relay_requires_review(self):
        result = evaluate_decision(
            [104, 118],
            {104: 5, 8: 2},
            102
        )

        self.assertEqual(
            result["decision"],
            "REVIEW_REQUIRED"
        )

        self.assertEqual(result["matched_relays"], [104])
        self.assertFalse(result["automatic_shutdown"])

    def test_positive_no_relay_match(self):
        result = evaluate_decision(
            [104],
            {8: 2},
            102
        )

        self.assertEqual(
            result["decision"],
            "NO_MATCH_IN_OBSERVED_WINDOW"
        )

        self.assertEqual(result["matched_relays"], [])

    def test_missing_routing_evidence(self):
        result = evaluate_decision(
            [104],
            {},
            0
        )

        self.assertEqual(
            result["decision"],
            "INSUFFICIENT_EVIDENCE"
        )

    def test_unparsed_forwarding_records(self):
        result = evaluate_decision(
            [104],
            {},
            102,
            unparsed_forward_records=1
        )

        self.assertEqual(
            result["decision"],
            "INSUFFICIENT_EVIDENCE"
        )

    def test_incomplete_audit(self):
        result = evaluate_decision(
            [104],
            {104: 2},
            102,
            audit_complete=False
        )

        self.assertEqual(
            result["decision"],
            "INSUFFICIENT_EVIDENCE"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
