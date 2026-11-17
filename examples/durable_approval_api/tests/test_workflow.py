from __future__ import annotations

import asyncio

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.workflow import build_graph, config


def test_graph_pauses_and_resumes_after_approval():
    calls = []

    async def executor(**proposal):
        calls.append(proposal)
        return {"executed": True, "mode": "test"}

    graph = build_graph(executor, InMemorySaver())
    thread = config("approval-thread-test-001")
    proposal = {
        "action": "restart_service",
        "service": "checkout-api",
        "environment": "staging",
        "reason": "Repeated health checks are failing.",
        "change_reference": "CHG-TEST-001",
    }

    async def scenario():
        paused = await graph.ainvoke({"proposal": proposal}, config=thread)
        assert paused.get("__interrupt__")
        assert calls == []

        result = await graph.ainvoke(
            Command(resume={
                "decision": "approve",
                "approver_id": "commander-b",
                "approver_role": "incident_commander",
            }),
            config=thread,
        )
        assert result["status"] == "completed"
        assert result["execution"]["executed"] is True
        assert len(calls) == 1

    asyncio.run(scenario())


def test_rejection_does_not_execute():
    calls = []

    async def executor(**proposal):
        calls.append(proposal)
        return {"executed": True}

    graph = build_graph(executor, InMemorySaver())
    thread = config("approval-thread-test-002")

    async def scenario():
        await graph.ainvoke(
            {"proposal": {
                "action": "restart_service",
                "service": "checkout-api",
                "environment": "staging",
                "reason": "Repeated health checks are failing.",
                "change_reference": "CHG-TEST-002",
            }},
            config=thread,
        )
        result = await graph.ainvoke(
            Command(resume={"decision": "reject"}),
            config=thread,
        )
        assert result["status"] == "rejected"
        assert result["execution"]["executed"] is False
        assert calls == []

    asyncio.run(scenario())
