# Lesson 23 — LangGraph: Production Workflows

## 1. Why LangGraph?

A chain is usually a mostly fixed sequence. An agent gives the model discretion to choose tools. A production workflow often needs something more explicit: shared state, deterministic routing, parallel work, bounded execution, persistence, and approval gates.

LangGraph models a workflow as a directed graph:

- **State** is the shared data passed between steps.
- **Nodes** are Python functions (or async functions) that read state and return updates.
- **Edges** define what runs next.
- **Conditional edges** choose a route from current state.
- **Reducers** define how concurrent updates to a state field are combined.
- **Checkpointers** persist graph state by thread.
- **Interrupts** pause execution for an external decision, such as human approval.

Use a graph when the control flow matters and should be inspectable. Do not use a graph merely to make a simple prompt call look sophisticated.

## 2. Mental model

```text
                 START
                   |
          classify_incident
                   |
            route_by_severity
             /           \
          low             high
           |                |
       close_ticket     collect evidence
                         /          \
                    logs node    infra node
                         \          /
                       synthesize
                           |
                          END
```

The example in this lesson focuses on the parallel evidence branch. It uses deterministic mock tools so you can learn graph mechanics without API keys or a running LLM.

## 3. Install and run

Use Python 3.11+ and a virtual environment. From the repository root:

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r examples/langgraph_workflows/requirements.txt
python examples/langgraph_workflows/main.py
python -m unittest discover -s examples/langgraph_workflows -p "test_*.py" -v
~~~

The example pins a compatible major-version range rather than pretending every future release has identical APIs. For a production application, resolve and lock exact versions after testing in your target environment.

## 4. State is the workflow contract

State is not conversational memory. It is the typed data contract for one graph execution.

In the example, `InvestigationState` contains:

- incident identifier and service name;
- severity;
- evidence returned by independent collectors;
- a final summary.

Nodes return partial updates. They should not mutate shared state in place. For concurrent branches, use a reducer for fields that multiple nodes update. The example uses an `Annotated[list, operator.add]` reducer for evidence.

Important design rules:

1. Keep state serializable if you intend to checkpoint it.
2. Store identifiers and concise evidence, not huge raw log files.
3. Do not put secrets or access tokens in graph state.
4. Validate external input before starting the graph.
5. Define ownership of each state key; avoid multiple nodes writing the same scalar field concurrently.

## 5. Nodes and edges

A node is an ordinary Python callable that accepts the state and returns a dictionary of updates. An edge connects nodes. The graph is compiled before invocation.

The example has:
- `collect_logs`: mock log evidence;
- `collect_infrastructure`: mock infrastructure evidence;
- `synthesize`: combines evidence into a deterministic summary.

The two collectors are launched as parallel branches. A join edge waits for both branches before synthesis. This is useful when evidence sources are independent and the overall workflow can benefit from concurrent I/O.

Parallel does not mean unlimited. In production, apply concurrency limits, per-tool timeouts, request deadlines, and the retry policy covered in Lesson 22.

## 6. Conditional routing

Use `add_conditional_edges` when the next step depends on state. A routing function should be deterministic, fast, and side-effect free.

Good routing inputs include validated severity, approval status, whether required evidence exists, and explicit policy outcomes. Do not let an LLM make authorization decisions. A model can recommend an action; trusted application code must enforce policy.

## 7. Persistence and thread identity

A checkpointer saves graph snapshots. When invoking a compiled graph with a checkpointer, pass a stable `thread_id` in the configurable section. The thread ID identifies one workflow conversation/execution history; it is not an authorization mechanism.

For local learning, an in-memory checkpointer is convenient but loses state when the process exits. For production, select a durable checkpointer supported by your deployment, configure retention, protect stored state, and test recovery after process restarts.

Do not confuse:
- **Graph state:** data for the current workflow thread.
- **Checkpointer:** persistence of graph execution state.
- **Store:** application-managed data that can be shared across threads.
- **LLM context:** the subset of information deliberately sent to a model.

## 8. Human approval and interrupts

For consequential operations—restarting production services, rolling back deployments, changing firewall rules—pause before execution.

LangGraph supports interrupt/resume workflows. A node can call `interrupt(payload)` to pause and expose a review payload. Resume the same thread using `Command(resume=...)`. The node may be re-entered when resumed, so put side effects after the approval check and make them idempotent. Never treat a user-supplied resume value as sufficient authorization: validate the actor and policy in trusted application code.

A safe flow is:

1. Agent proposes an action with arguments and evidence.
2. Backend validates schema, scope, and policy.
3. Graph interrupts with a review payload.
4. An authenticated human approves or rejects.
5. Backend verifies the approver is authorized.
6. Graph resumes; only then can the controlled action run.
7. Record an audit event with actor, decision, timestamp, and action ID.

## 9. Error handling and reliability

A graph does not automatically make tools reliable. Apply the controls from Lesson 22 at tool boundaries:

- Set per-operation timeouts and an overall workflow deadline.
- Retry only known transient failures and safe/idempotent operations.
- Bound attempts and use exponential backoff with jitter.
- Limit concurrency.
- Preserve partial evidence when one source fails.
- Distinguish "no evidence found" from "source unavailable".
- Use idempotency keys for side effects.
- Add circuit breakers where repeated dependency failures would otherwise cascade.

Represent expected failures in state as structured outcomes. Avoid swallowing unexpected exceptions and reporting a false success.

## 10. Testing strategy

Test the graph at multiple levels:

- Node unit tests: input state produces expected partial updates.
- Routing tests: each policy outcome selects the correct branch.
- Graph integration tests: parallel collectors join and produce a result.
- Failure tests: one collector fails while the other still returns evidence.
- Persistence tests: resume a thread using the same thread ID.
- Approval tests: rejected or unauthorized actions never execute.
- Evaluation tests: measure whether the final investigation is grounded in collected evidence.

The included tests use only the standard library test runner and deterministic mock collectors.

## 11. Production architecture

For the DevOps Investigation Agent capstone, a practical boundary is:

~~~text
FastAPI request
   |
Authentication + request validation
   |
Create / load investigation thread
   |
LangGraph orchestrator
   |-- Logs MCP client
   |-- Metrics MCP client
   |-- Infrastructure MCP client
   |-- Policy / approval service
   |
Evidence normalization + provenance
   |
LLM synthesis (optional, grounded in evidence)
   |
Persist result + audit events
   |
API response / streaming updates
~~~

Keep the API layer responsible for authentication, authorization, request validation, and response shaping. Keep the graph responsible for workflow progression. Keep MCP servers responsible for narrowly scoped capabilities. Keep privileged execution behind a separate policy-enforcing service.

## 12. Exercises

1. Add a metrics collector that returns CPU and memory observations.
2. Add a conditional route: if no evidence source succeeds, route to `manual_review`.
3. Add a correlation ID to state and include it in every collector result.
4. Replace the in-memory checkpointer with a durable backend and test restart recovery.
5. Add an approval interrupt before a mock restart operation. Prove that rejection never calls the operation.
6. Add a workflow deadline and a concurrency limit for collectors.

## 13. Knowledge check

1. What is the difference between a node and an edge?
2. Why does a parallel state field need a reducer?
3. What does `thread_id` identify when a checkpointer is enabled?
4. Why must approval be enforced by trusted backend code rather than an LLM response?
5. Why should "source unavailable" differ from "no matching evidence"?

## 14. Official references

- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- Graph API: https://docs.langchain.com/oss/python/langgraph/graph-api
- Persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- Interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- LangGraph testing: https://docs.langchain.com/oss/python/langgraph/test
