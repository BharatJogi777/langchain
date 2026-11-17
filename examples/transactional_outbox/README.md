# Transactional Outbox — Lessons 37 and 38

This lab contains the PostgreSQL outbox schema, async repository, standalone worker, LangGraph resume adapter, and unit tests. It uses mock/no-op resumption by default; it does not execute real infrastructure changes.

## Start PostgreSQL

~~~bash
docker compose up -d
psql "postgresql://outbox:local_dev_only_change_me@localhost:5437/outbox" -f schema.sql
~~~

## Install and test

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=examples/transactional_outbox python -m pytest -q examples/transactional_outbox/tests
~~~

## Run the worker

~~~bash
export DATABASE_URL='postgresql://outbox:local_dev_only_change_me@localhost:5437/outbox'
export WORKER_ID='local-worker-1'
python examples/transactional_outbox/run_worker.py
~~~

The no-op resumer is a safe placeholder. Replace it with LangGraphApprovalResumer(compiled_graph) after wiring the real Lesson 36 graph and PostgreSQL checkpointer. The worker expects an approval row and matching outbox event created by the API's atomic approval transaction.

The worker provides at-least-once delivery. It does not guarantee exactly-once external side effects. Use downstream idempotency keys and reconcile uncertain outcomes before retrying.
