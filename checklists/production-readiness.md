# Production readiness checklist

## Architecture
- [ ] LLM/agent use justified against deterministic alternatives.
- [ ] Failure behavior, fallback, SLOs, latency and cost budgets documented.
- [ ] Model/provider/version strategy recorded.

## Security/privacy
- [ ] Authentication and tenant authorization enforced in code.
- [ ] Retrieval and conversation state enforce ACLs.
- [ ] Tools use least privilege and allowlists; no arbitrary shell/SQL.
- [ ] Prompt injection threat-modeled.
- [ ] Secrets externalized; logs/traces redact sensitive data.
- [ ] Retention, deletion, and audit requirements implemented.

## Reliability
- [ ] Timeouts/cancellation at external boundaries.
- [ ] Bounded retries and idempotency.
- [ ] Concurrency limits, backpressure, rate limits.
- [ ] Agent step/tool/token/deadline limits.
- [ ] Partial failures and degraded mode tested.
- [ ] Backups, migrations, rollback documented.

## Quality
- [ ] Output schema and business invariants validated.
- [ ] RAG evaluated on representative questions.
- [ ] Citations validated against source evidence.
- [ ] Unanswerable/adversarial cases included.
- [ ] Prompt/model changes run through regression evaluation.
- [ ] Human review for consequential decisions.

## Operations
- [ ] Structured logs, metrics, traces, correlation IDs.
- [ ] p50/p95 latency, error rate, token usage, cost tracked.
- [ ] Health/readiness endpoints.
- [ ] Load and resilience tests completed.
- [ ] Runbooks, alerts, rollback plan exist.
- [ ] Dependency lockfile and vulnerability scanning.