# FastAPI DevOps investigation agent API

This example exposes the multi-MCP DevOps investigation workflow through FastAPI. It reuses the Lesson 30 MCP servers, Lesson 31 resilience executor, and Lesson 32 observability pattern (copied into this example so its `app` package is self-contained).

## Requirements

- Python 3.12+
- Ollama running locally with `llama3.2:3b` (or set `OLLAMA_MODEL`)
- The Lesson 30 MCP server files in this repository

## Install and run

From the repository root:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/fastapi_agent_api/requirements.txt
ollama pull llama3.2:3b
uvicorn main:app --app-dir examples/fastapi_agent_api --host 127.0.0.1 --port 8000
~~~

## Call the API

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

Health endpoints:

~~~bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
~~~

## Run tests without Ollama or MCP

~~~bash
PYTHONPATH=examples/fastapi_agent_api python -m pytest -q examples/fastapi_agent_api/tests
~~~

Tests inject a fake investigator and use FastAPI TestClient. They do not start MCP subprocesses or call a model.

## Optional LangSmith tracing

Set before launching Uvicorn:

~~~bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="your-key"
export LANGSMITH_PROJECT="devops-investigation-api"
~~~

Never commit credentials. Review prompt/tool-output redaction and retention before enabling hosted tracing for production data.

## Important notes

- The API runtime is built once in FastAPI lifespan, not on every request.
- The supplied correlation ID is validated; invalid values are replaced.
- The response includes the correlation ID in both the JSON body and response header.
- Partial specialist results are returned as partial success with explicit unavailable-specialist details.
- HTTP metrics use bounded route templates and status classes.
- OpenTelemetry exporters are configured for console learning. Replace them with a Collector/backend in production.
- Add authentication, authorization, rate limiting, request concurrency limits, an overall deadline, and a service allow-list before exposing this API publicly.

See [Lesson 33](../../docs/33-fastapi-langchain-agent-api.md) for the full walkthrough.
