# Secured FastAPI DevOps investigation agent API

This example exposes the multi-MCP DevOps investigation workflow through FastAPI. It combines:

- Lesson 31 timeouts, retries, and circuit breakers.
- Lesson 32 structured logs and OpenTelemetry.
- Lesson 33 FastAPI middleware, health endpoints, and lifespan.
- Lesson 34 JWT authentication, RBAC scopes, service-level authorization, MCP tool-boundary checks, and rate limiting.

## Requirements

- Python 3.12+
- Ollama running locally with `llama3.2:3b` (or set `OLLAMA_MODEL`)
- The Lesson 30 MCP server files in this repository

## Install

From the repository root:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/fastapi_agent_api/requirements.txt
~~~

## Configure local demo credentials

Generate a signing secret and set three demo passwords. The values below are prompts, not passwords to commit:

~~~bash
export JWT_SECRET_KEY="$(openssl rand -hex 32)"
read -s DEMO_ADMIN_PASSWORD
export DEMO_ADMIN_PASSWORD
read -s DEMO_INVESTIGATOR_PASSWORD
export DEMO_INVESTIGATOR_PASSWORD
read -s DEMO_VIEWER_PASSWORD
export DEMO_VIEWER_PASSWORD
~~~

The demo identities have these permissions:

| Username | Role | Allowed services |
|---|---|---|
| admin | admin | all services |
| investigator | investigator | checkout-api, payments-api |
| viewer | viewer | checkout-api (read scope only; no investigation endpoint yet) |

Passwords are hashed with Argon2id when the demo app initializes. The user store is in-memory and resets on restart. Replace it with a persistent identity provider or database for production.

## Run

~~~bash
ollama pull llama3.2:3b
uvicorn main:app --app-dir examples/fastapi_agent_api --host 127.0.0.1 --port 8000
~~~

## Obtain an access token (local demo only)

~~~bash
curl -X POST http://127.0.0.1:8000/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'username=investigator' \
  --data-urlencode 'password=YOUR_INVESTIGATOR_PASSWORD'
~~~

Copy `access_token` from the response.

## Start an authorized investigation

~~~bash
curl -X POST http://127.0.0.1:8000/v1/investigations \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'X-Correlation-ID: incident-checkout-001' \
  -d '{
    "service": "checkout-api",
    "incident": "Checkout requests are timing out after a deployment",
    "task": "Inspect logs, latency, health, and recent deployments"
  }'
~~~

Try the same token with `orders-api`. The investigator role is not assigned that service and should receive HTTP 403.

Health endpoints:

~~~bash
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
~~~

## Run tests without Ollama or MCP

~~~bash
PYTHONPATH=examples/fastapi_agent_api python -m pytest -q examples/fastapi_agent_api/tests
~~~

The tests inject a fake investigator and do not launch Ollama or MCP subprocesses.

## Important security notes

- The `/token` password endpoint is a local learning mechanism. For real browser/mobile/enterprise applications, prefer OIDC Authorization Code with PKCE; use an appropriate client-credentials flow for machine-to-machine clients.
- JWTs are signed, not encrypted. Do not place secrets or private data in claims.
- The demo user database is in-memory. Use a persistent identity provider/user store in production.
- The in-process rate limiter is per worker. Use an API gateway or shared Redis-backed limiter across workers/replicas.
- The MCP runtime uses an explicit tool-name allow-list and wraps every tool so its `service` argument must match the service authorized by the API.
- Also enforce authorization at the MCP server/downstream service. Do not rely on a system prompt as a security boundary.
- The example tools are read-only. Add human approval and stronger authorization before introducing write-capable tools.
- Add TLS, authentication integration, tenant isolation, concurrency limits, an overall deadline, secret-manager integration, and audit logging before public deployment.

See:
- [Lesson 33 — FastAPI agent API](../../docs/33-fastapi-langchain-agent-api.md)
- [Lesson 34 — Production API security](../../docs/34-production-agent-api-security.md)
