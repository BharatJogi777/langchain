# Lesson 37 — Transactional Outbox and Durable Background Workers for AI Agents

## Learning objectives

Learn the dual-write problem, atomic outbox writes, concurrent claiming with PostgreSQL FOR UPDATE SKIP LOCKED, leases, bounded retries, dead-letter handling, idempotent workflow resumption, and recovery from uncertain external side effects.

## 1. The dual-write problem

Lesson 36 has a dangerous failure window:

~~~text
1. API records approval in PostgreSQL.
2. Transaction commits.
3. API resumes the LangGraph thread.
4. Process crashes between steps 2 and 3.
~~~

The approval is durable, but the graph remains paused. Reversing the order is also unsafe: the graph could resume before the approval commits.

## 2. Transactional Outbox pattern

Persist the business decision and the intent to resume the workflow in the same database transaction:

~~~sql
BEGIN;

UPDATE approval_requests
SET status = 'decision_recorded',
    decision = :decision,
    decided_by = :reviewer_id,
    decided_at = now()
WHERE request_id = :request_id
  AND status = 'pending';

-- Application must verify exactly one row was updated.

INSERT INTO approval_outbox (
    event_id, request_id, event_type, payload, status,
    available_at, attempts, created_at
)
VALUES (
    :event_id, :request_id, 'resume_approval_workflow',
    :payload, 'pending', now(), 0, now()
);

INSERT INTO approval_audit_events (...);

COMMIT;
~~~

If the transaction rolls back, neither the decision nor the event exists. If it commits, a worker can find the event even if the API process dies.

The outbox does not execute the action. It records durable intent.

## 3. Outbox schema

See the runnable schema in examples/transactional_outbox/schema.sql. It includes:
- Unique event ID and request ID.
- Event type and JSON payload.
- Pending, processing, delivered, and dead states.
- Attempt count and next available time.
- Worker identity, lease expiry, and claim token.
- A uniqueness constraint to prevent duplicate resume events.

Use a generation/version in the uniqueness key if a business request can legitimately produce multiple events of the same type.

## 4. Claim work safely

Multiple worker processes can poll the same table. Claim rows inside a short transaction:

~~~sql
WITH candidates AS (
    SELECT event_id
    FROM approval_outbox
    WHERE (
        status = 'pending'
        OR (status = 'processing' AND locked_until < now())
    )
      AND available_at <= now()
    ORDER BY available_at, created_at
    FOR UPDATE SKIP LOCKED
    LIMIT :batch_size
)
UPDATE approval_outbox AS o
SET status = 'processing',
    locked_by = :worker_id,
    claim_token = :claim_token,
    locked_until = now() + interval '60 seconds',
    attempts = attempts + 1
FROM candidates
WHERE o.event_id = candidates.event_id
RETURNING o.*;
~~~

SKIP LOCKED allows concurrent workers to skip rows already claimed by another transaction. Commit the claim before doing slow graph or MCP work. Never hold row locks during a network call.

A lease lets another worker recover an event if the first worker dies. A lease does not prove the old worker stopped; use fencing and idempotency.

## 5. Worker lifecycle

A worker should:
1. Claim a bounded batch.
2. Validate event type and payload schema.
3. Reload the authoritative approval record.
4. Verify decision, status, expiry, tenant, and proposal hash.
5. Resume the correct LangGraph thread.
6. Persist the workflow/operation result and mark the event delivered.
7. On transient failure, schedule a bounded retry.
8. On permanent failure or exhausted attempts, mark dead and alert.

The outbox payload is a wake-up hint, not the source of approval truth. Reload the business record before resuming.

## 6. Retry with full jitter

Immediate retries can overload an unhealthy dependency. Use capped exponential backoff with jitter:

~~~python
import random

def retry_delay_seconds(attempt: int) -> float:
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    ceiling = min(300.0, 2.0 * (2 ** min(attempt - 1, 30)))
    return random.uniform(0.0, ceiling)
~~~

Classify failures:
- Transient: temporary database/network failure, rate limit, service unavailable.
- Permanent: invalid payload, unsupported event, expired or revoked approval.
- Ambiguous side effect: timeout after the external request may have completed.

Ambiguous outcomes require reconciliation, not blind retry.

## 7. At-least-once delivery and idempotency

A worker may resume the graph successfully and crash before marking the outbox row delivered. The event will be retried. Therefore the outbox gives durable at-least-once delivery, not exactly-once execution.

Use:
- Unique event IDs and database constraints.
- Compare-and-set state transitions.
- Stable operation IDs and downstream idempotency keys.
- Downstream operation lookup/reconciliation.
- Duplicate-safe graph nodes and MCP tools.

A LangGraph checkpoint cannot atomically commit an unrelated infrastructure side effect.

## 8. Lease fencing

A completion update should match the current lease token:

~~~sql
UPDATE approval_outbox
SET status = 'delivered',
    delivered_at = now(),
    locked_by = NULL,
    locked_until = NULL
WHERE event_id = :event_id
  AND status = 'processing'
  AND locked_by = :worker_id
  AND claim_token = :claim_token;
~~~

If zero rows are updated, the worker lost its lease and must not overwrite the newer worker's state. A stale worker may still be running; downstream idempotency or fencing is required to protect external side effects.

## 9. Dead-letter handling

After the maximum retry count, mark the event dead, save a sanitized error category, and alert an operator. Provide a reviewed replay process that creates a new auditable attempt or event generation. Never silently erase delivery history.

Do not store bearer tokens, passwords, or secret-bearing exception text in error fields.

## 10. Failure recovery matrix

| Failure | Expected recovery |
|---|---|
| API dies before commit | No decision or outbox event; client may retry |
| API dies after commit | Worker discovers pending event |
| Worker dies before resume | Lease expires; another worker claims |
| Worker dies after resume | Duplicate delivery; idempotent processing |
| MCP times out with unknown result | Reconcile downstream operation |
| Poison event exhausts retries | Dead-letter and alert |
| Old worker finishes after lease expiry | Fencing token rejects stale update |

## 11. Observability

Track pending event count, age of oldest event, expired leases, attempts per event, dead-letter count, resume latency, duplicate delivery, unknown operation outcomes, and worker heartbeat.

Keep event ID, approval request ID, LangGraph thread ID, operation ID, and trace ID distinct. Do not log secrets or full prompt/tool payloads.

## 12. Lab

See examples/transactional_outbox:
- PostgreSQL Compose service.
- Outbox schema and claim query.
- Retry/backoff and lease helpers.
- Unit tests for bounded retry and expired leases.

Start PostgreSQL:

~~~bash
docker compose -f examples/transactional_outbox/docker-compose.yml up -d
~~~

Install and test:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r examples/transactional_outbox/requirements.txt
PYTHONPATH=examples/transactional_outbox python -m pytest -q examples/transactional_outbox/tests
~~~

The lab is a controlled simulation. It does not connect to production infrastructure or execute real MCP write operations.

## 13. Exercises

1. Explain the dual-write failure window in Lesson 36.
2. Why must the approval update and outbox insert share a transaction?
3. Why is SKIP LOCKED useful for concurrent workers?
4. Why should graph resumption happen outside the claim transaction?
5. What happens if a worker crashes after resuming but before marking delivery?
6. Why does the outbox provide at-least-once rather than exactly-once delivery?
7. Explain the difference between a lease and a fencing token.
8. How should the system handle an ambiguous MCP timeout?
9. Design a safe operator replay process for dead-letter events.

## Completion criteria

You can implement the outbox transaction, claim rows concurrently, use leases and fencing, apply bounded retries, handle dead letters, and demonstrate worker recovery. You can also explain why external operations need their own idempotency and reconciliation.
