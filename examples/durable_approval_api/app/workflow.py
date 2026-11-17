from __future__ import annotations

from typing import Any, Awaitable, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

ActionExecutor = Callable[..., Awaitable[dict[str, Any]]]


class State(TypedDict, total=False):
    proposal: dict[str, Any]
    decision: dict[str, Any]
    execution: dict[str, Any]
    status: str


def build_graph(executor: ActionExecutor, checkpointer):
    def approval_gate(state: State):
        proposal = state["proposal"]
        decision = interrupt({
            "kind": "approval_required",
            "action": proposal["action"],
            "service": proposal["service"],
            "environment": proposal["environment"],
            "reason": proposal["reason"],
            "change_reference": proposal["change_reference"],
        })
        if decision["decision"] == "reject":
            return {"decision": decision, "status": "rejected"}
        return {"decision": decision, "status": "approved"}

    async def execute(state: State):
        proposal = state["proposal"]
        # The API validates the stored proposal, reviewer identity, role,
        # expiry and decision before it resumes this graph.
        result = await executor(**proposal)
        return {"execution": result, "status": "completed"}

    def route(state: State):
        return "execute" if state["status"] == "approved" else "finish"

    builder = StateGraph(State)
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("execute", execute)
    builder.add_node("finish", lambda state: {"execution": {"executed": False}})
    builder.add_edge(START, "approval_gate")
    builder.add_conditional_edges("approval_gate", route, {"execute": "execute", "finish": "finish"})
    builder.add_edge("execute", END)
    builder.add_edge("finish", END)
    return builder.compile(checkpointer=checkpointer)


def config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}
