# Lesson 33 — Integrating LangChain Observability with FastAPI

## 1. Objective

In Lesson 32, we instrumented the investigation workflow. Now we expose it as an HTTP API and connect the HTTP request lifecycle to the same correlation and telemetry model.

A production request should have a clear path:

~~~text
HTTP client
  |
  v
FastAPI middleware
  |-- validate/create X-Correlation-ID
  |-- record HTTP request count and duration
  |-- OpenTelemetry HTTP server span
  |
  v
POST /v1/investigations
  |
  v
Investigation service
  |-- logs specialist
  |-- metrics specialist
  |-- infrastructure specialist
  |
  v
JSON report + X-Correlation-ID
~~~

The example reuses the Lesson 30 MCP servers, Lesson 31 resilience executor, and Lesson 32 observability/investigation modules.

## 2. Why the API layer needs its own instrumentation

Specialist spans alone cannot answer all API questions. The API layer needs to show:
- How many HTTP requests arrived?
- Which routes are slow?
- How many requests returned 4xx or 5xx?
- Did the request fail before the investigation started?
- Which API request produced a given specialist trace?

FastAPI middleware executes around request handling and can inspect or modify the response. OpenTelemetry's FastAPI instrumentation adds HTTP server spans. The application middleware in this example separately records request count and duration with bounded attributes.

References: [FastAPI middleware](https://fastapi.tiangolo.com/tutorial/middleware/), [FastAPI OpenTelemetry guidance](https://fastapi.tiangolo.com/advanced/opentelemetry/), and [OpenTelemetry FastAPI instrumentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html).

## 3. API contract

### POST /v1/investigations

Request:

~~~json
{
  "service": "checkout-api",
  "incident": "Checkout requests are timing out after a deployment",
  "task": "Inspect logs, latency, health, and recent deployments"
}
~~~

Response:

~~~json
{
  "service": "checkout-api",
  "report": "DevOps investigation report ...",
  "partial": true,
  "evidence": {
    "logs_agent": "..."
  },
  "unavailable": {
    "metrics_agent": "TimeoutError"
  },
  "correlation_id": "..."
}
~~~

A partial report is still a valid investigation response. An unavailable specialist is never interpreted as evidence that the service is healthy.

### Health endpoints

- `GET /health/live`: process is running.
- `GET /health/ready`: runtime dependencies have completed initialization.

Liveness and readiness answer different questions. Do not make liveness depend on an optional downstream service; otherwise a temporary dependency outage can trigger unnecessary process restarts.

## 4. Correlation ID middleware

The API accepts an optional `X-Correlation-ID` request header. It accepts only a small, bounded character set and maximum length. Invalid values are replaced with a generated identifier.

Why validate it?
- Prevent unbounded log field sizes.
- Avoid control characters and log injection.
- Prevent arbitrary user input from becoming a high-cardinality metric label.

The middleware places the ID in a context variable for the duration of the request, returns it in the response header, and includes it in the JSON response.

Do not use correlation IDs as metric labels. They belong in logs and traces, not metric dimensions.

## 5. HTTP metrics

The example records:
- `http.server.requests`: request count.
- `http.server.duration`: request duration in seconds.

Attributes are limited to HTTP method, route template, and status class. Route templates are preferable to raw URL paths because paths can contain unbounded IDs.

OpenTelemetry FastAPI instrumentation creates HTTP spans. The middleware's metrics are explicit application instruments. In a production deployment, confirm which HTTP metrics your instrumentation/backend already supplies to avoid duplicate instruments.

## 6. Lifespan and resource management

FastAPI lifespan is the correct place to initialize and close application resources:
- Build specialist agents and MCP tool wrappers once per process.
- Store the runtime on `app.state`.
- Flush and shut down telemetry providers during shutdown.
- Close any clients/resources whose API explicitly requires closing.

Do not initialize an Ollama model call or MCP server connection on every HTTP request. Create the reusable runtime during startup and execute it per request.

The example's runtime factory discovers the MCP tools at startup. If discovery fails for one server, it registers an unavailable specialist so other specialists can still run. This preserves partial-result behavior.

## 7. Project structure

~~~text
examples/fastapi_agent_api/
├── main.py
├── requirements.txt
├── README.md
├── app/
│   ├── __init__.py
│   ├── api.py
│   └── runtime.py
└── tests/
    ├── __init__.py
    └── test_api.py
~~~

## 8. Install and run

From the repository root:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/fastapi_agent_api/requirements.txt
ollama pull llama3.2:3b
uvicorn main:app --app-dir examples/fastapi_agent_api --host 127.0.0.1 --port 8000
~~~

Submit an investigation:

~~~bash
curl -X POST http://127.0.0.1:8000/v1/investigations \
  -H 'Content-Type: application/json' \
  -H 'X-Correlation-ID: incident-checkout-001' \
  -d '{
    "service": "checkout-api",
    "incident": "Checkout requests are timing out after a deployment",
    "task": "Inspect logs, latency, health, and recent deployments"
  }'
~~~

Inspect health:

~~~bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
~~~

Run tests without Ollama or MCP:

~~~bash
PYTHONPATH=examples/fastapi_agent_api:examples/mcp_observability:examples/mcp_resilience_advanced \
python -m pytest -q examples/fastapi_agent_api/tests
~~~

## 9. Optional LangSmith tracing

LangChain agents support LangSmith tracing. Enable it through environment configuration before starting Uvicorn:

~~~bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="your-key"
export LANGSMITH_PROJECT="devops-investigation-api"
~~~

Keep credentials out of source control. Review prompt/tool-output redaction, data residency, access controls, and retention before enabling hosted tracing with production data. See [LangChain observability](https://docs.langchain.com/oss/python/langchain/observability).

## 10. Production hardening checklist

### API and request validation
- Authenticate callers and authorize access to each target service.
- Apply request size limits, rate limits, and concurrency limits.
- Validate service names against an allow-list; never let a caller choose arbitrary shell commands or MCP server addresses.
- Add an overall request deadline, not only per-tool timeouts.
- Define whether clients can poll a long-running investigation instead of holding an HTTP connection open.

### Reliability
- Use the Lesson 31 retry and circuit-breaker boundaries.
- Bound the number of simultaneous investigations.
- Return partial evidence with explicit unavailable-specialist metadata.
- Do not retry non-idempotent operations automatically.
- Handle client disconnect and cancellation intentionally.

### Observability
- Keep route labels templated and metric cardinality bounded.
- Correlate HTTP logs with specialist spans.
- Avoid logging prompts, secrets, raw headers, or sensitive tool output.
- Export through a Collector with batching, timeouts, and controlled retention.
- Avoid duplicate HTTP metrics when framework instrumentation already emits them.

### Deployment
- Run Uvicorn with a deliberate worker count and resource budget.
- Remember each worker has its own in-memory circuit breakers and model/runtime objects.
- Use shared coordination for breakers/rate limits when cross-worker consistency is required.
- Set graceful shutdown timeouts so active requests and telemetry can finish safely.
- Add readiness checks for required startup resources, not every optional dependency.

## 11. Exercises

1. Add authentication middleware and protect `POST /v1/investigations`.
2. Add a service allow-list and reject unknown service names with HTTP 422.
3. Add a global investigation deadline and distinguish it from per-tool timeouts.
4. Add request concurrency limits and test overload behavior.
5. Add a `GET /v1/investigations/{id}` endpoint backed by a persistent job store.
6. Add a Docker Compose deployment with an OpenTelemetry Collector.
7. Add integration tests that run the MCP subprocesses but still use a deterministic fake chat model.

## 12. Knowledge check

1. Why should a correlation ID be validated before logging?
2. Why are route templates better metric labels than raw paths?
3. What is the difference between liveness and readiness?
4. Why should MCP tool discovery happen at application startup rather than per request?
5. Why can a partial specialist failure still produce HTTP 200?
6. Why does each Uvicorn worker have a separate in-memory circuit breaker?

## Completion criteria

You can run the FastAPI service, submit an investigation, follow its correlation ID through structured logs, identify HTTP and specialist spans, explain startup/shutdown behavior, and describe the production controls required before exposing an agent API publicly.

## References

- [FastAPI middleware](https://fastapi.tiangolo.com/tutorial/middleware/)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [FastAPI OpenTelemetry guidance](https://fastapi.tiangolo.com/advanced/opentelemetry/)
- [OpenTelemetry FastAPI instrumentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html)
- [OpenTelemetry Python instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/)
- [LangChain observability](https://docs.langchain.com/oss/python/langchain/observability)
