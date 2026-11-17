# Lesson 35 — Human-in-the-Loop Approval and Safe Write-Capable MCP Tools

## 1. Learning objectives

By the end of this lesson, you should be able to:

- Explain why a model-generated tool call is a proposal, not permission.
- Pause a LangGraph workflow with `interrupt()`.
- Persist the paused state with a checkpointer and resume using the same `thread_id`.
- Validate a reviewer decision in trusted Python code.
- Enforce separation of duties and environment-specific approval policy.
- Execute an MCP operation only after approval.
- Use an idempotency key to reduce duplicate side effects.
- Explain why a workflow checkpoint does not guarantee exactly-once execution.
- Design durable approval, audit, and recovery behavior for production.

## 2. The problem: agents can request dangerous actions

A read-only DevOps agent can inspect logs and metrics. A write-capable agent might also:
- Restart a service.
- Roll back a deployment.
- Scale a workload.
- Change a feature flag.
- Disable an unhealthy worker.

These operations can cause outages or data loss. The model must never be the authority that decides whether it is allowed to perform them.

The model can recommend an operation. Trusted code checks the caller's identity, role, target, environment, change ticket, policy, and approval before invoking the operation.

## 3. Architecture

~~~text
User request / investigation evidence
               |
               v
        Agent proposes action
               |
               v
    Pydantic proposal validation
               |
               v
    Stable idempotency key creation
               |
               v
      LangGraph approval node
               |
               v
          interrupt()
               |
       checkpoint + pause
               |
               v
       Human review interface
               |
       authenticated reviewer
               |
               v
  trusted API constructs decision
               |
               v
     resume with Command(...)
               |
               v
     Validate approval policy
       |                 |
    rejected          approved
       |                 |
       v                 v
  no execution      execution node
                         |
                         v
                  MCP write tool
                         |
                         v
             downstream authorization
                         |
                         v
               operation + audit
~~~

LangGraph interrupts pause graph execution and surface a JSON-serializable payload. A checkpointer preserves state, and the workflow resumes with `Command(resume=...)` using the same thread ID. See the [official LangGraph interrupt documentation](https://docs.langchain.com/oss/python/langgraph/interrupts).

## 4. Understand `interrupt()`

A minimal example:

~~~python
from langgraph.types import interrupt, Command

def approval_node(state):
    decision = interrupt({
        "message": "Approve this operation?",
        "service": state["service"],
        "action": state["action"],
    })
    return {"decision": decision}
~~~

The first invocation stops at `interrupt()`. The caller receives an interrupt payload. Later, a trusted application resumes the same graph thread:

~~~python
result = await graph.ainvoke(
    Command(resume={"decision": "approve"}),
    config={"configurable": {"thread_id": "incident-123"}},
)
~~~

Important details:
- A checkpointer is required for resuming.
- The same thread ID identifies the paused workflow.
- The interrupt payload must be JSON serializable.
- The node containing `interrupt()` restarts from its beginning when resumed.
- Keep all work before the interrupt pure/read-only. Put irreversible work after the approval gate.
- Do not expose raw `Command(resume=...)` to untrusted callers.

The demo uses `InMemorySaver` for simplicity. It loses checkpoints when the process exits. Use a durable production checkpointer, such as LangGraph's PostgreSQL checkpointer, and persist approval records independently.

## 5. Proposal schema

The example validates proposals with Pydantic:

| Field | Meaning |
|---|---|
| request_id | Stable workflow identifier |
| requested_by | Authenticated requester identity |
| action | Explicit allow-listed operation |
| service | Target service |
| environment | staging or production |
| reason | Why the operation is proposed |
| change_reference | Change/incident ticket |

The schema rejects unknown fields and constrains the action to `restart_service` or `rollback_deployment`.

Do not let a model invent a free-form shell command, Kubernetes manifest, URL, or cloud API operation and then execute it. Prefer narrow, typed, allow-listed operations.

## 6. Trusted approval policy

The example demonstrates:
- Only `platform_admin` or `incident_commander` can approve.
- The requester cannot approve their own operation.
- Production operations require an `incident_commander`.
- An approval requires a review comment.
- A rejection never reaches the execution node.

These are deterministic checks in `validate_approval()`. The LLM does not make these decisions.

### Critical API integration rule

The CLI asks for an approver identity and role only to make the example interactive. That is not authentication.

In the real FastAPI integration:
1. Authenticate the reviewer using the JWT/session from Lesson 34.
2. Check a dedicated permission such as `operations:approve`.
3. Load the pending proposal from the database/checkpointer.
4. Construct `ApprovalDecision` using the authenticated principal's subject and role.
5. Accept only the decision/comment from the request body.
6. Call the internal resume function.

Never trust `approver_id`, `approver_role`, `tenant_id`, or `approved_by` supplied by the client.

## 7. MCP write tools

The example includes a separate stdio MCP server with two write-shaped tools:
- `restart_service`
- `rollback_deployment`

They are deliberately **simulation-only**. They write to a local SQLite ledger and never contact Kubernetes, cloud APIs, or real services.

The workflow discovers the tool catalog, verifies the exact expected names, and calls the selected tool only from the post-approval execution node.

In production, authorization must also exist at the MCP server and downstream operations API. A client-side graph gate is not enough: another MCP client could call the server directly. Use narrowly scoped service identities and enforce target/environment permissions server-side.

## 8. Idempotency and duplicate execution

A workflow may be retried after a timeout, worker restart, or lost HTTP response. Without idempotency, the same approved action may be sent more than once.

The example computes a stable SHA-256 key from the canonical proposal and sends it to the MCP tool. The mock SQLite executor:
- Stores the key with the action payload and result.
- Returns the prior result when the same key and payload arrive again.
- Rejects reuse of the same key with a different payload.

This is a teaching example, not a universal exactly-once guarantee.

For real external systems, the downstream API must support idempotency keys, or you need a durable operation/outbox/reconciliation design. A local database transaction cannot atomically commit with an unrelated cloud API call. Plan for uncertain outcomes, retries, and reconciliation.

## 9. Audit trail

A production approval record should capture:
- Request and workflow IDs.
- Requester identity and tenant.
- Proposed action and canonical parameters.
- Target service and environment.
- Evidence/reason and change reference.
- Reviewer identity, role, decision, comment, and timestamp.
- Policy version and approval expiry.
- Idempotency key.
- Execution start/end, downstream operation ID, result, and error category.

Keep audit events append-only and access-controlled. Do not log secrets, raw access tokens, or unnecessary sensitive log contents.

## 10. Timeouts, expiry, and cancellation

An approval can remain pending for hours. Add:
- An approval expiry timestamp.
- A scheduled expiry/cancellation path.
- A way to revoke a pending proposal if evidence changes.
- A maximum execution deadline after approval.
- Revalidation of target state immediately before execution.
- A policy for approvals that become stale after a deployment or incident change.

Approval is not a blank cheque. The exact operation, service, environment, and parameters must match what the reviewer approved.

## 11. Run the simulation

From the repository root:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/human_approval_mcp/requirements.txt
PYTHONPATH=examples/human_approval_mcp python examples/human_approval_mcp/main.py
~~~

The program:
1. Starts a local MCP stdio server.
2. Builds the LangGraph approval workflow.
3. Proposes a staging restart for `checkout-api`.
4. Pauses and prints the review payload.
5. Asks for a demo approval/rejection.
6. Invokes the MCP tool only after policy validation.
7. Prints the simulated result.

Try rejecting the operation. The execution tool should not be called.

Try entering the requester as approver. The policy should reject self-approval.

For production, change the environment to `production` and observe that `platform_admin` alone is insufficient; the example requires `incident_commander`.

## 12. Run tests

~~~bash
PYTHONPATH=examples/human_approval_mcp python -m pytest -q examples/human_approval_mcp/tests
~~~

The tests use fake action executors and temporary SQLite databases. They do not require Ollama, a real Kubernetes cluster, or a running production MCP server.

## 13. Production design exercise

Design the FastAPI endpoints that would sit around this workflow:

- `POST /v1/operations/proposals` — create a proposal and pause.
- `GET /v1/operations/proposals/{request_id}` — show proposal and status.
- `POST /v1/operations/proposals/{request_id}/decision` — approve/reject.
- `GET /v1/operations/proposals/{request_id}/audit` — read audit history.

Define:
- Which JWT scope can create proposals?
- Which scope can approve?
- Can the requester approve their own request?
- Which roles can approve staging vs production?
- How do you prevent an approver from changing the approved parameters?
- How do you handle an approval after the proposal expires?
- What happens if the downstream MCP server executes but the API process crashes before recording the result?
- How do you reconcile a timeout when you do not know whether the operation completed?

## 14. Knowledge check

1. What does `interrupt()` return to the caller?
2. Why must the same `thread_id` be used to resume?
3. Why does the node restart from the beginning after resume matter?
4. Why should requester identity and approver role come from authenticated server context?
5. Why must the MCP server enforce authorization even when the LangGraph workflow already checks approval?
6. Why does a checkpointer not guarantee exactly-once external side effects?
7. What is the purpose of an idempotency key?
8. Why should the system revalidate target state immediately before execution?

## Completion criteria

You can demonstrate a workflow that pauses before a write-capable MCP tool, rejects unauthorized/self-approval, executes only after a valid approval, and suppresses duplicate mock operations. You can explain the additional durable storage, identity, audit, and downstream authorization required before connecting real infrastructure.

## References

- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain human-in-the-loop middleware](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [LangGraph persistence and checkpointers](https://docs.langchain.com/oss/python/langgraph/persistence)
- [MCP specification](https://modelcontextprotocol.io/specification/2025-06-18)
