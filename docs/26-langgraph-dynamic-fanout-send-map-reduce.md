# Lesson 26 — Dynamic Fan-out with Send and Map-Reduce

## Learning objectives

By the end of this lesson, you will understand how to:
1. Dispatch a runtime-determined number of worker tasks.
2. Pass each worker its own small input state with `Send`.
3. Aggregate parallel worker updates with a reducer.
4. Handle empty input and enforce a fan-out limit.
5. Distinguish fixed parallel branches from dynamic fan-out.
6. Apply this pattern to services, regions, hosts, documents, and MCP evidence sources.

## 1. Why dynamic fan-out?

In Lesson 23, you wired a fixed set of parallel collectors: logs, metrics, and infrastructure. That is useful when the number of tasks is known at graph-design time.

But consider an incident affecting an unknown number of services:

- One incident may involve 2 services.
- Another may involve 12 services.
- A third may involve 50 services.

You do not want to create 50 different nodes. You want one worker node and a runtime decision to invoke it once for each service.

That is **dynamic fan-out**.

## 2. What Send does

`Send` is a message describing:
- the name of the worker node to execute;
- the custom input state for that worker.

A routing function returns a list of `Send` objects. LangGraph schedules those worker invocations in parallel. Each worker returns a partial state update. A reducer merges the updates into the graph's shared state.

~~~text
                dispatch
                   |
         runtime list of services
           /        |        \
        Send      Send       Send
         |          |          |
      worker     worker      worker
      service A  service B   service C
         \          |          /
             results reducer
                    |
                 summarize
~~~

Official API reference: https://docs.langchain.com/oss/python/langgraph/graph-api

## 3. Fixed parallel branches vs Send

| Fixed branches | Dynamic fan-out with Send |
|---|---|
| Nodes known at graph-build time | Number of worker invocations known at runtime |
| One named edge per branch | One worker node can run many times |
| Good for logs + metrics + infra | Good for N services, hosts, docs, regions |
| Each branch normally receives graph state | Each Send can pass custom worker input |

Use fixed branches when the set of tasks is stable. Use Send when the number of tasks varies per request.

## 4. Example state design

The parent graph state contains:
- incident ID;
- list of target services;
- aggregated results;
- final report.

Each worker only needs:
- incident ID;
- one service name.

This smaller worker input is intentional. A worker should receive only the data it needs, rather than an entire application state containing unrelated information.

The example uses a list reducer to collect worker outputs. The ordering of concurrently produced results is not a business guarantee. Sort by service name or an explicit sequence field before presenting a stable report.

## 5. Dispatch validation and fan-out limits

Do not blindly create one worker per untrusted input item.

The example:
- rejects more than 25 services;
- strips whitespace;
- rejects empty names;
- deduplicates service names;
- handles an empty service list without creating workers.

In a production API, also validate tenant ownership and service access before invoking the graph. A fan-out cap protects your application from accidental or malicious work amplification.

## 6. Map and reduce

**Map:** invoke the same worker for each service. Each worker independently gathers or analyzes evidence.

**Reduce:** collect the worker updates into a shared result list using a reducer, then synthesize a report after all workers finish.

A reducer is not a database transaction and does not make external operations idempotent. Give each logical operation a stable idempotency key, bound retries, and preserve partial failures as structured result records.

## 7. Run the example

From the repository root:

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r examples/langgraph_send/requirements.txt
python examples/langgraph_send/main.py
python -m unittest discover -s examples/langgraph_send -p "test_*.py" -v
~~~

No LLM, API key, MCP server, or cloud account is required. The worker uses deterministic mock service observations.

## 8. Production applications

The same architecture can be used for:
- one investigation worker per microservice;
- one retrieval worker per document;
- one scan worker per host or cluster;
- one compliance check per cloud account;
- one analysis task per region;
- one MCP tool call per independent evidence source.

For real external calls, use async nodes where appropriate, set per-operation timeouts, limit concurrency, retry only safe transient failures, and retain partial results if a worker fails.

Do not put an unbounded number of tasks into a single graph invocation. Consider queue-based orchestration or chunked batches for very large workloads.

## 9. Exercises

1. Add a worker that checks deployment history for each service.
2. Add a structured `status` field with values such as `ok`, `unavailable`, and `error`.
3. Sort the final report by service name.
4. Add a tenant ID and enforce service authorization before dispatch.
5. Add a configurable fan-out limit and test the boundary.
6. Simulate one worker returning unavailable evidence while the other workers succeed.
7. Replace the mock worker with an async MCP call using Lesson 22's timeout and retry policy.

## 10. Knowledge check

1. What does `Send` specify?
2. Why is a worker input often smaller than the parent graph state?
3. Which state mechanism aggregates worker results?
4. Why should the application cap the number of dispatched workers?
5. Is the order of parallel worker results guaranteed?
6. When would you choose a fixed branch instead of dynamic fan-out?

## Official references

- Graph API and Send: https://docs.langchain.com/oss/python/langgraph/graph-api
- Send API reference: https://reference.langchain.com/python/langgraph/types/Send
- Graph API overview: https://docs.langchain.com/oss/python/langgraph/overview
