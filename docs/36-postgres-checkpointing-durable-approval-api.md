# Lesson 36 — Persistent LangGraph Checkpointing with PostgreSQL and Durable Approval APIs

## 1. Learning objectives

After this lesson, you should be able to:

- Explain what a LangGraph checkpoint and thread represent.
- Choose between in-memory, SQLite, and PostgreSQL checkpointers.
- Configure `AsyncPostgresSaver` with a PostgreSQL connection pool.
- Persist a paused approval workflow across API process restarts.
- Separate graph checkpoint data from business approval records and audit events.
- Build proposal, status, decision, and audit endpoints.
- Explain why the approval database and graph checkpoint are not automatically one atomic transaction.
- Design an outbox/recovery worker for production.

## 2. Why in-memory persistence is not enough

Lesson 35 used `InMemorySaver`. It is excellent for local development and tests, but its data lives in the Python process.

Imagine:
1. A proposal is created.
2. The graph pauses at `interrupt()`.
3. The reviewer is notified.
4. The API container is restarted for a deployment.
5. The reviewer submits approval.

If the graph checkpoint existed only in RAM, the process that received the decision cannot restore the paused state.

A persistent checkpointer stores the graph's execution state outside the process. LangGraph identifies a workflow thread with `thread_id`; checkpoints are snapshots of graph state and execution metadata. The checkpointer can retain checkpoint history and pending writes. See the [LangGraph checkpoint reference](https://langchain-ai.github.io/langgraph/reference/checkpoints/) and [persistence guide](https://docs.langchain.com/oss/python/langgraph/persistence).

## 3. Checkpointer options

| Checkpointer | Storage | Best use |
|---|---|---|
| `InMemorySaver` | Process memory | Unit tests and local experiments |
| `SqliteSaver` | SQLite | Small local workflows |
| `PostgresSaver` | PostgreSQL, sync | Persistent production workflows |
| `AsyncPostgresSaver` | PostgreSQL, async | Async FastAPI/LangGraph services |

For our asynchronous FastAPI application, we use `AsyncPostgresSaver`.

Install:

~~~bash
python -m pip install "langgraph-checkpoint-postgres>=3,<4" "psycopg[binary,pool]>=3.2,<4"
~~~

## 4. PostgreSQL checkpointer setup

A minimal async setup looks like this:

~~~python
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

pool = AsyncConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=10,
    open=False,
)

await pool.open()
await pool.wait()

checkpointer = AsyncPostgresSaver(pool)
await checkpointer.setup()

graph = builder.compile(checkpointer=checkpointer)
~~~

Call `setup()` during application startup, before serving requests. Keep the pool open for the lifetime of the application and close it during shutdown. Do not create a new pool for every request.

The checkpointer reference documents async PostgreSQL support and setup/migration behavior. See [AsyncPostgresSaver](https://langchain-ai.github.io/langgraph/reference/checkpoints/).

## 5. What belongs in a checkpoint vs an application table?

Do not confuse workflow persistence with business data persistence.

| Data | Storage |
|---|---|
| Graph node progress | LangGraph checkpoint |
| State at an interrupt | LangGraph checkpoint |
| Graph thread ID | Approval request record |
| Requester identity | Approval request record |
| Proposed action and target | Approval request record |
| Reviewer identity and decision | Approval request record |
| Expiry time and business status | Approval request record |
| Append-only approval events | Audit table |
| Downstream operation ID/result | Operation record |

Why two stores?

The checkpointer is optimized for restoring graph execution. Your business database is optimized for querying approval requests, enforcing uniqueness and state transitions, reporting, and auditing.

A graph checkpoint is not a substitute for an approval table or an audit log.

## 6. Example database model

The example creates two application tables.

### approval_requests

Stores:
- `request_id`: public UUID returned to the API caller.
- `thread_id`: opaque LangGraph thread identifier.
- `requester_id`: authenticated requester.
- Action, service, environment, reason, and change reference.
- Status and expiry.
- Decision, approver ID/role, and reviewer comment.

### approval_audit_events

Stores append-only events:
- `proposal_created`
- `approval_decided`
- `approval_expired`
- `workflow_completed` or `workflow_rejected`

The example records proposal and decision events in database transactions. Production audit storage should have stronger controls: restricted write permissions, immutable retention, backups, and alerting.

## 7. FastAPI endpoints

The example exposes:

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/v1/approvals` | Create proposal and pause graph |
| GET | `/v1/approvals/{request_id}` | Read proposal/status |
| POST | `/v1/approvals/{request_id}/decision` | Approve or reject |
| GET | `/v1/approvals/{request_id}/audit` | Read audit events |
| GET | `/health/live` | Liveness check |

The proposal endpoint generates:
- A public UUID for the approval resource.
- A separate opaque UUID for the LangGraph `thread_id`.

Never use predictable or user-controlled thread IDs as authorization tokens. A thread ID identifies graph state; it does not prove that the caller may access or resume it.

## 8. Decision flow

When the reviewer submits a decision:

1. Authenticate the reviewer.
2. Check the review permission.
3. Load the proposal from the application database.
4. Check requester/reviewer separation of duties.
5. Check environment-specific approval policy.
6. Check expiry.
7. Record the decision under a row lock.
8. Resume the graph with the stored `thread_id`.
9. Let the graph continue to the execution node or rejection path.
10. Record the workflow result and audit event.

The example uses a row-level `SELECT ... FOR UPDATE` and a state transition to `decision_recorded` so concurrent reviewers cannot both win the same pending decision.

## 9. Restart experiment

Start PostgreSQL:

~~~bash
cd examples/durable_approval_api
docker compose up -d
cd ../..
~~~

Install and start the API:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/durable_approval_api/requirements.txt

export DATABASE_URL='postgresql://langgraph:local-dev-only-change-me@localhost:5435/langgraph'

uvicorn app.api:app --app-dir examples/durable_approval_api --host 127.0.0.1 --port 8010
~~~

Create a proposal:

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

Copy the returned `request_id`. Stop the API process with Ctrl+C. Restart it using the same database. Then submit the decision:

~~~bash
curl -X POST http://127.0.0.1:8010/v1/approvals/REQUEST_ID/decision \
  -H 'Content-Type: application/json' \
  -H 'X-Demo-User: commander-sam' \
  -H 'X-Demo-Role: incident_commander' \
  -d '{"decision":"approve","comment":"Reviewed the incident evidence"}'
~~~

The graph restores the checkpoint from PostgreSQL and resumes the paused workflow.

## 10. Important demo authentication limitation

The example accepts `X-Demo-User` and `X-Demo-Role` headers so you can test the workflow with curl. These headers are completely untrusted. They are **not authentication** and must never be used in a deployed system.

Replace the `demo_principal` dependency with the JWT/RBAC authentication and principal resolution from Lesson 34. The API must derive user ID, roles, scopes, and tenant from a verified identity source.

Do not let a client submit `approver_id`, `approver_role`, or `thread_id` in the decision body.

## 11. The hard production problem: decision recorded, graph not resumed

The approval database and LangGraph checkpointer are separate logical operations. Even if both use the same PostgreSQL server, the example does not put both operations inside one shared transaction.

A failure can occur here:

~~~text
1. API records decision in approval_requests
2. API process crashes
3. graph.ainvoke(Command(resume=...)) never runs
~~~

This is why the example stores `decision_recorded` as a durable intermediate status. A production service needs a recovery mechanism.

### Transactional outbox pattern

A robust design adds an outbox table:

~~~sql
CREATE TABLE approval_outbox (
    event_id BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);
~~~

In the same database transaction:
- Update the approval decision.
- Insert the audit event.
- Insert an outbox event requesting graph resumption.

A background worker polls unprocessed outbox events, claims them safely, resumes the graph, and records the result. If the worker crashes, another worker retries.

The worker must be idempotent. It should inspect graph state and operation status before repeating an action. The downstream operation itself must accept an idempotency key or provide a queryable operation ID. Never assume that a timeout means the action did not happen.

## 12. Expiry and stale approvals

The example stores a 30-minute expiry and checks it before accepting a decision. A complete production design also needs:
- A scheduled expiry worker that marks untouched requests expired.
- A cancellation endpoint for the requester or incident commander.
- Revalidation of service health/deployment state before execution.
- A policy version captured with the proposal.
- A rule for evidence that becomes stale after approval.
- A maximum delay between approval and execution.

An approval is valid only for the exact proposal reviewed.

## 13. Connection pool and lifecycle

The example opens one `AsyncConnectionPool` during FastAPI lifespan, initializes the application tables and checkpointer, and closes the pool during shutdown.

Production guidance:
- Set pool sizes based on API concurrency and PostgreSQL limits.
- Configure connection timeouts and health checks.
- Use a dedicated least-privilege database role.
- Enable TLS for remote database connections.
- Keep database credentials in a secret manager.
- Back up and test restore of both checkpoint and business tables.
- Monitor pool exhaustion, checkpoint latency, DB storage, and stale pending approvals.

## 14. Run the unit tests

~~~bash
PYTHONPATH=examples/durable_approval_api python -m pytest -q examples/durable_approval_api/tests
~~~

These tests use an in-memory checkpointer and a fake executor to verify the pause/resume path and rejection behavior. They do not replace the PostgreSQL process-restart experiment above. The full API integration should additionally be tested against a disposable PostgreSQL instance.

## 15. Tests and exercises

The code is a runnable learning skeleton. Add tests before adapting it to production:

1. Proposal is checkpointed and remains pending.
2. Process restarts while an approval is pending; resume succeeds.
3. Non-approver role is denied.
4. Requester cannot approve their own proposal.
5. Production requires the incident commander.
6. Expired approval is rejected.
7. Concurrent approvals result in one accepted decision.
8. API crashes after decision commit; outbox worker resumes later.
9. Worker retries after an ambiguous MCP timeout without duplicating the operation.
10. User A cannot read or resume User B's workflow.

The local executor is simulation-only. No real infrastructure is changed.

## 16. Knowledge check

1. What is the difference between a LangGraph checkpoint and an approval request row?
2. Why should a thread ID not be treated as an authorization credential?
3. Why do we need a separate audit table?
4. What does `SELECT ... FOR UPDATE` protect in the decision endpoint?
5. Why is `decision_recorded` useful as an intermediate state?
6. What failure occurs if the API crashes after storing the decision but before resuming the graph?
7. How does a transactional outbox help?
8. Why does an idempotency key still need downstream support?
9. Why should the system revalidate target state immediately before execution?
10. Which data should be retained or encrypted in checkpoint storage?

## Completion criteria

You can start a proposal, stop and restart the API, resume the same workflow from PostgreSQL, inspect the approval and audit records, and explain the remaining outbox/recovery work required for production.

## References

- [LangGraph checkpoint reference](https://langchain-ai.github.io/langgraph/reference/checkpoints/)
- [LangGraph persistence guide](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [Psycopg connection pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
