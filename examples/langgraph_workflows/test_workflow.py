import unittest

from main import build_graph, collect_logs, collect_infrastructure


class LangGraphWorkflowTests(unittest.TestCase):
    def test_log_collector_returns_evidence(self):
        result = collect_logs({"service": "payment-api"})
        self.assertEqual(result["evidence"][0]["source"], "logs")
        self.assertIn("timeout", result["evidence"][0]["detail"])

    def test_infrastructure_collector_returns_evidence(self):
        result = collect_infrastructure({"service": "payment-api"})
        self.assertEqual(result["evidence"][0]["status"], "ok")

    def test_parallel_graph_joins_both_evidence_sources(self):
        graph = build_graph()
        result = graph.invoke(
            {
                "incident_id": "INC-TEST",
                "service": "payment-api",
                "severity": "high",
                "evidence": [],
            },
            config={"configurable": {"thread_id": "test-thread"}},
        )
        sources = {item["source"] for item in result["evidence"]}
        self.assertEqual(sources, {"logs", "infrastructure"})
        self.assertIn("2 evidence item(s)", result["summary"])


if __name__ == "__main__":
    unittest.main()
