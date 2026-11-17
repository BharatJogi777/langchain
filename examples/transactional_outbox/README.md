# Transactional Outbox — Lesson 37

This lab demonstrates outbox schema design, safe claiming, bounded retry scheduling, and lease recovery. It uses a PostgreSQL schema and deterministic unit-test helpers. It does not connect to production services or execute infrastructure changes.

See ../../docs/37-transactional-outbox-durable-agent-workers.md for the architecture and failure analysis.

## Start PostgreSQL

~~~bash
docker compose up -d
~~~

Apply schema:

~~~bash
psql "postgresql://outbox:local_dev_only_change_me@localhost:5437/outbox" -f schema.sql
~~~

## Install and test

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=examples/transactional_outbox python -m pytest -q examples/transactional_outbox/tests
~~~

The outbox provides at-least-once delivery, not exactly-once external execution. A real MCP/downstream operation needs a durable idempotency key and reconciliation for ambiguous outcomes.
