import unittest

from main import (
    build_graph,
    build_specialist,
    logs_subgraph,
)


class SubgraphTests(unittest.TestCase):
    def test_specialist_graph_returns_finding(self):
        result = logs_subgraph.invoke({
            "incident_id": "INC-1",
            "services": ["payment-api"],
            "evidence": [],
            "private_notes": [],
        })
        self.assertIn("payment-api", result["finding"])
        self.assertTrue(result["private_notes"])

    def test_specialist_private_state_is_not_parent_output(self):
        graph = build_graph()
        result = graph.invoke({
            "incident_id": "INC-2",
            "services": ["orders-api"],
            "findings": [],
        })
        self.assertEqual(len(result["findings"]), 3)
        self.assertNotIn("private_notes", result)

    def test_parent_runs_all_specialists(self):
        graph = build_graph()
        result = graph.invoke({
            "incident_id": "INC-3",
            "services": ["payment-api", "catalog-api"],
            "findings": [],
        })
        names = {item["specialist"] for item in result["findings"]}
        self.assertEqual(names, {"Logs", "Metrics", "Infrastructure"})
        self.assertIn("Incident INC-3", result["report"])

    def test_specialist_can_handle_empty_services(self):
        specialist = build_specialist("Test", "checked {service}")
        result = specialist.invoke({
            "incident_id": "INC-4",
            "services": [],
            "evidence": [],
            "private_notes": [],
        })
        self.assertIn("no evidence available", result["finding"])


if __name__ == "__main__":
    unittest.main()
