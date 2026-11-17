"""Deterministic supervisor delegating to specialist workers.

All findings are mock data. No LLM, MCP server, or live infrastructure is used.
"""
from __future__ import annotations

from operator import add
from typing import Annotated, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command


AgentName = Literal["metrics_agent", "logs_agent", "infrastructure_agent"]


class Finding(TypedDict):
    specialist: str
    summary: str
    status: str


class SupervisorState(TypedDict):
    incident_id: str
    incident_type: str
    service: str
    remaining_agents: list[str]
    findings: Annotated[list[Finding], add]
    handoff_count: int
    max_handoffs: int
    route_reason: str
    report: str


ALLOWED_AGENTS = {
    "metrics_agent",
    "logs_agent",
    "infrastructure_agent",
}


def initial_plan(incident_type: str) -> list[str]:
    """A small deterministic plan used for teaching and repeatable tests."""
    plans = {
        "latency": ["metrics_agent", "logs_agent", "infrastructure_agent"],
        "errors": ["logs_agent", "metrics_agent"],
        "deployment": ["infrastructure_agent", "logs_agent", "metrics_agent"],
    }
    return list(plans.get(incident_type, ["logs_agent"]))


def supervisor(state: SupervisorState) -> Command[AgentName | Literal["finalize", "__end__"]]:
    remaining = list(state["remaining_agents"])
    count = state["handoff_count"]
    budget = state["max_handoffs"]

    if not remaining or count >= budget:
        reason = "No specialists remain or the handoff budget is exhausted."
        return Command(
            goto="finalize",
            update={"route_reason": reason},
        )

    # Validate the destination even though this demo's plan is generated locally.
    next_agent = remaining.pop(0)
    if next_agent not in ALLOWED_AGENTS:
        return Command(
            goto="finalize",
            update={"remaining_agents": [], "route_reason": "Rejected unknown specialist."},
        )

    return Command(
        goto=next_agent,
        update={
            "remaining_agents": remaining,
            "handoff_count": count + 1,
            "route_reason": f"Delegating to {next_agent} based on incident type {state['incident_type']}.",
        },
    )


def make_worker(name: str, summary: str):
    def worker(state: SupervisorState) -> dict:
        return {
            "findings": [{
                "specialist": name,
                "summary": summary.format(service=state["service"]),
                "status": "completed",
            }]
        }
    return worker


metrics_agent = make_worker(
    "metrics",
    "Observed elevated p95 latency and connection-pool pressure on {service}.",
)
logs_agent = make_worker(
    "logs",
    "Found repeated upstream timeout errors in {service}.",
)
infrastructure_agent = make_worker(
    "infrastructure",
    "Found a recent deployment for {service}; runtime health is currently stable.",
)


def finalize(state: SupervisorState) -> dict:
    findings = sorted(state["findings"], key=lambda item: item["specialist"])
    report_lines = [
        f"Incident {state['incident_id']} — {state['service']}",
        f"Delegations used: {state['handoff_count']}/{state['max_handoffs']}",
        "",
    ]
    if findings:
        report_lines.extend(
            f"- {item['specialist']} ({item['status']}): {item['summary']}"
            for item in findings
        )
    else:
        report_lines.append("- No specialist findings were collected.")
    report_lines.extend(["", f"Supervisor: {state['route_reason']}"])
    report_lines.append("Findings are evidence, not proof of root cause.")
    return {"report": "\n".join(report_lines)}


def build_graph():
    builder = StateGraph(SupervisorState)
    builder.add_node("supervisor", supervisor)
    builder.add_node("metrics_agent", metrics_agent)
    builder.add_node("logs_agent", logs_agent)
    builder.add_node("infrastructure_agent", infrastructure_agent)
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "supervisor")
    builder.add_edge("metrics_agent", "supervisor")
    builder.add_edge("logs_agent", "supervisor")
    builder.add_edge("infrastructure_agent", "supervisor")
    builder.add_edge("finalize", END)
    return builder.compile()


def run_incident(
    incident_id: str = "INC-280",
    incident_type: str = "latency",
    service: str = "payment-api",
    max_handoffs: int = 3,
) -> dict:
    if max_handoffs < 0:
        raise ValueError("max_handoffs must be non-negative")

    return build_graph().invoke({
        "incident_id": incident_id,
        "incident_type": incident_type,
        "service": service,
        "remaining_agents": initial_plan(incident_type),
        "findings": [],
        "handoff_count": 0,
        "max_handoffs": max_handoffs,
        "route_reason": "",
        "report": "",
    })


if __name__ == "__main__":
    result = run_incident()
    print(result["report"])
