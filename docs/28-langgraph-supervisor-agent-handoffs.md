# Lesson 28 — LangGraph Supervisor Pattern and Agent Handoffs

## Learning objectives

- Explain supervisor, worker, routing, and handoff.
- Build a supervisor that delegates to specialist subgraphs.
- Use `Command(goto=...)` to update state and transfer control.
- Return control from workers to the supervisor.
- Bound delegation with an explicit budget.
- Distinguish a supervisor graph you implement yourself from the optional `langgraph-supervisor` library.

## 1. What is the supervisor pattern?

A supervisor is a coordinator that decides which specialist should work next. A worker performs a narrow task and returns its result. The supervisor reviews the result and decides whether to delegate again or finish.

For a DevOps incident:

- Supervisor: plans the investigation and chooses the next specialist.
- Metrics specialist: checks latency, CPU, memory, traffic.
- Logs specialist: searches application errors.
- Infrastructure specialist: checks deployment and runtime status.
- Report node: produces the final evidence summary.

This is different from Lesson 27's parallel specialist fan-out. Fan-out starts several independent workers in the same stage. A supervisor delegates selectively, observes each result, and chooses the next step.

## 2. What is a handoff?

A handoff transfers graph control from the current node to another node. It may also update state with the task, reason, and context the next worker needs.

LangGraph's `Command` combines a state update with control flow:

~~~python
from langgraph.types import Command

def supervisor(state):
    return Command(
        goto="metrics_agent",
        update={"route_reason": "The incident reports elevated latency."},
    )
~~~

A worker can return control to the supervisor through a normal edge:

~~~python
builder.add_edge("metrics_agent", "supervisor")
~~~

The supervisor then runs again and decides what to do next. This creates the supervisor-worker loop.

Official reference: [LangGraph Command and graph control flow](https://docs.langchain.com/oss/python/langgraph/graph-api#command).

## 3. Architecture in this lesson

~~~text
             START
                |
           supervisor
          /     |      \
      metrics  logs   infrastructure
          \     |      /
           supervisor
                |
             finalize
                |
               END
~~~

The supervisor maintains a bounded queue of specialists to invoke. For this deterministic teaching example, the queue is initialized from incident type and evidence. In a model-powered system, the supervisor LLM can choose the next specialist using structured output or approved handoff tools. The execution boundary and safety checks should remain in trusted application code.

## 4. Runnable example

See [examples/langgraph_supervisor/](../examples/langgraph_supervisor/).

The example uses mock specialists and an explicit deterministic supervisor policy. It does not call an LLM, MCP server, or real infrastructure. This keeps routing behavior reproducible.

### Run

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r examples/langgraph_supervisor/requirements.txt
python examples/langgraph_supervisor/main.py
python -m unittest discover -s examples/langgraph_supervisor -p "test_*.py" -v
~~~

## 5. Read the implementation carefully

The supervisor decides the next node and returns a `Command`. For example:

~~~python
return Command(
    goto=next_agent,
    update={
        "remaining_agents": remaining,
        "handoff_count": state["handoff_count"] + 1,
        "route_reason": reason,
    },
)
~~~

The worker returns a finding. It does not choose the next worker:

~~~python
def metrics_agent(state):
    return {
        "findings": [{
            "specialist": "metrics",
            "summary": "p95 latency is elevated",
        }]
    }
~~~

The edge sends control back to the supervisor. The supervisor owns the next decision.

## 6. Why bound handoffs?

An unconstrained supervisor can keep delegating forever, repeat the same work, or create unnecessary cost.

The example enforces:
- a finite list of permitted specialists;
- duplicate removal;
- a maximum handoff count;
- a known destination allow-list;
- a deterministic terminal path.

Production systems should additionally enforce request deadlines, token/cost budgets, per-tool timeouts, idempotency, and cancellation. Do not rely only on the graph recursion limit: application-level budgets explain and control why a workflow stops.

## 7. Supervisor policy: deterministic versus LLM-powered

There are two distinct approaches:

### Deterministic supervisor

Trusted Python rules choose the next specialist. Advantages:
- predictable;
- inexpensive;
- easy to unit test;
- appropriate when routing rules are known.

Disadvantages:
- rigid;
- needs code changes as routing requirements evolve;
- less capable with ambiguous natural-language incidents.

### LLM-powered supervisor

An LLM interprets the incident and selects among a limited set of handoff tools. Advantages:
- flexible routing from natural-language context;
- can adapt delegation based on findings.

Disadvantages:
- non-deterministic;
- adds inference cost and latency;
- may select an inappropriate tool;
- requires structured validation and strict authorization.

A strong production design often combines both: the model proposes a route, and trusted code validates that route against an allow-list, authorization policy, remaining budget, and workflow state.

## 8. The optional langgraph-supervisor package

LangChain also provides a separate `langgraph-supervisor` package with helpers such as `create_supervisor` and `create_handoff_tool`. It can be useful when you want a prebuilt supervisor abstraction.

However, current LangChain guidance recommends implementing the supervisor pattern directly with tools for many use cases because this gives more control over context engineering and handoffs. Learn the underlying graph pattern first; do not add a helper package just because it exists.

References:
- [Supervisor package reference](https://reference.langchain.com/python/langgraph-supervisor)
- [create_supervisor API](https://reference.langchain.com/python/langgraph-supervisor/supervisor/create_supervisor)
- [create_handoff_tool API](https://reference.langchain.com/python/langgraph-supervisor/handoff/create_handoff_tool)

## 9. Production guardrails

1. Only allow known worker destinations.
2. Validate incident, tenant, environment, and service scope before delegation.
3. Pass only the minimum required context to each specialist.
4. Set a maximum number of handoffs and an overall deadline.
5. Prevent duplicate or conflicting investigations.
6. Preserve partial results if one specialist fails.
7. Record who/what selected a worker, why, and what input was sent.
8. Keep remediation separate from investigation; require explicit approval for changes.
9. Test the supervisor policy independently from LLM output.
10. Treat worker output as evidence, not as trusted instructions.

## 10. Exercises

1. Add a database specialist and route to it when logs report connection pool exhaustion.
2. Add an `unavailable` result and verify the supervisor can continue with other specialists.
3. Add a hard deadline to the graph invocation.
4. Add a structured route proposal from an LLM, but validate it against the specialist allow-list.
5. Add an approval node before any remediation capability.
6. Compare this sequential supervisor with Lesson 27's parallel specialist graph. Measure latency, cost, and evidence completeness.

## 11. Knowledge check

1. What is the responsibility of the supervisor?
2. What does a handoff transfer?
3. Why does a worker return control to the supervisor?
4. Why should the handoff count be bounded?
5. When is deterministic routing preferable to LLM routing?
6. Why must a model-proposed destination be validated by trusted code?

## Key takeaway

The supervisor owns coordination; specialists own narrow tasks. A handoff is a controlled transfer of execution, not unrestricted agent-to-agent conversation. Build the control flow explicitly, validate every delegation, and make termination a deliberate part of the design.

Next: combine supervisor routing with real model decisions, structured outputs, and MCP tools while keeping authorization and execution in trusted application code.
