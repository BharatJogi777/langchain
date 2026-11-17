from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

MAX_SERVICES_PER_INVESTIGATION = 25


class ServiceResult(TypedDict):
    service: str
    status: str
    finding: str


class InvestigationState(TypedDict, total=False):
    incident_id: str
    services: list[str]
    results: Annotated[list[ServiceResult], operator.add]
    report: str


def dispatch(state: InvestigationState):
    """Create one worker invocation per validated service."""
    raw_services = state.get("services", [])
    if len(raw_services) > MAX_SERVICES_PER_INVESTIGATION:
        raise ValueError(
            f"Too many services: {len(raw_services)}; "
            f"maximum is {MAX_SERVICES_PER_INVESTIGATION}"
        )

    services = []
    seen = set()
    for raw_name in raw_services:
        name = raw_name.strip()
        if not name:
            raise ValueError("Service names cannot be empty")
        if name not in seen:
            seen.add(name)
            services.append(name)

    if not services:
        return "summarize"

    return [
        Send(
            "investigate_service",
            {
                "incident_id": state["incident_id"],
                "service": service,
            },
        )
        for service in services
    ]


def investigate_service(worker_state: dict) -> dict:
    """Mock one service investigation; replace with bounded MCP calls."""
    service = worker_state["service"]
    incident_id = worker_state["incident_id"]

    # Deterministic fixtures make the example and tests reproducible.
    observations = {
        "payment-api": ("ok", "upstream timeout errors observed"),
        "orders-api": ("ok", "request latency elevated"),
        "catalog-api": ("ok", "no abnormal error spike detected"),
    }
    status, finding = observations.get(
        service,
        ("unavailable", "no mock observation configured for this service"),
    )

    return {
        "results": [{
            "service": service,
            "status": status,
            "finding": f"{incident_id}: {finding}",
        }]
    }


def summarize(state: InvestigationState) -> dict:
    results = sorted(state.get("results", []), key=lambda item: item["service"])
    if not results:
        return {"report": f"Incident {state.get('incident_id', 'unknown')}: no services to investigate."}

    lines = [
        f"- {item['service']} [{item['status']}]: {item['finding']}"
        for item in results
    ]
    return {
        "report": (
            f"Incident {state['incident_id']}: investigated {len(results)} service(s).\n"
            + "\n".join(lines)
        )
    }


def build_graph():
    builder = StateGraph(InvestigationState)
    builder.add_node("investigate_service", investigate_service)
    builder.add_node("summarize", summarize)
    builder.add_conditional_edges(START, dispatch)
    # All dynamically dispatched worker runs join before summarization.
    builder.add_edge("investigate_service", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile()


if __name__ == "__main__":
    graph = build_graph()
    result = graph.invoke(
        {
            "incident_id": "INC-260",
            "services": ["payment-api", "orders-api", "catalog-api"],
            "results": [],
        },
        {"max_concurrency": 5},
    )
    print(result["report"])
