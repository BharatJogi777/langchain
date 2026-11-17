import unittest

from main import (
    build_graph,
    collect_logs,
    merge_evidence,
)


class StateAndReducerTests(unittest.TestCase):
    def test_merge_appends_distinct_evidence(self):
        existing = [{"evidence_id": "a", "source": "logs", "detail": "timeout"}]
        incoming = [{"evidence_id": "b", "source": "metrics", "detail": "cpu high"}]
        result = merge_evidence(existing, incoming)
        self.assertEqual({item["evidence_id"] for item in result}, {"a", "b"})

    def test_merge_is_idempotent_for_same_id(self):
        item = {"evidence_id": "a", "source": "logs", "detail": "timeout"}
        result = merge_evidence([item], [item])
        self.assertEqual(len(result), 1)

    def test_same_id_update_replaces_existing_record(self):
        old = {"evidence_id": "a", "source": "logs", "detail": "old"}
        new = {"evidence_id": "a", "source": "logs", "detail": "updated"}
        result = merge_evidence([old], [new])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["detail"], "updated")

    def test_collector_uses_stable_evidence_id(self):
        result = collect_logs({"incident_id": "INC-1", "service": "api"})
        self.assertEqual(result["evidence"][0]["evidence_id"], "INC-1:logs:001")

    def test_graph_collects_all_sources_and_checkpoints(self):
        graph = build_graph()
        config = {"configurable": {"thread_id": "unit-test-thread"}}
        result = graph.invoke(
            {"incident_id": "INC-2", "service": "orders", "evidence": []},
            config=config,
        )
        self.assertEqual(len(result["evidence"]), 3)
        snapshot = graph.get_state(config)
        self.assertEqual(len(snapshot.values["evidence"]), 3)
        self.assertEqual(snapshot.config["configurable"]["thread_id"], "unit-test-thread")
        self.assertTrue(any("Collected 3" in item for item in [result["summary"]]))


if __name__ == "__main__":
    unittest.main()
