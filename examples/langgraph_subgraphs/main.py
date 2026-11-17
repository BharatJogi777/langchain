from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph


class SpecialistState(TypedDict, total=False):
    """Private state contract for one specialist workflow."""
    incident_id: str
    services: list[str]
    evidence: list[str]
    private_notes: list[str]
    finding: str


class ParentState(TypedDict, total=False):
    """Shared state contract for the overall investigation."""
    incident_id: str
    services: list[str]
    findings: Annotated[list[dict[str, str]], operator.add]
    report: str


def build_specialist(name: str, evidence_template: str):
    """Build a self-contained child graph for a specialist."""

    def inspect(state: SpecialistState) -> dict:
        services = state.get("services", [])
        evidence = [
            evidence_template.format(service=service)
            for service in services
        ]
        return {
            "evidence": evidence,
            "private_notes": [f"{name} checked {len(services)} service(s)."],
        }

    def conclude(state: SpecialistState) -> dict:
        evidence = state.get("evidence", [])
        finding = (
            f"{name}: " + ("; ".join(evidence) if evidence else "no evidence available")
        )
        return {"finding": finding}

    builder = StateGraph(SpecialistState)
    builder.add_node("inspect", inspect)
    builder.add_node("conclude", conclude)
    builder.add_edge(START, "inspect")
    builder.add_edge("inspect", "conclude")
    builder.add_edge("conclude", END)
    return builder.compile()


logs_subgraph = build_specialist(
    "Logs specialist",
    "log review for {service}: elevated timeout errors",
)
metrics_subgraph = build_specialist(
    "Metrics specialist",
    "metrics review for {service}: latency above baseline",
)
infra_subgraph = build_specialist(
    "Infrastructure specialist",
    "infrastructure review for {service}: deployment status healthy",
)


def make_parent_node(specialist_graph, specialist_name: str):
    """Adapt parent state to child state and child output back to parent."""
    def run_specialist(state: ParentState) -> dict:
        child_result = specialist_graph.invoke({
            "incident_id": state["incident_id"],
            "services": state.get("services", []),
            "evidence": [],
            "private_notes": [],
        })
        return {
            "findings": [{
                "specialist": specialist_name,
                "finding": child_result["finding"],
            }]
        }
    return run_specialist


def synthesize(state: ParentState) -> dict:
    findings = sorted(
        state.get("findings", []),
        key=lambda item: item["specialist"],
    )
    if not findings:
        return {"report": f"Incident {state['incident_id']}: no specialist findings."}

    sections = [
        f"- {item['specialist']}: {item['finding']}"
        for item in findings
    ]
    return {
        "report": (
            f"Incident {state['incident_id']} — specialist summary\n"
            + "\n".join(sections)
        )
    }


def build_graph():
    builder = StateGraph(ParentState)
    builder.add_node("logs_agent", make_parent_node(logs_subgraph, "Logs"))
    builder.add_node("metrics_agent", make_parent_node(metrics_subgraph, "Metrics"))
    builder.add_node("infra_agent", make_parent_node(infra_subgraph, "Infrastructure"))
    builder.add_node("synthesize", synthesize)

    # All specialist nodes are triggered together and run in parallel.
    builder.add_edge(START, "logs_agent")
    builder.add_edge(START, "metrics_agent")
    builder.add_edge(START, "infra_agent")

    # A list of source nodes creates a join: synthesis waits for all specialists.
    builder.add_edge(["logs_agent", "metrics_agent", "infra_agent"], "synthesize")
    builder.add_edge("synthesize", END)
    return builder.compile()


if __name__ == "__main__":
    graph = build_graph()
    result = graph.invoke({
        "incident_id": "INC-270",
        "services": ["payment-api", "orders-api"],
        "findings": [],
    })
    print(result["report"])
