# Lesson 22 — MCP Reliability: Timeouts, Retries, and Failure Handling

## Learning objectives

By the end of this lesson, you should be able to:

1. Distinguish connection, timeout, protocol, validation, and application errors.
2. Apply deadlines and bounded retries to read-only MCP operations.
3. Explain exponential backoff and jitter.
4. Limit concurrent calls.
5. Understand circuit breakers and bulkheads.
6. Return honest partial results when one MCP server fails.
7. Test failure paths rather than testing only successful tool calls.

## 1. Why reliability matters

Assume an agent investigates a payment incident using three MCP servers:

- Logs server: responds successfully.
- Infrastructure server: takes 30 seconds.
- Metrics server: is unavailable.

Without resilience controls, the agent can hang, exhaust resources, or fail the entire investigation. Production systems must define how long each operation may take, which failures can be retried, and what to do when a dependency remains unavailable.

Reliability is not achieved by retrying everything. Retrying the wrong operation can duplicate side effects or make an outage worse.

## 2. Understand failure categories

| Failure | Example | Typical handling |
|---|---|---|
| Validation | Empty service name | Fix input; do not retry |
| Authentication/authorization | Invalid token, forbidden scope | Alert/configure access; do not retry blindly |
| Not found | Unknown service | Return a domain result; usually no retry |
| Timeout | Metrics query exceeds deadline | Retry only if safe and budget remains |
| Connection failure | Server process unavailable | Bounded retry for safe operations |
| Rate limited | Server returns a rate-limit response | Respect retry guidance and backoff |
| Internal server error | MCP server crashes during execution | Investigate; retry only if classified transient and operation is safe |
| Protocol/schema error | Invalid tool response | Treat as integration defect; do not retry blindly |

A timeout does not prove that the remote operation did not execute. The server may have completed the operation but the response may have been lost. This is especially important for write operations.

## 3. Timeout versus deadline

A **timeout** limits one operation. A **deadline** limits the complete workflow.

For example:

- One tool call may take at most 5 seconds.
- An investigation may take at most 20 seconds.
- Retries and subsequent tool calls must fit inside the remaining investigation budget.

Do not give every retry a fresh, unlimited budget. The remaining time should be considered before starting another attempt.

## 4. Retry only safe, transient failures

A retry policy needs all of these:

- A known set of transient errors.
- A maximum number of attempts.
- A per-attempt timeout.
- A bounded delay between attempts.
- A total deadline or request budget.
- An operation that is safe to repeat, or an idempotency mechanism.

Good candidates: read-only health checks and read-only metrics queries.

Dangerous candidates: restart service, deploy release, create payment, delete resource. These may have succeeded even when the response was lost. Do not automatically retry them unless the operation has a well-designed idempotency key and the server enforces it.

## 5. Exponential backoff and jitter

A common backoff schedule grows the delay after each failure:

~~~text
delay = min(max_delay, base_delay * 2 ** (attempt - 1))
actual_delay = random(0, delay)
~~~

Example with base delay 0.5 seconds and maximum 4 seconds:

| Attempt | Maximum backoff before attempt |
|---|---:|
| 1 | 0 seconds |
| 2 | 0.5 seconds |
| 3 | 1 second |
| 4 | 2 seconds |
| 5 | 4 seconds |

Add random jitter so many clients do not retry at exactly the same time. Production systems should also honor server-provided retry guidance when the protocol or transport exposes it.

## 6. Implement a reusable async retry helper

The helper below is deliberately transport-independent. It can wrap an asynchronous read operation. It does not assume that every MCP adapter exception is a ConnectionError; inspect the exceptions exposed by your pinned adapter and map only known transient failures into the retryable set.

Create resilience.py:

~~~python
import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def invoke_read_with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    timeout_seconds: float = 5.0,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.25,
    max_delay_seconds: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        OSError,
    ),
) -> T:
    """Invoke a repeatable read operation with a timeout and bounded retries."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if base_delay_seconds < 0 or max_delay_seconds < 0:
        raise ValueError("retry delays cannot be negative")

    for attempt in range(1, max_attempts + 1):
        try:
            return await asyncio.wait_for(
                operation(),
                timeout=timeout_seconds,
            )
        except retryable_exceptions:
            if attempt == max_attempts:
                raise

            backoff = min(
                max_delay_seconds,
                base_delay_seconds * (2 ** (attempt - 1)),
            )
            await asyncio.sleep(random.uniform(0, backoff))

    raise RuntimeError("unreachable")
~~~

Important notes:

- This helper is for repeatable reads, not arbitrary tools.
- It retries only the exception types configured by the caller.
- Do not add a broad except Exception and retry everything.
- asyncio.wait_for cancels the local awaitable on timeout, but cancellation does not guarantee that a remote server stopped processing the request.
- A production application should enforce an overall request deadline too.

## 7. Use the helper at the tool boundary

For a direct asynchronous operation:

~~~python
async def read_service_health(service: str) -> dict:
    # Replace this function with the actual read-only backend operation.
    return {"service": service, "status": "healthy"}


async def main():
    result = await invoke_read_with_retry(
        lambda: read_service_health("payment-service"),
        timeout_seconds=3,
        max_attempts=3,
    )
    print(result)
~~~

When integrating with MCP, identify the exact exception types produced by the version of langchain-mcp-adapters and MCP SDK that you pinned. Wrap the adapter call at a trusted application boundary and map only documented transient transport failures to retryable exceptions.

Do not assume every MCP error is transient. Tool input errors, authorization errors, and business-level results should not be retried.

## 8. Bound concurrency

An agent may request several tools close together. Without a limit, a burst of calls can overload a downstream API or database.

Use an asyncio semaphore around calls to a constrained dependency:

~~~python
import asyncio

metrics_semaphore = asyncio.Semaphore(4)


async def bounded_metrics_read(operation):
    async with metrics_semaphore:
        return await operation()
~~~

The value 4 is only an example. Choose limits based on downstream capacity, rate limits, latency, and load testing. Use separate limits for independent dependencies when their capacities differ.

## 9. Circuit breaker

A circuit breaker prevents repeated calls to a dependency that is consistently failing.

It typically has three states:

1. **Closed:** calls are allowed; failures are counted.
2. **Open:** calls are rejected quickly for a cool-down period.
3. **Half-open:** a limited probe is allowed to test recovery.

A circuit breaker is different from a retry:

- Retry asks: "Should I try this operation again?"
- Circuit breaker asks: "Should I call this dependency at all right now?"

Use a mature, tested implementation or a well-reviewed internal abstraction. Define thresholds, cool-down, half-open probe limits, and per-dependency isolation. Avoid implementing a global breaker that lets one failing server block every other server.

## 10. Bulkheads and partial results

A bulkhead isolates failures so one dependency cannot consume all application resources.

For an investigation workflow, collect independent results separately:

~~~python
import asyncio


async def collect_one(name, operation):
    try:
        result = await operation()
        return {"dependency": name, "ok": True, "data": result}
    except Exception as exc:
        # Log the exception with a correlation ID in production.
        # Return a safe summary; do not expose secrets or stack traces to the model.
        return {
            "dependency": name,
            "ok": False,
            "error_type": type(exc).__name__,
        }


async def collect_evidence(logs_call, health_call, metrics_call):
    return await asyncio.gather(
        collect_one("logs", logs_call),
        collect_one("infrastructure", health_call),
        collect_one("metrics", metrics_call),
    )
~~~

This example intentionally converts each dependency failure into a result so the other evidence can still be returned. In production, do not silently swallow exceptions: log them, attach trace/correlation IDs, record latency, and classify the failure.

The agent's system instructions should require it to:

- Identify which sources succeeded and failed.
- Distinguish unavailable evidence from evidence of absence.
- Avoid inventing missing metrics or log events.
- State when the investigation is incomplete.
- Avoid recommending a remediation based on missing evidence alone.

## 11. Overall deadline

A request-level deadline is a budget shared by all work. For example, if an investigation has a 20-second deadline, a 5-second retry should not begin when only 1 second remains.

Use an application-level deadline and pass the remaining budget into downstream operations. In Python 3.11+, asyncio.timeout(total_seconds) can bound a block of asynchronous work:

~~~python
import asyncio


async def investigate():
    async with asyncio.timeout(20):
        # Run bounded evidence collection and synthesis here.
        ...
~~~

Handle the resulting TimeoutError at the request boundary and return a controlled response. The example is a deadline boundary, not a complete cancellation strategy for remote systems.

## 12. Tests: verify failures, not just success

A retry helper should be tested for:

- Success on the first attempt.
- A transient failure followed by success.
- Exhaustion after the configured maximum attempts.
- A timeout.
- A non-retryable exception that fails immediately.
- Invalid configuration.

A minimal standard-library test is included in examples/mcp_resilience/test_resilience.py. Run it with:

~~~bash
python -m unittest discover -s examples/mcp_resilience -p "test_*.py" -v
~~~

## 13. Production checklist

- [ ] Every network/tool operation has a bounded timeout.
- [ ] The incoming request has an overall deadline.
- [ ] Retries are bounded and limited to classified transient failures.
- [ ] Write operations are not blindly retried.
- [ ] Idempotency is enforced server-side where required.
- [ ] Backoff includes jitter.
- [ ] Concurrency is bounded per downstream dependency.
- [ ] Repeated failures can open a circuit breaker.
- [ ] Independent dependencies are isolated.
- [ ] Partial results are clearly marked as partial.
- [ ] Logs and traces contain correlation IDs and safe error metadata.
- [ ] Secrets and raw internal stack traces are not sent to the LLM.
- [ ] Failure paths are covered by automated tests.

## 14. Exercises

1. Run the retry helper tests.
2. Change the fake operation to fail twice and then succeed.
3. Set max_attempts=1; verify that no retry occurs.
4. Add a fake operation that always times out.
5. Add a non-retryable ValueError; verify it fails immediately.
6. Add a semaphore and simulate concurrent requests.
7. Design a partial investigation response when logs succeed but metrics fail.
8. Explain why a restart-service tool must not use the same retry policy as a read-only health-check tool.

## 15. Knowledge check

1. Why is retrying every exception dangerous?
2. What is the difference between a per-tool timeout and an overall deadline?
3. Why do we add jitter to exponential backoff?
4. Why can a timed-out write operation still have completed on the server?
5. What problem does a circuit breaker solve that retries do not?
6. How does a bulkhead help when one MCP server is unhealthy?
7. Why must an agent say that evidence is unavailable rather than infer that no issue exists?

**Completion criteria:** You can implement and test bounded retries for a safe read operation, explain why a write is different, and design a partial-result response that never fabricates missing evidence.

## Next lesson

Continue with production agent orchestration: explicit workflow state, deterministic steps, branching, retries, human approval, and persistence using LangGraph.
