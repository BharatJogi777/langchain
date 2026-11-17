# Production Deployment and Recovery Checklist

Use this before a staging release and repeat after significant architecture changes.

## Identity and access
- [ ] Demo login endpoint disabled.
- [ ] OIDC or machine identity integrated.
- [ ] User, role, tenant, and service authorization checked server-side.
- [ ] API, worker, and MCP services use separate least-privilege identities.
- [ ] MCP servers independently enforce authorization.
- [ ] Write-capable tools require explicit approval.

## Runtime and deployment
- [ ] API and worker are independently deployable.
- [ ] Images use pinned base images and locked dependencies.
- [ ] Processes run as non-root.
- [ ] Secrets are injected at runtime and rotated.
- [ ] No credentials, environment files, model weights, or production data in images.
- [ ] Startup, readiness, and liveness checks have distinct semantics.
- [ ] SIGTERM and bounded graceful shutdown are tested.
- [ ] Rollback procedure is documented.

## Reliability
- [ ] Overall workflow deadline and per-stage timeouts are bounded.
- [ ] API, model, MCP, worker, and database concurrency are bounded.
- [ ] Retries are limited and use backoff with jitter.
- [ ] Circuit breakers and fallback behavior are tested.
- [ ] Outbox leases and fencing are tested with multiple workers.
- [ ] Downstream idempotency and unknown-outcome reconciliation exist.
- [ ] Dead-letter inspection and replay process is documented.

## Data protection and recovery
- [ ] TLS and encryption at rest are enabled where required.
- [ ] PostgreSQL backup schedule and retention are configured.
- [ ] Restore test validates checkpoints, approvals, outbox, and audit.
- [ ] RPO and RTO are agreed with service owners.
- [ ] Restored pending events are reconciled before replay.

## Observability and operations
- [ ] Correlation IDs propagate across API, graph, MCP, worker, and audit.
- [ ] Metrics use bounded-cardinality labels.
- [ ] Dashboards cover API, model, MCP, database, and outbox.
- [ ] Alerts cover error rates, latency, queue age, dead letters, and resource saturation.
- [ ] Runbooks cover dependency outage, backlog, restore, and rollback.
- [ ] Sensitive data is redacted from logs and traces.

## Verification evidence
Record a result for each drill. A checked box without evidence is not verification.

| Drill | Expected result | Observed result / evidence | Pass? |
|---|---|---|---|
| PostgreSQL outage | Readiness fails; liveness remains healthy | | |
| Model outage | Bounded error, no infinite retry | | |
| MCP timeout | Deadline and resilience policy apply | | |
| Worker crash after claim | Lease allows safe reclaim | | |
| Duplicate event | No duplicate external effect | | |
| Stale worker | Fenced update rejected | | |
| Invalid/expired approval | No graph resume | | |
| SIGTERM | Graceful shutdown within grace period | | |
| Database restore | Workflow state remains consistent | | |

## Release decision

- Release owner:
- Environment:
- Version / image digest:
- Date:
- Known limitations:
- Rollback owner and procedure:
- Decision: GO / NO-GO
