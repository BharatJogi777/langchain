# Lesson 27 — LangGraph Subgraphs and Multi-Agent Architecture

## Learning objectives

By the end of this lesson, you should be able to:
1. Explain what a LangGraph subgraph is.
2. Build and compile a specialist graph independently.
3. Connect child graphs to a parent graph.
4. Choose between direct subgraph nodes and wrapper-node invocation.
5. Run specialist workflows in parallel and aggregate their findings.
6. Decide which state should be shared and which should remain private.

## 1. What is a subgraph?

A subgraph is a graph used as a node inside another graph. The outer graph is the **parent graph**; the nested graph is the **child graph**.

A subgraph is useful when a workflow has a meaningful independent responsibility. Examples:
- a log investigation workflow;
- a metrics analysis workflow;
- an infrastructure inspection workflow;
- a document retrieval workflow;
- a policy or compliance review workflow.

LangGraph documents subgraphs as a composition mechanism for multi-agent systems, reusable workflows, and independently developed components. See the official [Subgraphs guide](https://docs.langchain.com/oss/python/langgraph/use-subgraphs). [Source: official docs]

## 2. Parent graph and specialist subgraphs

Our DevOps investigation example has three specialists:

~~~text
                     Parent graph
                          |
            +-------------+-------------+
            |             |             |
         Logs agent    Metrics agent   Infra agent
         subgraph       subgraph       subgraph
            |             |             |
         findings      findings      findings
            +-------------+-------------+
                          |
                    Synthesis node
                          |
                    Incident report
~~~

Each specialist owns its own small workflow. The parent owns orchestration and final aggregation.

Important: these are deterministic workflow specialists with mock evidence, not autonomous LLM agents. We will add model reasoning and MCP calls in later integration exercises. A graph boundary alone does not make a component an AI agent.

## 3. Two ways to connect a subgraph

The official documentation describes two common patterns.

### Pattern A — Add a compiled subgraph directly as a node

Use this when parent and child graphs share state keys and the child should read/write those shared channels.

~~~python
builder.add_node("specialist", compiled_subgraph)
~~~

This is concise, but it couples the child to the parent's state contract.

### Pattern B — Invoke a subgraph inside a wrapper node

Use this when the child has a different state schema, needs private state, or requires input/output transformation.

~~~python
def run_specialist(parent_state):
    child_result = specialist.invoke({
        "incident_id": parent_state["incident_id"],
        "services": parent_state["services"],
    })
    return {"findings": [child_result["finding"]]}
~~~

This lesson uses Pattern B. Each specialist gets only the input it needs, and the wrapper maps the child result into the parent's shared output.

Reference: [LangGraph Subgraphs — define subgraph communication](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#define-subgraph-communication).

## 4. Build a specialist subgraph

Each specialist has its own state contract:

- `incident_id`
- `services`
- `evidence`
- `private_notes`

The parent does not need to know about the child's private notes. It receives only a concise finding.

This is a useful encapsulation boundary:
- parent state describes the overall investigation;
- child state describes one specialist's internal work;
- wrapper functions define the integration contract.

## 5. Parallel specialist execution

The parent graph starts all three specialist wrapper nodes in the same super-step. Each returns a partial update to the parent's `findings` channel.

The findings channel uses a reducer so concurrent writes are combined rather than overwriting one another.

Do not assume parallel completion order is stable. Sort findings before producing a deterministic report.

## 6. Persistence and memory

Subgraph persistence is a separate design decision. LangGraph supports per-invocation, per-thread, and stateless subgraph checkpointing modes. For most independent incident investigations, per-invocation state is a sensible starting point. Use per-thread persistence only when a specialist intentionally needs memory across multiple calls in the same thread.

If you enable checkpointing, compile the parent with a checkpointer and pass a `thread_id` when invoking it. Do not persist sensitive logs or credentials without an explicit retention and access policy.

See the official [subgraph persistence guide](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#subgraph-persistence).

## 7. Run the example

From the repository root:

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r examples/langgraph_subgraphs/requirements.txt
python examples/langgraph_subgraphs/main.py
python -m unittest discover -s examples/langgraph_subgraphs -p "test_*.py" -v
~~~

No LLM, API key, MCP server, or cloud account is required. All findings are deterministic mock data.

## 8. Production design guidance

Before turning these specialist workflows into real agents:

1. Give each specialist a narrow responsibility and explicit input/output schema.
2. Authorize requested services and tenants before invoking specialists.
3. Give external MCP calls timeouts, bounded retries, and concurrency limits.
4. Return structured partial failures instead of silently dropping failed specialists.
5. Keep secrets and raw credentials out of graph state and model prompts.
6. Add tracing around parent and child graph invocations.
7. Set a policy for which child state is checkpointed and how long it is retained.
8. Add a human approval step before consequential remediation.

A subgraph is an orchestration boundary, not a security sandbox. Child nodes execute in the same application process and inherit the application's trust level.

## 9. Exercises

1. Add a deployment-history specialist.
2. Make the logs specialist return a structured severity.
3. Simulate the metrics specialist failing and preserve the other findings.
4. Add a wrapper validation step that rejects an empty incident ID.
5. Add a checkpointer to the parent and inspect nested state.
6. Replace one mock specialist with an MCP client call.
7. Add a human approval node before any remediation action.

## 10. Knowledge check

1. What is a LangGraph subgraph?
2. When should you add a compiled subgraph directly as a node?
3. When should you call a subgraph inside a wrapper node?
4. Why does this example use separate child state?
5. Why does the parent findings channel need a reducer?
6. Does a subgraph provide a security boundary?

## Official references

- [LangGraph Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
