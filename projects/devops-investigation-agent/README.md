# Capstone: DevOps Investigation Agent

## Objective
Build an incident investigation service. User submits incident description and service. The system gathers approved evidence from logs, Kubernetes status, and database metrics; synthesizes a grounded report; persists state. Initial release is read-only: no pod restarts, deployment mutations, arbitrary shell, or database writes.

## Architecture
Client → FastAPI (auth/validation/rate limits) → Investigation service → LangGraph workflow or bounded LangChain agent → read-only Log MCP, Kubernetes MCP, Metrics MCP → evidence normalization/provenance → PostgreSQL (investigation/state/audit) → structured report with citations.

Optional RAG: ingest runbooks/postmortems into PostgreSQL/pgvector. Retrieval must enforce tenant and document ACL filters before returning content.

## Suggested layout
app/{main.py,config.py,api/,domain/,orchestration/,tools/,mcp/,retrieval/,persistence/,observability/}; mcp_servers/{logs_server.py,kubernetes_server.py,metrics_server.py}; tests/{unit,integration,evals}; docker-compose.yml; .env.example; pyproject.toml.

## Workflow
1. Authenticate caller and resolve tenant/permissions.
2. Validate incident and create investigation ID.
3. Classify incident and choose allowed evidence sources.
4. Query read-only tools with explicit time window and service scope.
5. Normalize to typed evidence records with timestamps and source IDs.
6. Deduplicate and bound result size.
7. Synthesize findings using only supplied evidence.
8. Validate report schema and ensure factual claims reference evidence.
9. Persist state, evidence references, and audit metadata.
10. Return findings, limitations, and confidence caveats.

## Report schema
investigation_id; service; time_window; summary; severity_assessment; findings[{claim,evidence_ids,confidence}]; hypotheses[{claim,supporting_evidence,disconfirming_evidence}]; recommended_read_only_checks; missing_evidence; generated_at; model_version; prompt_version.

## Safety
MCP tools are read-only and allowlisted. Tenant identity comes from auth context, never model arguments. Bound time ranges and results. No arbitrary shell/SQL. Treat outputs as untrusted evidence. Do not invent metrics, timestamps, pod names, or log lines. Any future remediation requires separate policy, scoped human approval, reauthorization, idempotency, and audit. Add per-tool timeout, max steps, deadline, token budget.

## Testing
Unit: schemas, policy, normalization, prompts, citation validator. Integration: fake MCP servers, PostgreSQL, auth. Evaluation: representative incidents and unanswerable cases. Resilience: timeout, malformed tool result, MCP exit, duplicate request, DB outage. Security: cross-tenant IDs, unauthorized namespace, injection in logs/runbooks, oversized output.

## Milestones
1. Deterministic FastAPI + mock adapters.
2. MCP servers and client discovery.
3. Bounded agent/graph orchestration.
4. Evidence model and report schema.
5. PostgreSQL persistence/checkpointing.
6. Optional runbook RAG.
7. Tests/evaluation/tracing/security.
8. Docker Compose, threat model, load test, operational docs.

## Definition of done
A reviewer can run locally, reproduce an incident, inspect trace, see evidence behind every claim, verify tenant isolation, run tests, and confirm no mutating tool is exposed.