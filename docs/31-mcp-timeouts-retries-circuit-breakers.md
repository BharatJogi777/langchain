# Lesson 31 — MCP Tool Execution: Timeouts, Retries, Circuit Breakers, and Failure Recovery

## 1. What you will build

Lesson 30 connected three specialist agents to separate MCP servers: logs, metrics, and infrastructure. The missing production concern is what happens when one dependency becomes slow or unavailable.

In this lesson, you will add a reusable resilience boundary around each specialist:

- A per-attempt timeout.
- Bounded retries for explicitly classified transient failures.
- Exponential backoff with jitter.
- A circuit breaker with CLOSED, OPEN, and HALF_OPEN states.
- Independent specialist execution.
- Partial reports when one specialist fails.
- Deterministic tests that do not require Ollama or running MCP servers.

The example reuses the three read-only mock MCP servers from Lesson 30.

## 2. Failure taxonomy: do not treat every error the same

| Failure | Example | Retry? | Why |
|---|---|---:|---|
| Invalid input | Empty service name | No | The same request will fail again |
| Authentication/authorization | 401/403 or denied scope | No | Retrying does not repair permissions |
| Domain result | Service not found | Usually no | This is a meaningful result, not an outage |
| MCP tool execution error | Server returns `isError=True` | Usually no | Adapter may return it as an error-status ToolMessage |
| Transient transport error | Connection reset, temporary unavailable | Maybe | Only if operation is safe to repeat |
| Timeout | Tool exceeds its deadline | Maybe | Remote execution may still have completed |
| Protocol/schema error | Invalid response shape | No by default | Usually an integration defect |

The Python MCP adapter distinguishes an MCP tool execution error from a transport/session failure. With `MultiServerMCPClient(handle_tool_errors=True)`, execution errors are returned to the agent as error-status tool messages; transport/session failures still raise. This setting is not a general retry mechanism. See the [adapter API reference](https://reference.langchain.com/python/langchain-mcp-adapters/client/MultiServerMCPClient).

**Important:** Do not classify every exception as transient. Inspect the exact exception types emitted by the versions you pin, and explicitly map only known temporary transport failures to your retryable exception set.

## 3. Timeout, retry budget, and workflow deadline

These are three different controls:

- **Attempt timeout:** maximum time for one call, for example 4 seconds.
- **Retry budget:** maximum number of attempts, including the first.
- **Workflow deadline:** maximum total time for the complete investigation.

If an attempt takes 4 seconds and you allow 3 attempts plus backoff, that specialist may consume considerably more than 4 seconds. A production API should enforce an overall request deadline as well as per-tool deadlines.

Python 3.11+ supports `asyncio.timeout()`; `asyncio.wait_for()` is also available. A timeout cancels the local awaitable and raises `TimeoutError`, but cancellation does not prove that a remote server stopped processing the request. Read the [Python asyncio timeout documentation](https://docs.python.org/3.12/library/asyncio-task.html#timeouts).

For a side-effecting operation, a lost response can mean the operation completed remotely even though the client timed out. Use server-enforced idempotency keys and operation status checks; do not blindly retry deployments, restarts, payments, deletes, or writes.

## 4. Exponential backoff and jitter

A bounded exponential backoff grows between attempts:

```text
cap = min(max_delay, base_delay * 2 ** (attempt - 1))
delay = random(0, cap)  # full jitter
```

Example with a 0.25 second base delay and 2 second cap:

| Retry | Maximum delay |
|---|---:|
| Before attempt 1 | 0 s |
| Before attempt 2 | 0.25 s |
| Before attempt 3 | 0.50 s |
| Before attempt 4 | 1.00 s |
| Before attempt 5 | 2.00 s |

Jitter prevents many application instances from retrying at exactly the same time after a shared outage. Retries must remain bounded and fit within the overall deadline.

## 5. Circuit breaker state machine

A retry asks: **Should I attempt this operation again?**

A circuit breaker asks: **Should I call this dependency at all right now?**

| State | Behavior | Transition |
|---|---|---|
| CLOSED | Calls are allowed; failures are counted | Threshold reached → OPEN |
| OPEN | Calls fail fast without contacting dependency | Cool-down elapsed → HALF_OPEN |
| HALF_OPEN | One probe is allowed to test recovery | Probe succeeds → CLOSED; fails → OPEN |

Use a separate breaker per dependency (and often per operation class). A failing metrics server must not block healthy logs or infrastructure servers.

This example's in-memory breaker is suitable for one process and learning. In a multi-worker or multi-replica deployment, each worker would otherwise have a different breaker state. Use a shared coordination mechanism or a mature resilience library when cross-process breaker state is required. Also define how a process restart affects breaker state.

## 6. Project structure

```text
examples/mcp_resilience_advanced/
├── main.py
├── requirements.txt
├── README.md
├── app/
│   ├── __init__.py
│   ├── resilience.py
│   └── investigation.py
└── tests/
    ├── __init__.py
    └── test_resilience.py
```

## 7. Implement the resilience boundary

Read `app/resilience.py`.

The `ResilientExecutor` wraps an asynchronous operation. It:
1. Asks the circuit breaker for permission.
2. Executes the operation with a timeout.
3. Retries only configured exception classes.
4. Applies bounded exponential backoff with full jitter.
5. Records one final success or failure for the breaker.
6. Raises a clear exception when the circuit is open.

The example injects the clock, sleep function, and random source so unit tests can control time and avoid slow/flaky waits.

Do not put broad `except Exception: retry` logic in production. Non-retryable errors are propagated immediately.

## 8. Isolate specialists and preserve partial results

Read `app/investigation.py`.

The logs, metrics, and infrastructure specialists are independent evidence sources. Run them concurrently and collect their outcomes independently. One failed specialist should not erase successful evidence from the others.

A partial report must clearly distinguish:
- Evidence actually returned by a specialist.
- A specialist that was unavailable.
- A hypothesis that still needs verification.

Never turn a failed metrics query into an invented latency number. Never present missing evidence as a healthy result.

The example sanitizes failure output to the exception class rather than copying arbitrary exception text into the report. Production systems should log the full exception in a protected observability system with a correlation ID, while exposing only safe summaries to the model and end user.

## 9. Connect to the Lesson 30 MCP specialists

Read `main.py`.

The program:
1. Starts the same three stdio MCP servers from Lesson 30.
2. Discovers each server's tools independently.
3. Creates a specialist agent with only its own tools.
4. Wraps each specialist's `ainvoke` call in its own `ResilientExecutor`.
5. Runs specialists independently and produces a full or partial report.

The default retryable exception set is intentionally narrow: `TimeoutError`, `ConnectionError`, and `OSError`. This is a teaching default, not a guarantee that every MCP transport emits these exact classes. Before production use, inspect and test the exception types from your pinned MCP SDK and adapter, then explicitly map transient failures. Do not add authentication, validation, or tool execution errors to this set.

The MCP adapter's `handle_tool_errors=True` setting allows an agent to inspect tool execution errors, but transport/session failures still need application-level handling. See the [adapter README](https://github.com/langchain-ai/langchain-mcp-adapters#tool-error-handling).

## 10. LangGraph node retries versus tool retries

LangGraph provides a node-level `RetryPolicy` with controls such as `max_attempts`, backoff, jitter, and `retry_on`. See the [RetryPolicy reference](https://reference.langchain.com/python/langgraph/types/RetryPolicy).

Choose the correct boundary:

- **Tool-level wrapper:** best when one tool or specialist call needs a specific timeout, retry classification, breaker, and audit context.
- **LangGraph node RetryPolicy:** useful when retrying a complete node is safe and its work is idempotent.
- **Workflow recovery node:** useful when failure should be converted into a partial result and the graph should continue.

Avoid retrying an entire agent node if it may repeat non-idempotent tool calls. In this lesson, resilience is applied around specialist invocation, and the investigation aggregator preserves independent outcomes.

## 11. Run it

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/mcp_resilience_advanced/requirements.txt
ollama pull llama3.2:3b
python examples/mcp_resilience_advanced/main.py
```

Ollama must be running locally. You can choose another installed chat model with `OLLAMA_MODEL`.

Run deterministic tests:

```bash
PYTHONPATH=examples/mcp_resilience_advanced python -m unittest discover -s examples/mcp_resilience_advanced/tests -v
```

The unit tests use fake asynchronous operations. They do not require Ollama, network access, or MCP subprocesses. The main program is the live integration example.

## 12. Production checklist

Before using this pattern against real services:

- [ ] Define an overall investigation deadline.
- [ ] Set per-tool and per-specialist timeouts.
- [ ] Retry only explicitly classified transient failures.
- [ ] Ensure retried operations are read-only or idempotent.
- [ ] Add jitter and a strict maximum attempt count.
- [ ] Set circuit-breaker thresholds and cool-down based on measured latency/error rates.
- [ ] Isolate breakers by dependency.
- [ ] Limit concurrency with semaphores or a worker pool.
- [ ] Bound response sizes and sanitize tool output.
- [ ] Emit metrics for attempts, timeouts, breaker state, and partial reports.
- [ ] Log correlation IDs and dependency names without leaking secrets.
- [ ] Test cancellation, server restart, half-open recovery, and concurrent requests.
- [ ] Enforce authorization inside each MCP server; agent tool scoping is not authorization.

Useful metrics include `mcp_tool_calls_total`, `mcp_tool_call_duration_seconds`, `mcp_tool_retries_total`, `mcp_tool_timeouts_total`, `mcp_circuit_breaker_state`, and `investigations_partial_total`. Use bounded labels; do not label metrics with arbitrary user prompts or unbounded service identifiers.

## 13. Exercises

1. Add a separate timeout for each specialist based on its dependency's latency SLO.
2. Make the metrics executor fail twice with `ConnectionError`, then succeed. Verify the retry count.
3. Make the infrastructure executor fail permanently. Verify the logs and metrics evidence remains in the final report.
4. Trigger the circuit breaker, advance a fake clock beyond its cool-down, and verify one HALF_OPEN probe can recover it.
5. Add a semaphore limiting each MCP server to two concurrent operations.
6. Add an overall investigation deadline and prove that retries cannot exceed it.
7. Explain why retrying a timed-out `restart_service` tool is unsafe without idempotency.

## 14. Knowledge check

1. What is the difference between a timeout and an overall deadline?
2. Why should validation and authorization errors not be retried?
3. What are the three circuit-breaker states?
4. Why does a timeout not prove a remote write did not happen?
5. How should an investigation behave when metrics are unavailable but logs succeeded?
6. When would you use a LangGraph `RetryPolicy` instead of a tool-level retry wrapper?

## Completion criteria

You can explain and test timeout behavior, bounded retries, jitter, circuit-breaker transitions, and partial-result aggregation. You can also identify the exact exception types your MCP adapter emits and justify which ones your application retries.

## References

- [LangChain MultiServerMCPClient API](https://reference.langchain.com/python/langchain-mcp-adapters/client/MultiServerMCPClient)
- [LangChain MCP adapter README](https://github.com/langchain-ai/langchain-mcp-adapters)
- [LangGraph RetryPolicy](https://reference.langchain.com/python/langgraph/types/RetryPolicy)
- [Python 3.12 asyncio tasks and timeouts](https://docs.python.org/3.12/library/asyncio-task.html)
