# LangGraph supervisor and handoff example

A deterministic supervisor delegates sequentially to metrics, logs, and infrastructure workers. Each worker returns to the supervisor, which either delegates again or finalizes.

## Run from repository root

```bash
python -m pip install -r examples/langgraph_supervisor/requirements.txt
python examples/langgraph_supervisor/main.py
python -m unittest discover -s examples/langgraph_supervisor -p "test_*.py" -v
```

No model, API key, MCP server, or live infrastructure is required. Worker findings are mock data.

## Concepts

- `Command(goto=...)` performs a state update and transfers control.
- Workers return to the supervisor through graph edges.
- The supervisor owns the delegation policy.
- A handoff budget guarantees termination.
- The destination allow-list constrains permitted workers.
- A reducer combines findings from successive worker runs.

This is an educational deterministic supervisor, not an LLM-powered router. Replace the planning policy with validated structured model output only after adding authorization, route validation, budgets, and tests.
