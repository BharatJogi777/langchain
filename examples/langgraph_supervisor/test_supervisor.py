import unittest

from main import ALLOWED_AGENTS, initial_plan, run_incident


class SupervisorTests(unittest.TestCase):
    def test_latency_plan_uses_three_specialists(self):
        result = run_incident(incident_type="latency")
        names = {item["specialist"] for item in result["findings"]}
        self.assertEqual(names, {"metrics", "logs", "infrastructure"})
        self.assertEqual(result["handoff_count"], 3)

    def test_error_plan_uses_two_specialists(self):
        result = run_incident(incident_type="errors")
        names = {item["specialist"] for item in result["findings"]}
        self.assertEqual(names, {"logs", "metrics"})
        self.assertEqual(result["handoff_count"], 2)

    def test_handoff_budget_stops_delegation(self):
        result = run_incident(incident_type="latency", max_handoffs=1)
        self.assertEqual(result["handoff_count"], 1)
        self.assertEqual(len(result["findings"]), 1)

    def test_zero_budget_finishes_without_workers(self):
        result = run_incident(incident_type="latency", max_handoffs=0)
        self.assertEqual(result["handoff_count"], 0)
        self.assertEqual(result["findings"], [])
        self.assertIn("budget is exhausted", result["report"])

    def test_unknown_incident_type_uses_safe_default(self):
        self.assertEqual(initial_plan("unknown"), ["logs_agent"])

    def test_destination_allow_list_is_explicit(self):
        self.assertEqual(
            ALLOWED_AGENTS,
            {"metrics_agent", "logs_agent", "infrastructure_agent"},
        )

    def test_negative_budget_is_rejected(self):
        with self.assertRaises(ValueError):
            run_incident(max_handoffs=-1)


if __name__ == "__main__":
    unittest.main()
