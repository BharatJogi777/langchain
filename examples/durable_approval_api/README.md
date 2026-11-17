# Durable approval API with PostgreSQL

This example upgrades the Lesson 35 approval workflow from in-memory checkpoints to PostgreSQL-backed LangGraph persistence and exposes FastAPI endpoints.

**Safety:** the executor is simulation-only. It does not contact Kubernetes, cloud APIs, or production services.

## Start PostgreSQL

~~~bash
cd examples/durable_approval_api
docker compose up -d
cd ../..
~~~

## Install and run

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/durable_approval_api/requirements.txt
export DATABASE_URL='postgresql://langgraph:local-dev-only-change-me@localhost:5435/langgraph'
uvicorn app.api:app --app-dir examples/durable_approval_api --host 127.0.0.1 --port 8010
~~~

The API creates the application approval/audit tables and LangGraph checkpoint tables on startup. It launches a separate stdio MCP server for the approved operation; both available tools are simulations only.

## Demo identity warning

For local learning only, the API accepts `X-Demo-User` and `X-Demo-Role` headers. These headers are not authentication and must never be used in production. Replace `demo_principal` with the JWT/RBAC principal dependency from Lesson 34. In production, roles/scopes must be loaded from a trusted identity source, not request headers.

## Create a proposal

~~~bash
curl -X POST http://127.0.0.1:8010/v1/approvals \
  -H 'Content-Type: application/json' \
  -H 'X-Demo-User: operator-alex' \
  -H 'X-Demo-Role: operator' \
  -d '{
    "action": "restart_service",
    "service": "checkout-api",
    "environment": "staging",
    "reason": "Repeated health checks are failing.",
    "change_reference": "CHG-2026-1042"
  }'
~~~

The response includes a UUID `request_id`. The workflow is checkpointed and paused before the API returns.

## Inspect the approval

~~~bash
curl http://127.0.0.1:8010/v1/approvals/REQUEST_ID \
  -H 'X-Demo-User: operator-alex' \
  -H 'X-Demo-Role: operator'
~~~

## Approve

~~~bash
curl -X POST http://127.0.0.1:8010/v1/approvals/REQUEST_ID/decision \
  -H 'Content-Type: application/json' \
  -H 'X-Demo-User: commander-sam' \
  -H 'X-Demo-Role: incident_commander' \
  -d '{"decision":"approve","comment":"Reviewed the incident evidence"}'
~~~

Use `decision: reject` to reject. Requester self-approval is denied. Production proposals require the incident commander role.

## Audit

~~~bash
curl http://127.0.0.1:8010/v1/approvals/REQUEST_ID/audit \
  -H 'X-Demo-User: commander-sam' \
  -H 'X-Demo-Role: incident_commander'
~~~

## What persists?

- LangGraph graph state and interrupt/checkpoint data: PostgreSQL checkpointer tables.
- Approval proposal, expiry, decision, reviewer, and status: `approval_requests`.
- Append-only business events: `approval_audit_events`.

The workflow uses a random opaque `thread_id`; the public approval ID is a separate UUID. Never expose another tenant's thread ID or allow callers to resume arbitrary threads.

## Unit tests

The graph tests use an in-memory checkpointer and fake executor; they do not require PostgreSQL:

~~~bash
PYTHONPATH=examples/durable_approval_api python -m pytest -q examples/durable_approval_api/tests
~~~

## Process restart experiment

1. Create a proposal and save its `request_id`.
2. Stop Uvicorn without deleting the Docker volume.
3. Start Uvicorn again with the same `DATABASE_URL`.
4. Submit the decision.
5. The graph resumes from PostgreSQL checkpoint state.

The API and checkpointer share a PostgreSQL pool. The example uses `AsyncPostgresSaver`; `setup()` must run before the graph handles requests. See the official [LangGraph checkpointer reference](https://langchain-ai.github.io/langgraph/reference/checkpoints/).

## Important production hardening still required

This is a teaching skeleton, not a complete production approval service:
- Replace demo headers with Lesson 34 authentication, scopes, service authorization, and tenant isolation.
- The example checks the production-role policy in the same transaction that records the decision; extend this policy with tenant, service, change-window, and risk-level authorization before production use.
- Add a durable outbox/worker for the gap between recording the decision and resuming the graph. A retry/reconciliation worker must find `decision_recorded` rows and safely resume them.
- Add downstream idempotency keys and reconciliation for ambiguous execution outcomes.
- Add rate limits, request correlation, structured logs, metrics, tracing, and encrypted backups.
- Apply data retention/TTL policies to checkpoint and audit tables.
- Keep checkpoint payloads small; store large evidence externally and checkpoint references.
- Protect audit records against modification and restrict access.
- Configure TLS, secret management, least-privilege DB roles, backups, restore drills, and migrations.

The decision endpoint demonstrates the happy path, but durable decision-to-resume recovery needs an outbox/worker before production deployment. The approval decision and LangGraph checkpoint are separate transactions; they cannot be made atomic merely by putting them in the same PostgreSQL database.
