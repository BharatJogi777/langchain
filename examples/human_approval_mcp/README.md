# Human approval before write-capable MCP operations

This is a **simulation-only** example. It does not connect to Kubernetes, cloud APIs, or production infrastructure.

It demonstrates a LangGraph workflow that proposes an operation, pauses using `interrupt()`, waits for a trusted human decision, and only then invokes a write-capable MCP tool. The MCP server simulates the operation and stores an idempotency record in SQLite.

## Architecture

~~~text
Action proposal
      |
      v
Validate schema + calculate idempotency key
      |
      v
LangGraph interrupt()  <---- checkpoint + thread_id
      |
      | external reviewer decision
      v
Validate approver identity/role + separation of duties
      |
      +---- rejected ----> finish (no tool call)
      |
      v approved
Invoke operations MCP tool
      |
      v
Mock operation + SQLite idempotency ledger
~~~

## Requirements

- Python 3.12+
- Install packages from this directory's `requirements.txt`.

## Run

From the repository root:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/human_approval_mcp/requirements.txt
PYTHONPATH=examples/human_approval_mcp python examples/human_approval_mcp/main.py
~~~

The demo proposes a restart of `checkout-api` in staging. Review the displayed proposal, enter `approve` or `reject`, then supply a demo approver identity and role. Use `incident_commander` for production proposals. The demo identity prompt is not authentication; a real API must derive the approver from a verified session/JWT.

The MCP server is launched as a stdio subprocess by the MCP client. It is deliberately a mock server. Its tool descriptions explicitly say SIMULATE and it never invokes a real operations API.

## Tests

~~~bash
PYTHONPATH=examples/human_approval_mcp python -m pytest -q examples/human_approval_mcp/tests
~~~

Tests inject a fake executor, so they do not require Ollama, a Kubernetes cluster, or a running MCP server.

## Production adaptation

- Replace `InMemorySaver` with a durable LangGraph checkpointer, such as the PostgreSQL checkpointer, and use a stable opaque thread ID.
- Persist proposal, approval, reviewer identity, decision, timestamps, execution attempt, and result in an audit store.
- The approval API must authenticate the reviewer, authorize the approval scope, and construct the resume payload server-side. Never accept `approver_id` or `approver_role` from an untrusted request body.
- Enforce separation of duties and environment-specific approval policies in trusted code.
- Enforce authorization again in the MCP server and downstream operations API. A client-side gate alone is insufficient.
- Use an idempotency key accepted by the downstream API. A local ledger cannot guarantee exactly-once behavior for an external side effect.
- Add action allow-lists, parameter validation, dry-run previews, deadlines, concurrency limits, rate limits, audit events, and rollback plans.
- Require stronger multi-party approval for high-risk production actions.

## Safety boundary

The LangGraph interrupt pauses the workflow and checkpointing preserves state until the same thread is resumed. The code after the interrupt is not run until the resume occurs. The node is re-entered when resumed, so do not place irreversible side effects before `interrupt()`. The execution node runs only after approval validation.

The mock executor uses a SQLite transaction and unique idempotency key to demonstrate duplicate suppression. For real infrastructure, the target system must participate in idempotency or you must use a durable operation/outbox/reconciliation design. Do not promise exactly-once side effects from a workflow checkpoint alone.

See [Lesson 35](../../docs/35-human-in-the-loop-safe-mcp-actions.md).
