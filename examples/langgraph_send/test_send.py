import unittest

from main import (
    MAX_SERVICES_PER_INVESTIGATION,
    build_graph,
    dispatch,
    investigate_service,
)


class SendFanOutTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_graph()

    def test_dispatch_creates_one_send_per_unique_service(self):
        sends = dispatch({
            "incident_id": "INC-1",
            "services": ["payments", "orders", "payments"],
        })
        self.assertEqual(len(sends), 2)
        self.assertEqual({item.arg["service"] for item in sends}, {"payments", "orders"})

    def test_empty_service_list_routes_to_summary(self):
        self.assertEqual(dispatch({"incident_id": "INC-EMPTY", "services": []}), "summarize")
        result = self.graph.invoke({
            "incident_id": "INC-EMPTY",
            "services": [],
            "results": [],
        })
        self.assertIn("no services", result["report"])

    def test_fan_out_limit_is_enforced(self):
        services = [f"service-{i}" for i in range(MAX_SERVICES_PER_INVESTIGATION + 1)]
        with self.assertRaises(ValueError):
            dispatch({"incident_id": "INC-LIMIT", "services": services})

    def test_blank_service_name_is_rejected(self):
        with self.assertRaises(ValueError):
            dispatch({"incident_id": "INC-BLANK", "services": ["  "]})

    def test_worker_returns_one_result(self):
        result = investigate_service({"incident_id": "INC-2", "service": "payment-api"})
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["status"], "ok")

    def test_graph_aggregates_dynamic_worker_results(self):
        result = self.graph.invoke({
            "incident_id": "INC-3",
            "services": ["payment-api", "orders-api", "catalog-api"],
            "results": [],
        }, {"max_concurrency": 3})
        self.assertEqual(len(result["results"]), 3)
        self.assertIn("investigated 3 service(s)", result["report"])
        self.assertEqual(
            [item["service"] for item in result["results"]],
            ["catalog-api", "orders-api", "payment-api"],
        )


if __name__ == "__main__":
    unittest.main()
