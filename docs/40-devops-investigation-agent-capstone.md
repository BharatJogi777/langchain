# Lesson 40 — Integrated DevOps Investigation Agent Capstone

This is the final structured lesson. It combines the concepts from Lessons 1–39 into one application architecture and gives you an implementation sequence, API contract, workflow design, data model, testing plan, and mastery assessment.

**Important status distinction:** the repository contains working learning components for MCP specialists, FastAPI, security demonstrations, PostgreSQL checkpointing, approvals, and an outbox worker. They have been developed in separate lessons. They are not yet verified as one end-to-end integrated production deployment. This capstone guide explains how to connect them and how to prove each integration. Do not describe the system as production-ready until the integration, security, recovery, and operational acceptance tests pass.

## 1. Product requirements

Build an internal assistant for investigating operational incidents.

An authorized engineer submits:
- service name,
- incident description,
- investigation objective,
- optional time range and environment.

The system:
1. Authenticates the caller and authorizes access to the requested service and tenant.
2. Creates an investigation record and durable LangGraph thread.
3. Collects evidence from read-only logs, metrics, and infrastructure MCP servers.
4. Retrieves relevant runbooks and previous incident knowledge through RAG.
5. Produces a structured diagnosis with evidence references, confidence, unknowns, and recommended next steps.
6. If an action is proposed, stores a proposal and pauses for a human decision.
7. Records the approval/rejection and an outbox event in one database transaction.
8. A separate worker validates the authoritative approval and resumes the graph.
9. Every state transition is auditable and recoverable after process restarts.

The initial capstone uses mock operational data and read-only MCP tools. The action execution adapter must remain a mock until the security, approval, idempotency, and reconciliation gates are independently reviewed.

## 2. Architecture

~~~text
 Engineer / Internal UI
          |
       HTTPS
          |
   API Gateway / OIDC
          |
     FastAPI API -------------------- OpenTelemetry
       |       |                           |
       |    Authorization                  v
       |                              Collector / Backend
       |
       +---- PostgreSQL
       |       |-- investigations
       |       |-- LangGraph checkpoints
       |       |-- approvals
       |       |-- outbox
       |       |-- audit events
       |
       +---- LangGraph workflow
                |
        +-------+---------+
        |       |         |
     Logs     Metrics   Infra
     MCP       MCP       MCP
        |       |         |
        +-------+---------+
                |
          Evidence reducer
                |
           RAG retriever
                |
         Structured report
                |
         Approval interrupt
                |
         Approval API transaction
                |
          PostgreSQL outbox
                |
          Async worker
                |
        Graph resume adapter
                |
         Final audit/report
~~~

### Responsibilities

| Component | Owns | Must not own |
|---|---|---|
| FastAPI | HTTP validation, identity, authorization, request IDs | Model-generated permission decisions |
| LangGraph | Workflow state, branches, interrupts, checkpoint thread | Secret storage or trusted identity |
| MCP servers | Narrow operational capabilities and server-side access checks | Broad unrestricted infrastructure credentials |
| RAG | Runbook and incident retrieval with source metadata | Treating retrieved text as trusted instructions |
| PostgreSQL | Durable state, approvals, outbox, audit | Long-running model/tool calls inside transactions |
| Worker | Outbox claims, validation, graph resume | Trusting event payload as approval authority |
| Model | Reasoning, synthesis, structured extraction | Authorization or direct infrastructure access |

## 3. Repository components to reuse

| Capability | Existing lesson artifact |
|---|---|
| Three MCP servers and specialist agents | `examples/langgraph_mcp_specialists/` |
| MCP timeout/retry/circuit-breaker policy | `examples/mcp_resilience_advanced/` |
| MCP tracing and structured telemetry | `examples/mcp_observability/` |
| Secured FastAPI application | `examples/fastapi_agent_api/` |
| Approval and safe action patterns | Lesson 35 |
| PostgreSQL checkpointing and approval persistence | Lesson 36 |
| Approval/outbox transaction and schema | Lesson 37 |
| Async worker and LangGraph resume adapter | `examples/transactional_outbox/` |
| Deployment and failure-test guidance | Lesson 39 |

Read each component README and its lesson before integrating. Check dependency versions and public APIs together in a fresh virtual environment. Do not blindly combine independently pinned requirements files; resolve and lock one compatible set for the integrated project.

## 4. Define the workflow state

Use typed state and keep evidence separate from model-written conclusions.

Suggested state:

~~~python
from typing import TypedDict, NotRequired

class Evidence(TypedDict):
    source: str
    tool_name: str
    observed_at: str
    content: str
    source_reference: str

class InvestigationState(TypedDict):
    investigation_id: str
    tenant_id: str
    requester_id: str
    service: str
    environment: str
    incident: str
    objective: str
    evidence: list[Evidence]
    retrieval_sources: list[dict]
    specialist_status: dict[str, str]
    diagnosis: NotRequired[dict]
    proposal: NotRequired[dict]
    approval_request_id: NotRequired[str]
    final_report: NotRequired[dict]
    errors: list[dict]
~~~

Rules:
- Derive tenant and requester identity from verified authentication context, never from user prompt fields.
- Keep state payloads bounded. Store large evidence externally and reference it by ID.
- Store source, timestamp, tool name, and retrieval metadata for every evidence item.
- Treat tool output, log messages, documents, and retrieved runbooks as untrusted data.
- Do not place credentials, tokens, or raw secrets in graph state or checkpoints.
- Use a stable `thread_id` tied to the investigation and tenant, with authorization checks before reading or resuming it.
- Define state schema versions and migration behavior for long-lived threads.

## 5. Graph design

A useful first graph is deliberately explicit:

~~~text
START
  |
validate_request_context
  |
parallel_read_only_investigation
  |---- logs_specialist
  |---- metrics_specialist
  |---- infrastructure_specialist
  |---- runbook_retrieval
  |
merge_and_validate_evidence
  |
synthesize_structured_diagnosis
  |
safety_and_evidence_review
  |
decision: more evidence needed?
  | yes -> targeted_followup (bounded loop) -> merge...
  | no
  |
prepare_recommendation
  |
decision: consequential action proposed?
  | no -> render_report -> END
  | yes
  |
create_approval_request
  |
interrupt / wait for human
  |
resume_after_approval
  |
decision: approved?
  | no -> record_rejection -> render_report -> END
  | yes -> validate_freshness_and_policy
  |
execute_mock_action (idempotent)
  |
verify_postcondition
  |
render_report
  |
END
~~~

Bound every loop with a maximum iteration count and total workflow deadline. A failed specialist should produce an explicit partial result, not fabricated evidence. The final report must distinguish observed facts, model inference, and recommendations.

## 6. Structured diagnosis contract

Ask the model for a schema, then validate it in application code. Example:

~~~python
from pydantic import BaseModel, Field
from typing import Literal

class Finding(BaseModel):
    statement: str
    category: Literal["fact", "inference", "unknown"]
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)

class Diagnosis(BaseModel):
    summary: str
    severity: Literal["low", "medium", "high", "critical", "unknown"]
    findings: list[Finding]
    likely_causes: list[str]
    missing_evidence: list[str]
    recommended_next_steps: list[str]
    requires_human_approval: bool
~~~

Validation rules:
- A factual finding must reference one or more evidence IDs.
- An inference must be labelled as an inference and include supporting evidence where available.
- An unknown must not be silently converted into a fact.
- Reject unknown evidence IDs.
- Do not allow the model to set the authenticated actor, tenant, approval result, or execution permission.
- Do not let the model invent timestamps, deployments, metrics, or log records.

## 7. RAG knowledge base

Index only approved operational documents:
- runbooks,
- service ownership and dependency maps,
- deployment procedures,
- postmortems,
- incident response policies.

Recommended ingestion metadata:
- document_id and immutable document version,
- tenant/environment/service scope,
- source URI and access classification,
- owner and last-reviewed timestamp,
- chunk ID and ingestion timestamp.

Retrieval pipeline:
1. Authenticate and establish tenant/service scope.
2. Apply metadata filters before returning candidate chunks.
3. Retrieve semantically and, where justified, lexically.
4. Rerank candidates.
5. Apply freshness and access policy.
6. Pass selected chunks with source IDs to the diagnosis step.
7. Return citations/source references in the report.

Never let retrieved text instruct the agent to ignore system policy, reveal credentials, or invoke tools. Documents are evidence, not authority. Add document poisoning and cross-tenant retrieval tests.

## 8. API contract

A minimal versioned API:

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/investigations` | Create investigation |
| GET | `/v1/investigations/{id}` | Read status and summary |
| GET | `/v1/investigations/{id}/events` | Read authorized audit timeline |
| GET | `/v1/investigations/{id}/report` | Fetch final structured report |
| GET | `/v1/approvals/{id}` | Read pending approval details |
| POST | `/v1/approvals/{id}/decision` | Approve or reject proposal |
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | Dependency readiness |

Creation should return `202 Accepted` and an investigation ID if execution is asynchronous. Do not keep an HTTP request open while an entire multi-agent investigation runs.

Approval request must include a proposal ID/hash, human-readable impact, expiry, allowed scope, and the exact action parameters. The approval decision must come from the authenticated reviewer identity, not a request-body actor field.

## 9. Durable data model

Use migrations and explicit foreign keys. A conceptual schema:

~~~sql
CREATE TABLE investigations (
    investigation_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    requester_id TEXT NOT NULL,
    service TEXT NOT NULL,
    status TEXT NOT NULL,
    thread_id TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE approval_requests (
    request_id UUID PRIMARY KEY,
    investigation_id UUID NOT NULL REFERENCES investigations(investigation_id),
    thread_id TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    decision TEXT,
    decided_by TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_events (
    audit_id UUID PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    investigation_id UUID NOT NULL REFERENCES investigations(investigation_id),
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
~~~

The outbox table and checkpoint tables are created by their corresponding lesson migrations/schema. Adapt names and foreign keys to the actual checkpointer package version. Do not create a second incompatible approval schema.

The approval decision and outbox insertion must commit in one transaction. The worker reloads the authoritative approval row, validates expiry and proposal hash, and uses a fenced claim token for all event state updates.

## 10. Approval and action security

The model may propose an action, but only trusted application code can authorize it.

Approval validation must verify:
- reviewer identity and permission for this tenant/service/action,
- request is pending and not expired,
- exact proposal hash matches the reviewed content,
- action type and parameters remain inside a server-side allow-list,
- target environment and service match the authorized scope,
- idempotency key is stable across retries,
- action is still safe and applicable at execution time.

A proposal approval is not an unconditional permission forever. Re-check freshness, target state, and policy immediately before execution. Record the before/after state and operation ID. For unknown external outcomes, reconcile by operation ID before retrying.

The initial capstone action executor must be a mock implementation. Do not add production write credentials to the learning project.

## 11. Integration sequence

Integrate in this order so failures are localized:

### Phase A — Read-only investigation
1. Create a fresh Python 3.12 environment.
2. Resolve one dependency lock for API, LangChain, LangGraph, MCP adapters, Ollama provider, psycopg, and tests.
3. Run the three MCP servers independently.
4. Run specialist agents with mock data.
5. Add a graph that fans out to specialists and merges evidence.
6. Add structured diagnosis validation and source references.

**Exit:** a deterministic test can run the graph with fake specialists and verify findings cite only supplied evidence.

### Phase B — API and identity
1. Wire FastAPI lifespan to initialize the graph runtime.
2. Replace the demo password authentication with an OIDC/JWT verifier appropriate to the deployment.
3. Enforce tenant, service, and action authorization at the API and tool boundary.
4. Add asynchronous investigation creation and status/report endpoints.
5. Persist investigation metadata and graph checkpoints.

**Exit:** unauthorized users cannot read another tenant's investigation or invoke tools outside their scope.

### Phase C — RAG
1. Add document ingestion and version metadata.
2. Add vector and optional lexical retrieval with tenant/service filters.
3. Add reranking and source attribution.
4. Test prompt injection and cross-tenant isolation.

**Exit:** every retrieved chunk has a source and access scope; forbidden documents never enter the prompt.

### Phase D — Approval and durable resumption
1. Add proposal creation and graph interrupt.
2. Persist approval and audit records.
3. In one transaction, store decision and outbox event.
4. Run worker as a separate process.
5. Connect the worker adapter to the compiled graph and PostgreSQL checkpointer.
6. Verify lease expiry, fencing, retry, dead-letter, idempotency, and reconciliation.

**Exit:** a process restart does not lose an approval wait, and replaying an event does not duplicate the mock action.

### Phase E — Operability
1. Add Dockerfiles and compose services for API, worker, PostgreSQL, and required MCP processes.
2. Configure Ollama on the host for local Mac development, or a separate private model endpoint.
3. Add health checks, resource limits, non-root users, secrets, telemetry, and migrations.
4. Execute Lesson 39 failure drills and backup/restore test.
5. Document runbooks and rollback.

**Exit:** the deployment can be started from a clean checkout, dependencies become healthy, tests pass, and recovery drills have recorded evidence.

## 12. Test matrix

| Area | Test | Required assertion |
|---|---|---|
| Identity | Missing/expired JWT | Request denied |
| Authorization | Cross-tenant investigation ID | No data disclosure |
| Tool policy | Model supplies a different service | Server-side wrapper rejects it |
| MCP | One server unavailable | Partial result clearly marks unavailable specialist |
| Agent loop | Model requests repeated tool use | Maximum steps/deadline enforced |
| Evidence | Diagnosis cites unknown evidence ID | Schema/application validation rejects it |
| RAG | Malicious runbook text | Instructions treated as untrusted data |
| RAG | Cross-tenant retrieval attempt | No unauthorized chunk returned |
| Checkpoint | API restart mid-investigation | Thread resumes from persisted state |
| Approval | Hash changed after review | Resume/action rejected |
| Approval | Expired request | Cannot approve or execute |
| Outbox | Worker crash after claim | Lease expires and event is safely reclaimed |
| Outbox | Duplicate event | Mock action remains idempotent |
| Outbox | Old worker completes after new claim | Fencing rejects stale completion |
| Database | Restore backup | Investigation/checkpoint/approval references remain consistent |
| Operations | SIGTERM | New work stops and resources close within grace period |

## 13. Local development on the MacBook Air M1 (8 GB RAM)

Keep the local setup lightweight:
- Run Ollama directly on macOS, not as another heavy container.
- Start with `llama3.2:3b` and low concurrency.
- Use PostgreSQL in Docker Compose.
- Use mock MCP tools and deterministic fake model responses for most tests.
- Do not run multiple model instances simultaneously.
- Keep API and worker processes separate, but run one worker locally.
- Run integration tests selectively; unit tests should not require Ollama.
- Keep retrieved context and tool output bounded.

The goal of local development is to validate architecture and correctness, not benchmark production throughput.

## 14. Run and verification workflow

Use the existing component guides first:

~~~bash
# Specialist agent tests
PYTHONPATH=examples/langgraph_mcp_specialists pytest -q examples/langgraph_mcp_specialists/tests

# FastAPI tests
PYTHONPATH=examples/fastapi_agent_api pytest -q examples/fastapi_agent_api/tests

# Outbox worker tests
PYTHONPATH=examples/transactional_outbox pytest -q examples/transactional_outbox/tests

# Start the outbox PostgreSQL dependency
docker compose -f examples/transactional_outbox/docker-compose.yml up -d
~~~

These commands verify component suites only. A capstone is not integrated until a single end-to-end test starts the required services, creates an investigation, pauses for approval, records a decision, resumes from PostgreSQL, and verifies the final report and audit trail. Record actual test output; never mark unexecuted tests as passed.

## 15. Capstone deliverables

Your final project should contain:

- [ ] Architecture and threat model.
- [ ] One dependency lock and reproducible setup.
- [ ] API and worker as independent processes.
- [ ] Read-only MCP servers with least-privilege policies.
- [ ] LangGraph investigation graph with bounded loops and persistence.
- [ ] RAG ingestion, metadata filters, citations, and evaluation dataset.
- [ ] Typed diagnosis and report schemas.
- [ ] OIDC/JWT verification and tenant-aware authorization.
- [ ] Approval API, transactional outbox, worker, fencing, and idempotency.
- [ ] PostgreSQL migrations and backup/restore instructions.
- [ ] Docker deployment and health checks.
- [ ] Unit, integration, contract, security, and evaluation tests.
- [ ] Metrics, traces, logs, dashboards, and alerts.
- [ ] Failure drills, runbooks, and rollback procedure.
- [ ] Demo script using mock incidents and mock actions.

## 16. Mastery assessment

You have completed the course when you can explain and implement these without copying:

1. Why use an agent for evidence collection but LangGraph for a durable multi-step workflow?
2. When should a deterministic LCEL chain replace an agent?
3. What does MCP standardize, and what does it not provide (identity, authorization, reliability)?
4. Why are tool outputs and RAG documents untrusted?
5. How do you prevent a model from changing the authorized service?
6. How do you make a graph resume after process restart?
7. Why are database checkpointing and the transactional outbox separate concerns?
8. Why is outbox delivery at-least-once rather than exactly-once?
9. How do claim tokens fence stale workers?
10. How do you handle an external operation whose outcome is unknown?
11. How do you evaluate retrieval quality, answer grounding, and tool selection?
12. How do you size model concurrency and PostgreSQL pools?
13. How do you define liveness, readiness, and an overall deadline?
14. How do you restore a workflow after database failure?
15. Which controls must remain in trusted code rather than prompts?

For each answer, draw the data flow, identify the trust boundary, explain one failure mode, and describe the test that proves the behavior.

## Course completion

The structured 40-lesson curriculum is complete after this lesson. The learning journey is not finished by reading the documents. Your next phase is to implement the integration phases, run the tests on your machine, fix real failures, and prepare to explain the architecture in a senior backend/AI engineer interview.

The repository's existing components are valuable building blocks, but this document does not claim that the integrated capstone has already been built or tested as one deployment.
