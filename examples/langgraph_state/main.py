from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


class Evidence(TypedDict):
    evidence_id: str
    source: str
    detail: str


def merge_evidence(existing: list[Evidence], incoming: list[Evidence]) -> list[Evidence]:
    """Merge by stable evidence ID so repeated updates do not duplicate records."""
    by_id = {item["evidence_id"]: item for item in existing}
    for item in incoming:
        by_id[item["evidence_id"]] = item
    return list(by_id.values())


class InvestigationState(TypedDict, total=False):
    incident_id: str
    service: str
    evidence: Annotated[list[Evidence], merge_evidence]
    summary: str


def collect_logs(state: InvestigationState) -> dict:
    return {
        "evidence": [{
            "evidence_id": f"{state['incident_id']}:logs:001",
            "source": "logs",
            "detail": f"{state['service']} reports upstream timeouts",
        }]
    }


def collect_metrics(state: InvestigationState) -> dict:
    return {
        "evidence": [{
            "evidence_id": f"{state['incident_id']}:metrics:001",
            "source": "metrics",
            "detail": "CPU 82%; memory 68%",
        }]
    }


def collect_infrastructure(state: InvestigationState) -> dict:
    return {
        "evidence": [{
            "evidence_id": f"{state['incident_id']}:infra:001",
            "source": "infrastructure",
            "detail": "3 of 3 replicas are ready",
        }]
    }


def summarize(state: InvestigationState) -> dict:
    evidence = state.get("evidence", [])
    lines = [f"- {item['source']}: {item['detail']}" for item in evidence]
    return {"summary": f"Collected {len(evidence)} evidence item(s).\n" + "\n".join(lines)}


def build_graph():
    builder = StateGraph(InvestigationState)
    builder.add_node("collect_logs", collect_logs)
    builder.add_node("collect_metrics", collect_metrics)
    builder.add_node("collect_infrastructure", collect_infrastructure)
    builder.add_node("summarize", summarize)

    builder.add_edge(START, "collect_logs")
    builder.add_edge(START, "collect_metrics")
    builder.add_edge(START, "collect_infrastructure")
    builder.add_edge(
        ["collect_logs", "collect_metrics", "collect_infrastructure"],
        "summarize",
    )
    builder.add_edge("summarize", END)

    return builder.compile(checkpointer=InMemorySaver())


if __name__ == "__main__":
    graph = build_graph()
    config = {"configurable": {"thread_id": "incident-INC-100"}}
    output = graph.invoke(
        {
            "incident_id": "INC-100",
            "service": "payment-api",
            "evidence": [],
        },
        config=config,
    )

    print(output["summary"])

    # Inspect the latest checkpoint for this thread.
    snapshot = graph.get_state(config)
    print("\nCheckpoint thread:", snapshot.config["configurable"]["thread_id"])
    print("Checkpoint keys:", sorted(snapshot.values.keys()))

    # Inspect prior snapshots. This is debugging history, not a business audit log.
    print("History snapshots:", sum(1 for _ in graph.get_state_history(config)))
