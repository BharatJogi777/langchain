import unittest

from main import build_graph, route_after_evaluation, route_severity


class ConditionalRoutingTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph()

    def test_low_severity_skips_investigation(self):
        result = self.graph.invoke({
            "incident_id": "INC-LOW",
            "service": "catalog-api",
            "severity": "low",
            "attempt": 0,
            "max_attempts": 3,
            "target_confidence": 0.8,
            "confidence": 0.0,
            "evidence": [],
        })
        self.assertEqual(result["status"], "closed_without_deep_investigation")
        self.assertEqual(result.get("attempt", 0), 0)

    def test_high_severity_loops_until_threshold(self):
        result = self.graph.invoke({
            "incident_id": "INC-HIGH",
            "service": "payment-api",
            "severity": "high",
            "attempt": 0,
            "max_attempts": 3,
            "target_confidence": 0.8,
            "confidence": 0.0,
            "evidence": [],
        }, {"recursion_limit": 20})
        self.assertEqual(result["attempt"], 3)
        self.assertEqual(result["status"], "sufficient_evidence")
        self.assertEqual(len(result["evidence"]), 3)

    def test_max_attempts_stops_even_when_threshold_not_met(self):
        result = self.graph.invoke({
            "incident_id": "INC-LIMIT",
            "service": "orders-api",
            "severity": "medium",
            "attempt": 0,
            "max_attempts": 2,
            "target_confidence": 0.99,
            "confidence": 0.0,
            "evidence": [],
        }, {"recursion_limit": 20})
        self.assertEqual(result["attempt"], 2)
        self.assertEqual(result["status"], "needs_manual_review")

    def test_routing_functions(self):
        self.assertEqual(route_severity({"severity": "low"}), "close_low")
        self.assertEqual(route_severity({"severity": "critical"}), "collect_evidence")
        self.assertEqual(
            route_after_evaluation({"confidence": 0.9, "attempt": 1, "target_confidence": 0.8, "max_attempts": 3}),
            "finalize",
        )
        self.assertEqual(
            route_after_evaluation({"confidence": 0.2, "attempt": 3, "target_confidence": 0.8, "max_attempts": 3}),
            "finalize",
        )


if __name__ == "__main__":
    unittest.main()
