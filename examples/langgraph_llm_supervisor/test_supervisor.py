from pydantic import ValidationError
import pytest

from main import RouteDecision, _policy_check, build_graph


class FakeStructuredModel:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def with_structured_output(self, schema, method):
        assert schema is RouteDecision
        assert method == "json_schema"
        return self

    def invoke(self, prompt):
        self.calls += 1
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def decision(agent="logs_agent", task="Inspect correlated application errors"):
    return RouteDecision(
        next_agent=agent,
        reason="The incident description suggests this evidence is useful.",
        task=task,
        confidence=0.8,
    )


def initial_state(**overrides):
    state = {
        "incident": "Checkout requests time out",
        "findings": [],
        "visited_agents": [],
        "remaining_budget": 2,
    }
    state.update(overrides)
    return state


def test_valid_decision_delegates_and_returns_to_supervisor():
    model = FakeStructuredModel([decision(), decision("finish", "Summarize findings")])
    graph = build_graph(model)
    result = graph.invoke(initial_state(), config={"recursion_limit": 20})
    assert result["visited_agents"] == ["logs_agent"]
    assert result["remaining_budget"] == 1
    assert any("logs_agent" in item for item in result["findings"])
    assert "Incident investigation summary" in result["report"]


def test_finish_decision_does_not_call_specialist():
    model = FakeStructuredModel([decision("finish", "Summarize")])
    result = build_graph(model).invoke(initial_state())
    assert result["visited_agents"] == []
    assert result["findings"] == []
    assert "No specialist findings" in result["report"]


def test_repeated_specialist_is_rejected_and_fails_closed():
    model = FakeStructuredModel([decision("logs_agent"), decision("logs_agent")])
    result = build_graph(model).invoke(
        initial_state(visited_agents=["logs_agent"], remaining_budget=2)
    )
    assert result["visited_agents"] == ["logs_agent"]
    assert "routing failed safely" in result["fallback_reason"]


def test_budget_exhaustion_skips_model():
    model = FakeStructuredModel([decision()])
    result = build_graph(model).invoke(initial_state(remaining_budget=0))
    assert model.calls == 0
    assert result["proposed_route"] == "finalize"


def test_model_failure_retries_then_fails_closed():
    model = FakeStructuredModel([RuntimeError("offline"), RuntimeError("offline")])
    result = build_graph(model).invoke(initial_state())
    assert model.calls == 2
    assert result["proposed_route"] == "finalize"
    assert "routing failed safely" in result["fallback_reason"]


def test_policy_rejects_long_task():
    with pytest.raises(ValidationError):
        decision(task="x" * 501)


def test_policy_rejects_repeated_destination():
    with pytest.raises(ValueError, match="already been visited"):
        _policy_check(decision(), initial_state(visited_agents=["logs_agent"]))


def test_policy_rejects_arbitrary_destination_at_schema_boundary():
    with pytest.raises(ValidationError):
        RouteDecision(
            next_agent="delete_production_database",
            reason="unsafe",
            task="Delete",
            confidence=1.0,
        )
