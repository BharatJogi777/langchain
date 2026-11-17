"""LangGraph approval gate. Irreversible work happens only after interrupt resumes."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Awaitable, Callable, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.models import ActionProposal, ApprovalDecision, validate_approval

ActionExecutor = Callable[..., Awaitable[dict[str, Any]]]


class ApprovalState(TypedDict, total=False):
    proposal: dict[str, Any]
    idempotency_key: str
    approval: dict[str, Any]
    execution: dict[str, Any]
    status: str
    error: str


def stable_idempotency_key(proposal: ActionProposal) -> str:
    material = json.dumps(
        proposal.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def build_approval_workflow(
    action_executor: ActionExecutor,
    *,
    checkpointer=None,
):
    """Create a workflow that cannot execute until an external approval resumes it."""
    saver = checkpointer or InMemorySaver()

    def validate_proposal(state: ApprovalState):
        proposal = ActionProposal.model_validate(state["proposal"])
        return {
            "proposal": proposal.model_dump(mode="json"),
            "idempotency_key": stable_idempotency_key(proposal),
            "status": "awaiting_approval",
        }

    def approval_gate(state: ApprovalState):
        proposal = ActionProposal.model_validate(state["proposal"])
        approval_payload = {
            "kind": "human_approval_required",
            "request_id": proposal.request_id,
            "action": proposal.action,
            "service": proposal.service,
            "environment": proposal.environment,
            "reason": proposal.reason,
            "change_reference": proposal.change_reference,
            "requested_by": proposal.requested_by,
            "idempotency_key": state["idempotency_key"],
        }

        # interrupt() checkpoints and suspends the graph. On resume this node
        # starts again; all work above this line is pure/read-only.
        raw_decision = interrupt(approval_payload)
        decision = ApprovalDecision.model_validate(raw_decision)
        validate_approval(proposal, decision)
        return {
            "approval": decision.model_dump(mode="json"),
            "status": "approved" if decision.decision == "approve" else "rejected",
        }

    async def execute_approved_action(state: ApprovalState):
        if state.get("status") != "approved":
            return {"execution": {"executed": False, "reason": "not_approved"}}
        proposal = ActionProposal.model_validate(state["proposal"])
        result = await action_executor(
            action=proposal.action,
            service=proposal.service,
            environment=proposal.environment,
            change_reference=proposal.change_reference,
            idempotency_key=state["idempotency_key"],
        )
        return {"execution": result, "status": "completed"}

    def route_after_approval(state: ApprovalState) -> str:
        return "execute" if state.get("status") == "approved" else "finish"

    builder = StateGraph(ApprovalState)
    builder.add_node("validate_proposal", validate_proposal)
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("execute", execute_approved_action)
    builder.add_node("finish", lambda state: {})
    builder.add_edge(START, "validate_proposal")
    builder.add_edge("validate_proposal", "approval_gate")
    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {"execute": "execute", "finish": "finish"},
    )
    builder.add_edge("execute", END)
    builder.add_edge("finish", END)
    return builder.compile(checkpointer=saver)


def thread_config(request_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": request_id}}


async def start_approval(graph, proposal: ActionProposal):
    return await graph.ainvoke(
        {"proposal": proposal.model_dump(mode="json")},
        config=thread_config(proposal.request_id),
    )


async def resume_approval(
    graph,
    *,
    request_id: str,
    decision: ApprovalDecision,
):
    """Resume with a decision constructed by a trusted authenticated API layer."""
    return await graph.ainvoke(
        Command(resume=decision.model_dump(mode="json")),
        config=thread_config(request_id),
    )
