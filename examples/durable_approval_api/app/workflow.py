from __future__ import annotations

import hashlib
import json
from typing import Any, Awaitable, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

ActionExecutor = Callable[..., Awaitable[dict[str, Any]]]


class State(TypedDict, total=False):
    proposal: dict[str, Any]
    idempotency_key: str
    decision: dict[str, Any]
    execution: dict[str, Any]
    status: str


def build_graph(executor: ActionExecutor, checkpointer):
    def validate_proposal(state: State):
        encoded = json.dumps(state["proposal"], sort_keys=True, separators=(",", ":"))
        key = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return {"idempotency_key": key}

    def approval_gate(state: State):
        proposal = state["proposal"]
        decision = interrupt({
            "kind": "approval_required",
            "action": proposal["action"],
            "service": proposal["service"],
            "environment": proposal["environment"],
            "reason": proposal["reason"],
            "change_reference": proposal["change_reference"],
            "idempotency_key": state["idempotency_key"],
        })
        if decision["decision"] == "reject":
            return {"decision": decision, "status": "rejected"}
        return {"decision": decision, "status": "approved"}

    async def execute(state: State):
        proposal = {
            **state["proposal"],
            "idempotency_key": state["idempotency_key"],
        }
        # The API validates the stored proposal, reviewer identity, role,
        # expiry and decision before it resumes this graph.
        result = await executor(**proposal)
        return {"execution": result, "status": "completed"}

    def route(state: State):
        return "execute" if state["status"] == "approved" else "finish"

    builder = StateGraph(State)
    builder.add_node("validate_proposal", validate_proposal)
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("execute", execute)
    builder.add_node("finish", lambda state: {"execution": {"executed": False}})
    builder.add_edge(START, "validate_proposal")
    builder.add_edge("validate_proposal", "approval_gate")
    builder.add_conditional_edges("approval_gate", route, {"execute": "execute", "finish": "finish"})
    builder.add_edge("execute", END)
    builder.add_edge("finish", END)
    return builder.compile(checkpointer=checkpointer)


def config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}
