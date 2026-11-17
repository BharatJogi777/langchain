import asyncio

import pytest
from pydantic import ValidationError

from app.graph import RouteDecision, build_graph


class FakeRouteModel:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def with_structured_output(self, schema, method):
        assert schema is RouteDecision
        assert method == "json_schema"
        return self

    async def ainvoke(self, prompt):
        self.calls += 1
        value = self.outputs.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def route(agent="logs_agent"):
    return RouteDecision(
        next_agent=agent,
        reason="Collect evidence from the relevant subsystem.",
        task="Inspect evidence for the affected service",
    )


def make_executors(calls):
    async def executor(name):
        async def run(task, service, incident):
            calls.append((name, task, service, incident))
            return f"mock evidence from {name}"
        return run
    return {
        "logs_agent": lambda task, service, incident: _run(calls, "logs", task, service, incident),
        "metrics_agent": lambda task, service, incident: _run(calls, "metrics", task, service, incident),
        "infrastructure_agent": lambda task, service, incident: _run(calls, "infrastructure", task, service, incident),
    }


async def _run(calls, name, task, service, incident):
    calls.append((name, task, service, incident))
    return f"mock evidence from {name}"


def initial_state(**updates):
    state = {
        "incident": "Checkout requests time out",
        "service": "checkout-api",
        "findings": [],
        "visited_agents": [],
        "remaining_budget": 2,
    }
    state.update(updates)
    return state


def test_routes_to_scoped_specialist_then_finishes():
    calls = []
    model = FakeRouteModel([route("logs_agent"), route("finish")])
    graph = build_graph(model, make_executors(calls))
    result = asyncio.run(graph.ainvoke(initial_state(), config={"recursion_limit": 20}))
    assert [call[0] for call in calls] == ["logs"]
    assert result["visited_agents"] == ["logs_agent"]
    assert result["remaining_budget"] == 1
    assert "mock evidence from logs" in result["report"]


def test_budget_exhaustion_does_not_call_model():
    calls = []
    model = FakeRouteModel([route()])
    graph = build_graph(model, make_executors(calls))
    result = asyncio.run(graph.ainvoke(initial_state(remaining_budget=0)))
    assert model.calls == 0
    assert "budget exhausted" in result["report"]


def test_repeated_specialist_fails_closed():
    calls = []
    model = FakeRouteModel([route("logs_agent"), route("logs_agent")])
    graph = build_graph(model, make_executors(calls))
    result = asyncio.run(
        graph.ainvoke(
            initial_state(visited_agents=["logs_agent"]),
            config={"recursion_limit": 20},
        )
    )
    assert calls == []
    assert "routing failed safely" in result["report"]


def test_model_failure_retries_then_finalizes():
    calls = []
    model = FakeRouteModel([RuntimeError("offline"), RuntimeError("offline")])
    graph = build_graph(model, make_executors(calls))
    result = asyncio.run(graph.ainvoke(initial_state()))
    assert model.calls == 2
    assert "routing failed safely" in result["report"]


def test_missing_specialist_executor_rejected():
    with pytest.raises(ValueError, match="Missing specialist executors"):
        build_graph(FakeRouteModel([]), {"logs_agent": _run})
