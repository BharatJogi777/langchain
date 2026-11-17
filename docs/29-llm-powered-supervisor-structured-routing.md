# Lesson 29 — LLM-Powered Supervisor with Structured Routing

## 1. What changes from Lesson 28?

Lesson 28 used deterministic Python logic to select a specialist. That is predictable, but a real incident may require interpreting unstructured symptoms:

> Checkout requests are timing out. CPU is normal, but the database connection pool is exhausted. The issue started after the latest deployment.

An LLM can interpret the incident and propose that the database/logs specialist should investigate first. The LLM must not control the workflow directly.

**Production boundary:** the model proposes a typed decision; Pydantic validates its shape; trusted Python validates the destination, budget, repetition, and task; LangGraph performs the handoff.

## 2. Architecture

```text
Incident
   |
   v
Supervisor node
   |  ChatOllama + Pydantic schema
   v
RouteDecision
   |  trusted Python validation
   +----> logs_agent --------+
   +----> metrics_agent -----+--> supervisor
   +----> infrastructure ---+
   +----> finalize
```

Workers are deliberately deterministic mock investigators in this lesson. The focus is routing, not connecting real monitoring systems. Later lessons can replace their internals with secured MCP clients.

## 3. Structured route schema

The model returns exactly these fields:

- `next_agent`: one of three allow-listed specialists or `finish`.
- `reason`: concise explanation for the proposed route.
- `task`: bounded task description for the specialist.
- `confidence`: model's self-reported confidence (informational only).

Pydantic validates the data type and basic constraints. The Python supervisor separately checks runtime policy. Confidence is not an authorization signal and must not be used as proof that a route is safe.

## 4. Why not let the LLM return arbitrary graph node names?

Never do this:

```python
decision = model.invoke(prompt)
return Command(goto=decision.next_agent)  # unsafe
```

The model could return a node that was never intended to be reachable. Instead, use a fixed mapping in application code and validate the proposed destination before constructing `Command`.

## 5. Install and run

Requirements are pinned to compatible package ranges in `examples/langgraph_llm_supervisor/requirements.txt`.

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r examples/langgraph_llm_supervisor/requirements.txt
ollama pull llama3.2:3b
python examples/langgraph_llm_supervisor/main.py
```

Ollama must be running locally. The default model is `llama3.2:3b`; override it with `OLLAMA_MODEL`.

Run deterministic tests without calling Ollama:

```bash
pytest -q examples/langgraph_llm_supervisor/test_supervisor.py
```

## 6. The core implementation

Open `examples/langgraph_llm_supervisor/main.py`. The important pieces are:

1. `RouteDecision`: the Pydantic contract.
2. `build_graph(model)`: dependency injection lets tests supply a fake model.
3. `supervisor_node`: invokes structured output, retries a failed model response once, validates the route, then returns a LangGraph `Command`.
4. Specialist nodes: append bounded findings and return to the supervisor.
5. `finalize`: creates a report from collected findings.

The example uses `ChatOllama.with_structured_output(RouteDecision, method="json_schema")`. The current Ollama integration documents `json_schema`, `json_mode`, and `function_calling` methods. If your installed provider/model combination does not support the selected method, check the installed integration version and try `method="json_mode"` with explicit JSON instructions. Do not silently treat arbitrary text as a valid route.

## 7. Runtime safety controls

The example enforces these controls:

- **Allow-list:** only `logs_agent`, `metrics_agent`, and `infrastructure_agent` are valid specialist destinations.
- **Budget:** each successful delegation consumes one unit. When the budget is exhausted, the graph finalizes.
- **No duplicate specialist:** a specialist cannot be dispatched twice in the same investigation. A production workflow may instead track attempts per specialist and allow a carefully bounded retry.
- **Task length:** task text is length-limited before it reaches a worker.
- **Safe failure:** model exceptions, malformed output, and policy-invalid decisions end in a safe finalization path. The system does not guess a destination.
- **No model authorization:** the model cannot approve deployments, execute shell commands, change access policy, or select arbitrary MCP tools.

The example's mock workers do not perform external side effects. Before replacing them with real tools, add authentication, tenant scoping, resource allow-lists, timeouts, audit records, idempotency, and human approval for consequential actions.

## 8. Structured output is not truth

A valid Pydantic object only proves that the response conforms to a schema. It does not prove that the chosen specialist is correct, that the incident facts are true, or that the task is safe. Treat model output as untrusted input even after parsing.

## 9. Testing strategy

The unit tests inject a fake structured model. This gives deterministic tests for:
- valid specialist delegation and return to supervisor;
- finish decisions;
- repeated-agent rejection;
- budget exhaustion;
- model failure fallback;
- invalid task length / policy checks.

Keep model integration tests separate from deterministic unit tests. A live Ollama test is useful as a manual smoke test, but should not make every unit-test run dependent on a locally running model.

## 10. Production improvements

Before production use, add:

1. Schema/version compatibility tests for the exact Ollama model tag.
2. Structured logs for decision ID, proposed route, validated route, latency, and fallback reason. Avoid logging secrets or full sensitive incident payloads.
3. Tracing across supervisor and specialist nodes.
4. Per-tenant budgets and deadlines.
5. A specialist-specific retry policy with idempotency.
6. Human approval gates before operational changes.
7. Evaluation datasets measuring routing accuracy, unnecessary delegation, safe fallback rate, and total cost/latency.
8. Prompt-injection defenses: incident text is untrusted data, not instructions that can change supervisor policy.

## 11. Knowledge check

1. What is the difference between schema validation and policy validation?
2. Why must `goto` be selected from a Python allow-list?
3. What should happen when the model returns malformed output twice?
4. Why is model confidence not an authorization signal?
5. Which controls must be added before replacing mock workers with MCP tools?

## 12. Completion exercise

Add a `database_agent` specialist. Update the Pydantic Literal, allow-list, worker node, graph edges, tests, and supervisor prompt. Add a test proving that a model cannot route to an arbitrary node such as `delete_production_database`.

## References

- [ChatOllama with_structured_output reference](https://reference.langchain.com/python/langchain-ollama/chat_models/ChatOllama/with_structured_output)
- [LangGraph Command and graph API](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/graph-api.mdx)
- [LangChain structured output guide](https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/structured-output.mdx)
