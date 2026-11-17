# Lesson 38 — Build an Async PostgreSQL Outbox Worker

Lesson 37 introduced the outbox schema and failure model. This lesson builds an asynchronous worker using Python 3.12, psycopg 3 async connection pooling, PostgreSQL, and an injected LangGraph resumer.

## Architecture

~~~text
Approval API
  | one PostgreSQL transaction
  +--> approval_requests.status = decision_recorded
  +--> approval_outbox.status = pending
                  |
                  v
        Async outbox worker
          1. claim rows (short transaction)
          2. load authoritative approval
          3. validate decision and proposal hash
          4. resume LangGraph thread
          5. fenced completion / retry / dead-letter
~~~

The worker does not trust the outbox payload as the approval authority. It reloads the approval row before resuming.

## Project files

- repository.py: async PostgreSQL pool and atomic claim/complete/retry/dead-letter operations.
- worker.py: poll loop, event validation, handler boundary, bounded retries, graceful cancellation.
- langgraph_adapter.py: adapter around LangGraph Command(resume=...).
- tests/: deterministic tests with fake repository and resumer.
- schema.sql: shared schema from Lesson 37.

## 1. Install and start PostgreSQL

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r examples/transactional_outbox/requirements.txt
docker compose -f examples/transactional_outbox/docker-compose.yml up -d
psql "postgresql://outbox:local_dev_only_change_me@localhost:5437/outbox" -f examples/transactional_outbox/schema.sql
~~~

## 2. Run the worker

~~~bash
export DATABASE_URL='postgresql://outbox:local_dev_only_change_me@localhost:5437/outbox'
export WORKER_ID='local-worker-1'
python examples/transactional_outbox/run_worker.py
~~~

The worker idles when the table is empty. It expects valid approval and outbox rows created by the approval API's atomic transaction. The default demonstration resumer is deliberately a no-op. Connect the real compiled graph only after wiring authenticated approval state and the Lesson 36 checkpointer.

## 3. Understand the claim transaction

The repository executes the FOR UPDATE SKIP LOCKED claim query in a transaction and commits immediately. The graph/MCP call happens after the claim transaction has ended. This prevents slow network operations from holding database row locks.

Each claim receives a fresh UUID claim token. Completion, retry, and dead-letter updates include that token. A worker whose lease has expired cannot overwrite a newer worker's database state.

## 4. Failure behavior

- Empty queue: sleep for the configured poll interval.
- Transient handler exception: reschedule with capped exponential backoff and jitter.
- Permanent/invalid event: move to dead-letter state.
- Worker cancellation: stop claiming new rows; an in-flight claim is left leased and can be reclaimed after expiry.
- Crash after successful graph resume but before marking delivered: event may be delivered again. The graph/action must be idempotent.
- Unknown external action outcome: reconcile by operation ID before retrying. Do not blindly issue another write.

## 5. Run tests

~~~bash
PYTHONPATH=examples/transactional_outbox python -m pytest -q examples/transactional_outbox/tests
~~~

Unit tests use fake dependencies. They do not prove PostgreSQL locking behavior; run a multi-worker integration exercise against local PostgreSQL before relying on the query.

## 6. Production hardening

Before production:
- Use a dedicated DB role with only required privileges and TLS.
- Add tenant-aware predicates to every approval/outbox query.
- Validate event schema versions and payload size.
- Add lease renewal for operations that can exceed the lease duration.
- Add downstream idempotency keys and reconciliation.
- Add metrics for queue depth, oldest event age, lease expiry, retries, dead letters, and processing duration.
- Use a supervisor/container orchestrator for process restart.
- Add graceful shutdown and readiness/liveness probes.
- Encrypt backups and set retention policies.
- Never log raw secrets or untrusted payloads.

## 7. Exercises

1. Run two worker processes and explain why they do not claim the same locked row.
2. Kill a worker after claiming an event; verify it becomes claimable after lease expiry.
3. Force the handler to fail transiently; inspect available_at and attempts.
4. Force a permanent error; verify the event becomes dead.
5. Simulate a successful handler followed by a worker crash before completion. Explain why downstream idempotency is still required.
6. Implement lease renewal for a long-running operation.

## Completion criteria

You can explain every database transaction boundary, run the worker independently from FastAPI, test transient/permanent failures, and explain the duplicate-delivery window. You do not claim exactly-once execution.
