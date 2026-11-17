from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


class Evidence(TypedDict):
    source: str
    status: str
    detail: str


class InvestigationState(TypedDict, total=False):
    incident_id: str
    service: str
    severity: str
    evidence: Annotated[list[Evidence], operator.add]
    summary: str


def collect_logs(state: InvestigationState) -> dict:
    """Mock a logs MCP tool call."""
    return {
        "evidence": [{
            "source": "logs",
            "status": "ok",
            "detail": f"{state['service']}: repeated upstream timeout errors",
        }]
    }


def collect_infrastructure(state: InvestigationState) -> dict:
    """Mock an infrastructure MCP tool call."""
    return {
        "evidence": [{
            "source": "infrastructure",
            "status": "ok",
            "detail": f"{state['service']}: deployment healthy; 3 replicas ready",
        }]
    }


def synthesize(state: InvestigationState) -> dict:
    evidence = state.get("evidence", [])
    lines = [f"- {item['source']} ({item['status']}): {item['detail']}" for item in evidence]
    summary = (
        f"Incident {state['incident_id']} for {state['service']} "
        f"has {len(evidence)} evidence item(s).\n" + "\n".join(lines)
    )
    return {"summary": summary}


def build_graph():
    builder = StateGraph(InvestigationState)
    builder.add_node("collect_logs", collect_logs)
    builder.add_node("collect_infrastructure", collect_infrastructure)
    builder.add_node("synthesize", synthesize)

    builder.add_edge(START, "collect_logs")
    builder.add_edge(START, "collect_infrastructure")
    # This join waits until both parallel collectors have completed.
    builder.add_edge(["collect_logs", "collect_infrastructure"], "synthesize")
    builder.add_edge("synthesize", END)

    # In-memory only: useful for learning, not durable production storage.
    return builder.compile(checkpointer=InMemorySaver())


if __name__ == "__main__":
    graph = build_graph()
    config = {"configurable": {"thread_id": "incident-2026-001"}}
    result = graph.invoke(
        {
            "incident_id": "INC-001",
            "service": "payment-api",
            "severity": "high",
            "evidence": [],
        },
        config=config,
    )
    print(result["summary"])
