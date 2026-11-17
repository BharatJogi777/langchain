# Lesson 32 — MCP Observability and Distributed Tracing

## 1. Why observability matters

Lesson 31 made MCP-backed specialists resilient. But when an investigation takes 45 seconds, how do you identify whether the delay came from model generation, one specialist, an MCP tool call, retries, or a slow dependency?

Three signals answer different questions:

| Signal | Question | Example |
|---|---|---|
| Logs | What happened? | metrics_agent failed with TimeoutError |
| Metrics | How often and how slowly? | 12% timeout rate; p95 duration 3.2 s |
| Traces | Where did this request spend time? | Investigation → metrics specialist → model/tool |

A correlation ID connects logs for one investigation. A trace ID connects spans in a distributed trace. A span ID identifies one operation within that trace.

## 2. Trace hierarchy

~~~text
investigation.run
├── specialist.execute [logs_agent]
│   ├── model/tool steps (LangSmith if enabled)
│   └── MCP server/tool operation (if separately instrumented)
├── specialist.execute [metrics_agent]
└── specialist.execute [infrastructure_agent]
~~~

This lesson instruments application-level investigation and specialist boundaries with OpenTelemetry. LangChain/LangGraph's internal model and tool execution traces can additionally be sent to LangSmith. These integrations complement each other; enabling both does not automatically guarantee that every span shares one trace ID.

LangChain agents support LangSmith tracing through environment configuration. See [LangChain observability](https://docs.langchain.com/oss/python/langchain/observability) and [LangGraph observability](https://docs.langchain.com/oss/python/langgraph/observability).

## 3. Correlation ID versus trace ID

- **Correlation ID:** application-level identifier for one investigation/request. It can be returned to a caller and included in logs.
- **Trace ID:** OpenTelemetry identifier for one distributed trace.
- **Span ID:** identifier for one operation within that trace.

OpenTelemetry context propagation carries trace context between instrumented processes and services. W3C Trace Context commonly uses the traceparent header for HTTP propagation. See [OpenTelemetry Python propagation](https://opentelemetry.io/docs/languages/python/propagation/) and [context propagation concepts](https://opentelemetry.io/docs/concepts/context-propagation/).

**MCP transport nuance:** do not assume context is automatically propagated through every MCP transport. HTTP transports can propagate trace headers when both sides support instrumentation. For stdio, explicitly pass a correlation identifier through an agreed request field or process metadata and instrument the server separately. This lesson traces the application process and logs a correlation ID; it does not claim automatic cross-process stdio trace propagation.

## 4. Structured logs

Prefer structured fields over free-form strings:

~~~json
{
  "timestamp": "2026-11-18T12:00:00Z",
  "level": "INFO",
  "logger": "devops_agent",
  "message": "specialist completed",
  "correlation_id": "f4a1...",
  "trace_id": "a3c2...",
  "span_id": "1b9d...",
  "specialist": "logs_agent",
  "outcome": "success"
}
~~~

The example uses Python logging with a JSON formatter. It injects the current correlation ID and, when an OpenTelemetry span exists, trace and span IDs.

Never log API keys, tokens, passwords, authorization headers, raw prompts, or unredacted production logs by default. Use protected log sinks, access controls, and retention limits.

## 5. Metrics

The example creates OpenTelemetry instruments for:
- agent.specialist.calls — specialist invocation count.
- agent.specialist.duration — specialist execution duration in seconds.

Use bounded attributes such as specialist name and outcome. Do not use correlation IDs, trace IDs, user IDs, raw prompts, or arbitrary service names as metric labels; high-cardinality labels can overwhelm a metrics backend.

For production, export metrics to an OpenTelemetry Collector or metrics backend and build dashboards for request rate, specialist success/failure rate, p50/p95/p99 duration, retries, timeouts, circuit-breaker opens, partial investigation rate, and model latency/token usage where available.

Metrics answer aggregate questions. A trace explains one slow request.

## 6. OpenTelemetry Python architecture

OpenTelemetry separates the API from the SDK:
- Application code uses the API (trace, metrics).
- The SDK provides providers, processors/readers, and exporters.
- An exporter sends telemetry to a backend or, for local learning, the console.

This lesson configures console exporters so you can see spans and metrics without a hosted service. For production, prefer an OpenTelemetry Collector and a supported backend. See the [OpenTelemetry Python documentation](https://opentelemetry.io/docs/languages/python/) and [manual instrumentation guide](https://opentelemetry.io/docs/languages/python/instrumentation/).

## 7. Project structure

~~~text
examples/mcp_observability/
├── main.py
├── requirements.txt
├── README.md
├── app/
│   ├── __init__.py
│   ├── observability.py
│   ├── resilience.py
│   └── investigation.py
└── tests/
    ├── __init__.py
    └── test_observability.py
~~~

The example reuses the three read-only MCP servers from Lesson 30 and the resilience wrapper from Lesson 31.

## 8. Run the example

From the repository root:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/mcp_observability/requirements.txt
ollama pull llama3.2:3b
python examples/mcp_observability/main.py
~~~

You should see structured JSON log records and OpenTelemetry span/metric output in the terminal. Console output is for local learning, not a production telemetry backend.

Run tests:

~~~bash
PYTHONPATH=examples/mcp_observability python -m unittest discover -s examples/mcp_observability/tests -v
~~~

Tests use fake specialist functions and an in-memory span exporter. They do not require Ollama or running MCP servers.

## 9. Enable LangSmith tracing optionally

If you choose to use LangSmith, configure the API key securely in your local environment:

~~~bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="your-key"
export LANGSMITH_PROJECT="devops-investigation-learning"
~~~

Do not commit the key. Disable tracing or configure redaction when prompts/tool outputs may contain sensitive data. Review privacy, retention, and data residency requirements before sending production traces to a hosted service.

See [LangSmith observability](https://docs.langchain.com/oss/python/langchain/observability) and [LangSmith OpenTelemetry integration](https://docs.smith.langchain.com/observability/how_to_guides/trace_with_opentelemetry).

## 10. Production design decisions

### Sampling
Tracing every request can be expensive at high volume. Use head sampling for baseline traffic and consider tail sampling in a Collector when you want to retain slow or failed traces. Align sampling with incident response and privacy requirements.

### Trace boundaries
Instrument boundaries that answer real debugging questions: API request, investigation orchestration, each specialist, each MCP tool execution, and model calls. Avoid spans for every trivial helper.

### Error status
When a specialist fails, mark its span as an error and record the exception in protected telemetry. The investigation can still return a successful partial response. Distinguish request-level status from child-specialist status.

### Context propagation
For HTTP calls, use supported OpenTelemetry instrumentation or inject/extract W3C trace context. For MCP stdio, design explicit propagation; don't assume HTTP headers exist. For background jobs, persist trace context or a correlation ID in the job envelope where appropriate.

### Reliability
Telemetry must not become a critical dependency. Configure bounded queues, exporter timeouts, batch processors, and graceful shutdown. Exporter failure should generally not crash the business workflow.

## 11. Exercises

1. Add an API request span around a FastAPI endpoint and pass a correlation ID into investigate().
2. Instrument each MCP tool call separately from the specialist agent invocation.
3. Add counters for retries, timeouts, and circuit-breaker opens from Lesson 31.
4. Create a dashboard with specialist call rate and p95 duration.
5. Configure an OpenTelemetry Collector and export traces/metrics to a backend.
6. Enable LangSmith tracing and compare its agent-step view with application-level OpenTelemetry traces.
7. Demonstrate how a partial investigation can have an overall response while one specialist span is marked failed.

## 12. Knowledge check

1. What is the difference between correlation ID, trace ID, and span ID?
2. Why do metrics need bounded-cardinality labels?
3. Why are logs, metrics, and traces complementary?
4. Does LangSmith tracing guarantee that MCP stdio server spans share the same trace ID?
5. Where should a production API create its correlation ID?
6. Why should telemetry exporter failure not normally crash an investigation?

## Completion criteria

You can follow one investigation through logs and traces, interpret specialist latency metrics, explain context propagation boundaries, and configure LangSmith and OpenTelemetry without leaking secrets or creating high-cardinality metrics.

## References

- [LangChain observability](https://docs.langchain.com/oss/python/langchain/observability)
- [LangGraph observability](https://docs.langchain.com/oss/python/langgraph/observability)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [OpenTelemetry Python instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/)
- [OpenTelemetry Python propagation](https://opentelemetry.io/docs/languages/python/propagation/)
- [OpenTelemetry context propagation](https://opentelemetry.io/docs/concepts/context-propagation/)
