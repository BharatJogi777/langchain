# Lesson 27 — LangGraph Subgraphs and Multi-Agent Architecture

## Learning objectives

By the end of this lesson, you should be able to:

1. Explain what a LangGraph subgraph is and why it is useful.
2. Build and compile a specialist graph independently.
3. Choose between adding a compiled subgraph as a node and invoking it inside a wrapper node.
4. Separate specialist-private state from parent-orchestrator state.
5. Run independent specialists in parallel and aggregate results safely.
6. Explain persistence choices and production boundaries for nested workflows.

## 1. Why subgraphs?

A subgraph is a compiled graph used as a node inside another graph. The outer graph is the **parent**; the nested graph is the **child**.

Subgraphs are useful for:
- multi-agent and specialist workflows;
- reusable business processes;
- independent development by teams;
- hiding internal state behind a stable input/output contract.

Official documentation describes both communication patterns and persistence choices: [LangGraph Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs). <Cite>Official LangGraph documentation</Cite>

A single giant graph is often hard to maintain. If logs, metrics, infrastructure, and report generation all share one state schema and one collection of nodes, a small change in one area can affect every other area.

Instead, package each responsibility behind a boundary.

## 2. Target architecture: DevOps investigation

~~~text
                         Parent graph
                              |
              +---------------+---------------+
              |               |               |
          Logs graph      Metrics graph    Infra graph
              |               |               |
          log finding     metric finding   infra finding
              +---------------+---------------+
                              |
                         Synthesis
                              |
                       Incident report
~~~

The parent graph coordinates. Each child graph performs a focused investigation.

Important distinction: a subgraph is a workflow boundary, not automatically an autonomous LLM agent. The example in this lesson uses deterministic mock evidence. A specialist becomes LLM-powered only when you deliberately add a model decision/reasoning step. It can also call approved MCP tools without being an LLM agent.

## 3. Two subgraph communication patterns

### Pattern A — Add the compiled subgraph directly as a node

~~~python
builder.add_node("specialist", compiled_subgraph)
~~~

Use this when the parent and child intentionally share state keys and compatible channel semantics. The child can read and write the shared channels directly.

Advantages:
- concise graph composition;
- parent can statically discover the nested graph;
- useful when the child is designed around the parent's state contract.

Trade-off: this couples the child to the parent's state schema. Changes to shared keys can ripple across graph boundaries.

### Pattern B — Invoke the subgraph inside a wrapper node

~~~python
def run_specialist(parent_state):
    child_input = {
        "incident_id": parent_state["incident_id"],
        "services": parent_state["services"],
    }
    child_result = specialist.invoke(child_input)
    return {"findings": [child_result["finding"]]}
~~~

Use this when the child has a different/private state schema or when input/output transformation is required.

The wrapper is an explicit adapter:
1. Select only the parent data the child is allowed to receive.
2. Invoke the child with its own input contract.
3. Validate and map the child's output.
4. Return a small update to the parent state.

This lesson uses Pattern B. It is a good default for specialist isolation.

## 4. Understand the state boundary

The example's child state contains:
- `incident_id` and `services`: child input;
- `evidence`: intermediate evidence collected by that specialist;
- `private_notes`: internal progress details;
- `finding`: the child result.

The parent state contains:
- `incident_id` and `services`: overall investigation context;
- `findings`: specialist outputs;
- `report`: final synthesis.

The parent does not receive `private_notes`. The wrapper deliberately maps only the finding. This is not just code organization: it reduces accidental coupling and limits how much raw/sensitive evidence flows through the overall graph.

Treat each graph boundary like an API boundary. Validate identifiers, constrain payload sizes, redact sensitive data, and version the output contract.

## 5. Parallel specialists and reducers

In `examples/langgraph_subgraphs/main.py`, the parent graph starts three specialist wrapper nodes from START:

~~~python
builder.add_edge(START, "logs_agent")
builder.add_edge(START, "metrics_agent")
builder.add_edge(START, "infra_agent")
builder.add_edge(
    ["logs_agent", "metrics_agent", "infra_agent"],
    "synthesize",
)
~~~

The list of source nodes creates a join: synthesis waits until all three branches finish.

Each branch writes to the same `findings` state key. That key therefore needs a reducer:

~~~python
class ParentState(TypedDict, total=False):
    findings: Annotated[list[dict[str, str]], operator.add]
~~~

The reducer combines concurrent list updates. Without an appropriate reducer, parallel writes to a single-value channel can cause an invalid concurrent update.

Do not rely on parallel completion order. The synthesis node sorts findings by specialist name so the final report is deterministic.

## 6. Run the example

From the repository root:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r examples/langgraph_subgraphs/requirements.txt
python examples/langgraph_subgraphs/main.py
python -m unittest discover -s examples/langgraph_subgraphs -p "test_*.py" -v
~~~

Expected report shape (exact ordering is sorted by specialist):

~~~text
Incident INC-270 — specialist summary
- Infrastructure: Infrastructure specialist: ...
- Logs: Logs specialist: ...
- Metrics: Metrics specialist: ...
~~~

No LLM, API key, MCP server, cloud account, or live infrastructure is required. All evidence is deterministic mock data.

## 7. Persistence and memory

Subgraph persistence is a separate decision from graph composition. LangGraph documents three useful modes:

| Mode | Configuration | Meaning |
|---|---|---|
| Per-invocation | Default / inherit parent checkpointer | Each child invocation starts fresh; it can still participate in parent durable execution |
| Per-thread | Child compiled with `checkpointer=True` | Child state can accumulate across calls on the same thread |
| Stateless | Child compiled with `checkpointer=False` | No child checkpoint state is saved |

For independent incident investigations, per-invocation state is usually the safest starting point. Per-thread memory is appropriate only when a specialist intentionally needs continuity across calls in the same thread.

If enabling persistence:
- compile the parent with a production checkpointer;
- supply a stable, tenant-safe `thread_id`;
- define retention and deletion policies;
- prevent one user's or incident's evidence from appearing in another context;
- test interrupt/resume and failure recovery.

See [Subgraph persistence](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#subgraph-persistence).

## 8. What changes when specialists call MCP tools?

Keep the graph contract stable and replace the mock collector nodes with trusted tool adapters.

| Specialist | Example read-only MCP capabilities |
|---|---|
| Logs | Search logs by approved service, time window, and query |
| Metrics | Query an allow-listed metric over a bounded time range |
| Infrastructure | Read deployment, pod, node, and event status |

The LLM may help interpret the question or select from approved capabilities, but application code must enforce tenant, environment, service, and time-range authorization. Tool arguments are untrusted input until validated.

Production requirements:
1. Authenticate and authorize every tool call.
2. Enforce least privilege and read-only scopes where possible.
3. Set deadlines, bounded retries, and concurrency limits.
4. Preserve partial findings if one specialist is unavailable.
5. Distinguish `unavailable` evidence from a successful query that found no issue.
6. Record source, timestamp, query parameters, and evidence references.
7. Redact secrets and personal data before state persistence or model context.
8. Require explicit approval before consequential remediation.

A subgraph is **not** a security sandbox. Child nodes run in the same application trust boundary unless you deliberately isolate them in separate processes/services with independent credentials and policy enforcement.

## 9. Common mistakes

| Mistake | Why it is a problem | Better approach |
|---|---|---|
| One giant shared state | Tight coupling and oversized state | Private specialist schemas and explicit output contracts |
| No reducer on parallel writes | Concurrent update conflict | Reducer or separate output channels |
| Return every raw log line | Large and potentially sensitive state | Bounded, redacted evidence summaries and references |
| Assume every specialist succeeds | Partial failures disappear | Typed success/failure results and partial aggregation |
| Treat every subgraph as a separate LLM | Unnecessary cost and complexity | Use graph boundaries first; add models where they add value |
| Persist all child state forever | Cross-incident leakage and stale context | Choose persistence scope deliberately |

## 10. Tests and exercises

Included tests cover:
- a specialist graph's output;
- child-private state not leaking into parent output;
- all three specialist branches being aggregated;
- empty service lists.

Exercises:
1. Add a deployment-history specialist.
2. Add a structured `status` field: `ok`, `degraded`, or `unavailable`.
3. Simulate one specialist failing and preserve the other findings.
4. Add wrapper validation that rejects an empty incident ID.
5. Add a checkpointer to the parent and inspect nested state.
6. Replace one mock specialist with a read-only MCP client call.
7. Add a human approval node before any remediation action.

## 11. Knowledge check

1. What is a LangGraph subgraph?
2. When should you add a compiled subgraph directly as a node?
3. When is a wrapper node a better boundary?
4. Why does the parent findings channel need a reducer?
5. Why should raw evidence and private notes not automatically flow into parent state?
6. Does a subgraph provide a security boundary?
7. When would per-thread subgraph persistence be justified?

## Key takeaway

A robust multi-agent system is not simply many LLMs talking to one another. It is a collection of bounded, testable workflows with explicit contracts, controlled tool access, deliberate persistence, and a parent orchestrator that coordinates specialists and handles their results.

Next lesson: combine subgraphs with dynamic fan-out so a runtime number of services, regions, or evidence sources can be investigated using the same specialist workflow.
