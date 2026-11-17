from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class Evidence(TypedDict):
    source: str
    detail: str


class IncidentState(TypedDict, total=False):
    incident_id: str
    service: str
    severity: str
    attempt: int
    max_attempts: int
    confidence: float
    target_confidence: float
    evidence: Annotated[list[Evidence], operator.add]
    status: str
    summary: str


def classify(state: IncidentState) -> dict:
    severity = state["severity"].lower()
    if severity not in {"low", "medium", "high", "critical"}:
        raise ValueError(f"Unsupported severity: {severity}")
    return {"severity": severity}


def route_severity(state: IncidentState) -> Literal["close_low", "collect_evidence"]:
    if state["severity"] == "low":
        return "close_low"
    return "collect_evidence"


def close_low(state: IncidentState) -> dict:
    return {
        "status": "closed_without_deep_investigation",
        "summary": f"Incident {state['incident_id']} is low severity; deep investigation skipped.",
    }


def collect_evidence(state: IncidentState) -> dict:
    attempt = state.get("attempt", 0) + 1
    evidence = {
        1: {"source": "logs", "detail": "Intermittent upstream timeout observed"},
        2: {"source": "metrics", "detail": "CPU utilization elevated to 82 percent"},
        3: {"source": "infrastructure", "detail": "All replicas ready; no restart loop"},
    }.get(attempt, {"source": "unknown", "detail": "No additional mock evidence"})

    return {"attempt": attempt, "evidence": [evidence]}


def evaluate(state: IncidentState) -> dict:
    # Deterministic teaching fixture, not a real confidence model.
    confidence_by_attempt = {1: 0.35, 2: 0.65, 3: 0.90}
    return {"confidence": confidence_by_attempt.get(state["attempt"], 0.0)}


def route_after_evaluation(
    state: IncidentState,
) -> Literal["collect_evidence", "finalize"]:
    enough = state["confidence"] >= state.get("target_confidence", 0.80)
    exhausted = state["attempt"] >= state.get("max_attempts", 3)
    if enough or exhausted:
        return "finalize"
    return "collect_evidence"


def finalize(state: IncidentState) -> dict:
    evidence = state.get("evidence", [])
    status = "sufficient_evidence" if state["confidence"] >= state.get("target_confidence", 0.80) else "needs_manual_review"
    lines = [f"- {item['source']}: {item['detail']}" for item in evidence]
    return {
        "status": status,
        "summary": (
            f"Incident {state['incident_id']} for {state['service']}: "
            f"{len(evidence)} evidence item(s), confidence={state['confidence']:.2f}.\n"
            + "\n".join(lines)
        ),
    }


def build_graph():
    builder = StateGraph(IncidentState)
    builder.add_node("classify", classify)
    builder.add_node("close_low", close_low)
    builder.add_node("collect_evidence", collect_evidence)
    builder.add_node("evaluate", evaluate)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        route_severity,
        {
            "close_low": "close_low",
            "collect_evidence": "collect_evidence",
        },
    )
    builder.add_edge("close_low", END)
    builder.add_edge("collect_evidence", "evaluate")
    builder.add_conditional_edges(
        "evaluate",
        route_after_evaluation,
        {
            "collect_evidence": "collect_evidence",
            "finalize": "finalize",
        },
    )
    builder.add_edge("finalize", END)
    return builder.compile()


if __name__ == "__main__":
    graph = build_graph()
    result = graph.invoke(
        {
            "incident_id": "INC-250",
            "service": "payment-api",
            "severity": "high",
            "attempt": 0,
            "max_attempts": 3,
            "target_confidence": 0.80,
            "confidence": 0.0,
            "evidence": [],
        },
        {"recursion_limit": 20},
    )
    print("Status:", result["status"])
    print(result["summary"])
