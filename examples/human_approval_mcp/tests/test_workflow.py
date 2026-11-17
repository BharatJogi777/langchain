from __future__ import annotations

import asyncio

import pytest

from app.models import ActionProposal, ApprovalDecision
from app.workflow import build_approval_workflow, resume_approval, start_approval


def proposal(environment="staging", requested_by="operator-a"):
    return ActionProposal(
        request_id="incident-test-0001",
        requested_by=requested_by,
        action="restart_service",
        service="checkout-api",
        environment=environment,
        reason="Repeated health checks are failing.",
        change_reference="CHG-TEST-001",
    )


def approval(
    decision="approve",
    approver_id="commander-b",
    approver_role="incident_commander",
):
    return ApprovalDecision(
        decision=decision,
        approver_id=approver_id,
        approver_role=approver_role,
        comment="Reviewed incident evidence",
    )


def test_workflow_pauses_before_execution_and_executes_after_approval():
    calls = []

    async def executor(**kwargs):
        calls.append(kwargs)
        return {"executed": True, "mode": "test"}

    graph = build_approval_workflow(executor)
    initial = start_approval(graph, proposal())

    assert initial.get("__interrupt__")
    assert calls == []

    final = resume_approval(
        graph,
        request_id="incident-test-0001",
        decision=approval(),
    )
    assert final["status"] == "completed"
    assert final["execution"]["executed"] is True
    assert len(calls) == 1


def test_rejection_never_calls_executor():
    calls = []

    async def executor(**kwargs):
        calls.append(kwargs)
        return {"executed": True}

    graph = build_approval_workflow(executor)
    start_approval(graph, proposal())
    final = resume_approval(
        graph,
        request_id="incident-test-0001",
        decision=approval(decision="reject"),
    )

    assert final["status"] == "rejected"
    assert final["execution"]["executed"] is False
    assert calls == []


def test_requester_cannot_approve_own_action():
    async def executor(**kwargs):
        raise AssertionError("must not execute")

    graph = build_approval_workflow(executor)
    start_approval(graph, proposal(requested_by="same-person"))
    with pytest.raises(PermissionError):
        resume_approval(
            graph,
            request_id="incident-test-0001",
            decision=approval(approver_id="same-person"),
        )


def test_production_requires_incident_commander():
    async def executor(**kwargs):
        raise AssertionError("must not execute")

    graph = build_approval_workflow(executor)
    start_approval(graph, proposal(environment="production"))
    with pytest.raises(PermissionError):
        resume_approval(
            graph,
            request_id="incident-test-0001",
            decision=approval(approver_role="platform_admin"),
        )


def test_operator_role_cannot_approve():
    async def executor(**kwargs):
        raise AssertionError("must not execute")

    graph = build_approval_workflow(executor)
    start_approval(graph, proposal())
    with pytest.raises(PermissionError):
        resume_approval(
            graph,
            request_id="incident-test-0001",
            decision=approval(approver_role="operator"),
        )


def test_mock_executor_is_idempotent(tmp_path):
    from app.mock_executor import MockOperationsExecutor

    executor = MockOperationsExecutor(tmp_path / "ledger.sqlite3")
    args = {
        "action": "restart_service",
        "service": "checkout-api",
        "environment": "staging",
        "change_reference": "CHG-1",
        "idempotency_key": "stable-key-001",
    }
    first = asyncio.run(executor(**args))
    second = asyncio.run(executor(**args))
    assert first == second

    with pytest.raises(ValueError):
        asyncio.run(executor(**{**args, "service": "payments-api"}))
