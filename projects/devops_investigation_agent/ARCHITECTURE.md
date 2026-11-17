# Capstone Architecture Decision Record

## Decision 1 — API and worker are separate processes

The API authenticates requests and creates durable work. The worker consumes outbox events and resumes paused workflows. They share PostgreSQL but have different scaling and lifecycle requirements.

## Decision 2 — LangGraph owns workflow state

The graph explicitly models fan-out, evidence merge, bounded follow-up, approval interrupt, and resume. A plain agent loop is not the durable workflow coordinator.

## Decision 3 — MCP is the tool protocol boundary

Each specialist receives a narrow tool catalog. The API derives tenant and service permissions from verified identity; the model cannot choose a new tenant or service. MCP servers independently authorize their callers.

## Decision 4 — PostgreSQL stores durable coordination state

Checkpoint data, investigation metadata, approvals, audit records, and outbox events have distinct responsibilities. Approval decision plus outbox insert is one transaction. Model and network calls never run while holding that transaction open.

## Decision 5 — RAG is evidence, not policy

Runbooks are filtered by tenant, service, environment, version, and access classification. Retrieved text cannot override system policy or grant tool permissions.

## Decision 6 — External actions are deferred and idempotent

The initial capstone executes mock actions only. Real action support requires a separate threat model, strict allow-list, human approval, immutable proposal hash, stable idempotency key, downstream authorization, audit, and reconciliation of unknown outcomes.

## Trust boundaries

- User to API: identity, request validation, rate limiting.
- API to graph: authenticated context and scoped state.
- Graph to model: prompt and tool outputs are untrusted.
- Graph to MCP: per-tool allow-list, timeouts, and server-side authorization.
- Graph to retriever: tenant-scoped document access.
- Approval UI to API: verified reviewer identity and exact proposal version.
- Worker to PostgreSQL: least-privilege role, fenced event claims.
- Worker to action adapter: policy revalidation and idempotency.
