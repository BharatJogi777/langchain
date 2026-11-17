# Lesson 25 — Conditional Routing, Loops, and Dynamic Workflows

## Learning objectives

You will learn to:
1. Route an execution path based on validated graph state.
2. Build a loop with both a quality condition and a hard iteration cap.
3. Use the recursion limit as a final safety net.
4. Understand when to use conditional edges, `Command`, and `Send`.
5. Design a DevOps investigation that gathers more evidence only when needed.

## 1. Conditional routing

A normal edge always selects the same next node:

~~~python
builder.add_edge("validate", "process")
~~~

A conditional edge calls a routing function after a node completes:

~~~python
def route_by_severity(state):
    if state["severity"] == "low":
        return "close_low"
    return "investigate"

builder.add_conditional_edges(
    "classify",
    route_by_severity,
    {
        "close_low": "close_low",
        "investigate": "collect_evidence",
    },
)
~~~

The routing function receives the current state and returns a destination (or destinations). Keep routing deterministic and side-effect free. Validate severity before it enters the graph.

**Important:** for a given source node, use either static outgoing edges or dynamic routing. Mixing static edges with conditional routing can cause both paths to execute. See the official Graph API documentation: https://docs.langchain.com/oss/python/langgraph/graph-api

## 2. Build a loop

A loop is simply an edge that points back to an earlier node.

~~~text
collect_evidence
       |
    evaluate
       |
  enough evidence?
    /       \
  yes        no
   |          |
finalize   collect_evidence
~~~

The loop needs an explicit exit condition. In the example:
- stop when confidence reaches the target;
- otherwise collect more evidence;
- stop anyway when the maximum collection attempts are reached.

A confidence score in a real system must be calibrated and evaluated. The example uses deterministic mock values to demonstrate control flow, not a real incident confidence model.

## 3. Hard limits and recursion limits

Your own state counter is a business rule: for example, at most three collection attempts.

LangGraph's `recursion_limit` is a separate execution safety ceiling measured in graph super-steps. Pass it at the top level of the invocation config:

~~~python
result = graph.invoke(
    initial_state,
    {"recursion_limit": 20},
)
~~~

If the graph exceeds the limit, LangGraph raises `GraphRecursionError`. Catch it at the application boundary, record the failure, and return a controlled response. Do not simply increase the limit to hide a broken exit condition.

The exact default recursion limit can vary by LangGraph release. Set an explicit limit appropriate to the workflow. Official reference: https://docs.langchain.com/oss/python/langgraph/graph-api

## 4. Example: evidence gathering loop

The runnable example implements:

1. `classify`: inspect the incident severity.
2. Conditional route: low severity goes to `close_low`; other severities go to `collect_evidence`.
3. `collect_evidence`: adds one deterministic mock evidence record and increments the attempt count.
4. `evaluate`: updates confidence from the mock evidence progression.
5. Conditional route: either loop back to collection or finalize.
6. `finalize`: creates a summary.

The evidence field uses a reducer because each collection attempt contributes another record. The attempt counter and confidence score use normal replacement semantics because each node returns the next scalar value.

## 5. Choosing the right control-flow primitive

| Primitive | Use it when |
|---|---|
| Normal edge | The next step is always the same |
| Conditional edge | Routing depends on state after a node |
| `Command` | One node must update state and choose the next node together |
| `Send` | A runtime-sized collection must fan out into repeated worker-node executions |

Prefer conditional edges for ordinary routing. Use `Command` when the state update and route belong together in the same node. Use `Send` for map-reduce patterns where the number of worker tasks is only known at runtime.

Official references:
- Graph API: https://docs.langchain.com/oss/python/langgraph/graph-api
- Control flow and loops: https://docs.langchain.com/oss/python/langgraph/use-graph-api
- Send and Command: https://docs.langchain.com/oss/python/langgraph/graph-api

## 6. Production guardrails

- Validate all routing fields before graph invocation.
- Keep a business-level maximum attempt count.
- Set a graph recursion limit.
- Apply a whole-workflow deadline in the API layer.
- Apply per-tool timeouts and bounded retries at each integration boundary.
- Retry only safe, idempotent operations.
- Distinguish an empty result from a failed dependency.
- Record why a loop stopped: quality threshold, max attempts, deadline, cancellation, or error.
- Do not let an LLM decide access control or whether a dangerous action is authorized.
- Test every branch and both loop exit conditions.

## 7. Run the example

From the repository root:

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r examples/langgraph_routing/requirements.txt
python examples/langgraph_routing/main.py
python -m unittest discover -s examples/langgraph_routing -p "test_*.py" -v
~~~

The example uses mock evidence and no model, API key, MCP server, or cloud dependency.

## 8. Exercises

1. Add a route for critical severity to an immediate escalation node.
2. Add a separate route for a source outage; do not treat it as "no evidence".
3. Change the confidence threshold and verify how many loop iterations occur.
4. Add a deadline field and stop collecting when the deadline is reached.
5. Add a test proving that max attempts always terminates the loop.
6. Add a manual-review route when evidence remains insufficient after the maximum attempts.

## 9. Knowledge check

1. What is the difference between a normal edge and a conditional edge?
2. Why should a loop have both a business-level cap and a recursion limit?
3. What is the difference between `Command` and a conditional edge?
4. When would you use `Send`?
5. Why is a mock confidence score not a production incident confidence model?

## Next lesson

Lesson 26 — Dynamic Fan-out with Send and Map-Reduce: dispatch one worker per service, host, region, or evidence source, then aggregate the results safely.
