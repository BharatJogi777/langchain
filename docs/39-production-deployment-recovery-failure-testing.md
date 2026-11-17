# Lesson 39 — Production Deployment, Recovery, and End-to-End Failure Testing

This lesson turns the DevOps Investigation Agent into an operable service. It covers deployment topology, configuration, secrets, health, observability, capacity, backups, recovery, graceful shutdown, and failure drills.

> This repository is a learning reference, not a certified production distribution. The FastAPI example still has demo-only in-memory users and password login, and the outbox worker defaults to a no-op LangGraph resumer. Do not expose these examples publicly or connect write-capable infrastructure tools without replacing those boundaries.

## Learning outcomes

By the end, you should be able to:
- Separate API, worker, PostgreSQL, model serving, and MCP tool processes.
- Configure containers without baking credentials into images.
- Define liveness, readiness, startup, and dependency health correctly.
- Set request, model, MCP, and overall workflow deadlines.
- Size concurrency against local resource limits and production capacity.
- Back up and restore PostgreSQL, including LangGraph checkpoints and approvals.
- Handle SIGTERM, restarts, stuck leases, retries, and duplicate delivery.
- Run end-to-end and failure-injection tests and explain the results.

## 1. Target deployment topology

~~~text
                 Users / Internal UI
                         |
                    HTTPS / WAF
                         |
                API Gateway / Ingress
                         |
                 FastAPI API replicas
                  |             |
             Auth / RBAC     Rate limit
                  |             |
                  +------ Agent runtime ------+
                         |                    |
                    LangGraph             MCP client
                         |                    |
                  PostgreSQL          MCP tool services
                  /   |    \           logs / metrics /
             checkpoints approvals outbox     inventory
                                  |
                            Worker replicas
                                  |
                         resume graph / actions
~~~

Model serving may be Ollama for a private deployment or a managed model provider. MCP servers should be independently authenticated and authorized. Do not expose MCP administrative interfaces publicly.

### Process responsibilities

| Process | Responsibility | Scaling dimension |
|---|---|---|
| API | Authentication, validation, request lifecycle | Concurrent HTTP requests |
| Worker | Outbox delivery and workflow resumption | Queue depth and event age |
| PostgreSQL | Checkpoints, approvals, audit, outbox | IOPS, connections, storage |
| Model server | Inference | GPU/CPU, memory, tokens/sec |
| MCP servers | Read approved operational evidence | Per-tool latency and limits |

Keep API and worker deployments separate. They have different scaling, timeout, restart, and resource profiles.

## 2. Configuration and secrets

Use environment variables or a secret manager. Keep a checked-in example environment file containing placeholders only; never commit a real environment file.

Suggested configuration groups:

~~~text
APP_ENV
LOG_LEVEL
API_HOST
API_PORT
DATABASE_URL
DATABASE_POOL_MIN
DATABASE_POOL_MAX
JWT_ISSUER
JWT_AUDIENCE
OIDC_ISSUER_URL
OIDC_CLIENT_ID
OIDC_CLIENT_SECRET
OLLAMA_BASE_URL
OLLAMA_MODEL
MCP_LOGS_URL
MCP_METRICS_URL
MCP_INFRA_URL
REQUEST_TIMEOUT_SECONDS
AGENT_DEADLINE_SECONDS
MCP_TOOL_TIMEOUT_SECONDS
WORKER_POLL_SECONDS
WORKER_LEASE_SECONDS
WORKER_MAX_ATTEMPTS
OTEL_EXPORTER_OTLP_ENDPOINT
~~~

Rules:
- Validate configuration at process startup and fail closed.
- Do not provide insecure default production secrets.
- Use a secret manager or orchestrator secret injection.
- Rotate credentials and define revocation procedures.
- Separate development, staging, and production credentials.
- Use TLS for external traffic and database connections.
- Redact authorization headers, tokens, passwords, API keys, and sensitive incident payloads from logs.
- Never put secrets in LangGraph state, model prompts, trace attributes, or checkpoint metadata.

The Lesson 34 password token endpoint is a local demonstration only. Replace it with OIDC Authorization Code + PKCE for user-facing applications or a suitable machine-to-machine flow.

## 3. Container and deployment boundaries

Build immutable images from a pinned Python base image. Install dependencies from a lock file in a build stage, run as a non-root user, and avoid copying environment files, Git metadata, test data, or local model files into the image.

A production Dockerfile should:
- Use a supported, pinned Python 3.12 patch image.
- Install only runtime dependencies in the final stage.
- Create a non-root user and writable directories explicitly.
- Set PYTHONDONTWRITEBYTECODE=1 and PYTHONUNBUFFERED=1.
- Use an exec-form entrypoint so SIGTERM reaches the process.
- Include vulnerability scanning and SBOM generation in release review.
- Be rebuilt regularly for base-image and dependency security updates.

Do not assume host.docker.internal is a portable production model endpoint. Configure the model service URL explicitly for each environment. In local Mac Docker Desktop development it can point to host Ollama; in production it should point to a private model service DNS name or provider endpoint.

MCP transport matters. A stdio MCP server is a child process of its client and needs its executable, environment, lifecycle, and resource limits in the same runtime boundary. A remote MCP server needs authenticated network transport, TLS, service identity, and independent authorization. Do not mix these deployment models accidentally.

## 4. Health checks: liveness vs readiness

- **Liveness:** Is this process alive and able to make progress? It should not fail merely because PostgreSQL or Ollama is temporarily unavailable.
- **Readiness:** Can this instance safely accept the work it advertises? Check critical dependencies with bounded timeouts.
- **Startup:** Has initialization completed, including connection pools, graph compilation, and required configuration validation?

Do not make readiness perform a full LLM inference or a long-running MCP call. Use cheap dependency checks. Return degraded/not-ready when a required dependency is unavailable, while keeping liveness healthy so the orchestrator does not create restart loops.

## 5. Timeouts and concurrency budgets

Use a hierarchy of deadlines. The overall request deadline must exceed the sum of bounded internal stages, but it must still be finite.

Example budget (illustrative; measure and tune):
- HTTP request deadline: 45 seconds.
- Agent workflow deadline: 38 seconds.
- Individual MCP tool deadline: 8 seconds.
- Model call deadline: 25 seconds.
- Database statement timeout: 3 seconds.
- Cleanup reserve: 2 seconds.

Do not blindly copy these values into production. Measure p50/p95/p99 latency and set deadlines according to user-facing SLOs.

Control concurrency at every boundary:
- API server worker count and per-principal request limits.
- Maximum in-flight investigations per tenant.
- Model server queue and token budget.
- MCP per-server and per-tool concurrency.
- PostgreSQL pool size and connection budget.
- Worker batch size and maximum parallel handlers.

A rough database connection budget is: replicas × pool maximum per replica + worker pools + migration/admin reserve. Keep it below PostgreSQL's usable connection capacity.

## 6. Observability and SLOs

Carry a correlation ID across API, LangGraph nodes, MCP calls, worker events, and audit records. Keep trace IDs and span IDs distinct from business identifiers.

Recommended metrics:
- HTTP request count, latency histogram, and error rate.
- Investigation duration and outcome.
- Model request latency, token usage, timeout and refusal counts.
- MCP tool latency, error, timeout, and circuit-breaker state.
- Outbox pending count, oldest pending age, attempts, lease expiry, dead-letter count.
- PostgreSQL pool wait time, active connections, query latency, disk usage.
- Approval wait time and expired/denied approval counts.

Use bounded labels. Do not label metrics with user IDs, incident text, raw URLs, thread IDs, or arbitrary service names from user input. Put carefully controlled identifiers in traces/logs only when privacy policy permits.

Define SLOs before alerts. Example starting targets for a learning environment:
- API availability: 99.5% over 30 days.
- Non-LLM health endpoint p95: below 300 ms.
- Outbox oldest pending event: alert after 2 minutes.
- Dead-letter events: alert on any non-zero count.
These are examples, not universal production targets.

## 7. Graceful shutdown and recovery

On SIGTERM:
1. Mark the instance unready.
2. Stop accepting new requests or claiming new outbox events.
3. Allow bounded in-flight work to finish.
4. Cancel remaining work after the shutdown grace period.
5. Close MCP sessions, HTTP clients, telemetry exporters, and database pools.
6. Exit before the orchestrator's kill deadline.

A worker crash may leave a processing event leased. The lease lets another worker reclaim it after expiry. Fencing tokens prevent a stale worker from updating the row after a newer worker has claimed it. They do not make external side effects exactly-once.

If a worker resumes a graph and crashes before marking the event delivered, the event can be delivered again. Every consequential downstream operation needs a stable idempotency key and a reconciliation strategy for unknown outcomes.

## 8. Database backup and restore

Back up all durable state needed to continue a workflow:
- LangGraph checkpoint tables.
- Approval requests and decisions.
- Outbox events and delivery state.
- Audit records and relevant application data.

A backup is not proven until a restore has been tested.

Example local logical backup:

~~~bash
pg_dump "$DATABASE_URL" --format=custom --file=agent-backup.dump
~~~

Restore into a separate empty test database:

~~~bash
createdb agent_restore_test
pg_restore --dbname=agent_restore_test --clean --if-exists agent-backup.dump
~~~

Validate row counts, foreign keys, checkpoint visibility, approval-to-thread linkage, and pending outbox events. Define RPO (maximum tolerable data loss) and RTO (maximum tolerable recovery time) with the service owner. For larger deployments, use managed PostgreSQL backups and point-in-time recovery.

Do not restore an old outbox snapshot and immediately execute every pending event against production systems. Reconcile event state and external operation IDs first.

## 9. End-to-end testing strategy

Run these layers separately:

1. Unit tests: authorization, state transitions, reducers, retry calculation, idempotency, event validation.
2. Component tests: API with fake agent runtime; worker with fake resumer; MCP clients with mock servers.
3. Integration tests: real PostgreSQL, checkpointer, approval/outbox transaction, two worker processes.
4. Contract tests: API request/response schemas and MCP tool schemas.
5. End-to-end tests: create an investigation, pause for approval, reject/approve, resume, verify audit and final state.
6. Load tests: concurrent investigations, database pool pressure, model queue pressure, and worker backlog.
7. Security tests: missing/expired tokens, cross-tenant access, prompt injection in logs, tool argument tampering, unauthorized write requests.

Never use real production infrastructure or credentials in failure-injection exercises.

## 10. Failure-injection drills

| Drill | Injection | Expected behavior |
|---|---|---|
| PostgreSQL unavailable | Stop local database | Readiness fails; liveness remains responsive; no false success |
| Model unavailable | Stop Ollama | Bounded model error; no infinite retry |
| MCP timeout | Delay mock MCP response | Tool timeout; circuit breaker policy applies |
| Worker crash | Kill worker after claim | Lease expires; another worker reclaims |
| Duplicate delivery | Replay same event | Idempotency prevents duplicate external action |
| Stale worker | Let lease expire while old worker pauses | Fencing rejects stale DB update |
| Invalid approval | Change proposal hash | Event is quarantined; graph is not resumed |
| Disk pressure | Fill disposable test volume | Alert, controlled failure; no silent data loss |
| SIGTERM | Stop API/worker gracefully | Stop new work and close resources within grace period |

For each drill, capture: setup, command, expected result, observed result, logs/traces, recovery action, and remaining risk.

## 11. Local practice commands

Run the PostgreSQL dependency used in Lessons 37/38:

~~~bash
docker compose -f examples/transactional_outbox/docker-compose.yml up -d
docker compose -f examples/transactional_outbox/docker-compose.yml ps
~~~

Run the worker unit tests:

~~~bash
PYTHONPATH=examples/transactional_outbox python -m pytest -q examples/transactional_outbox/tests
~~~

Run the secured FastAPI example's unit tests:

~~~bash
PYTHONPATH=examples/fastapi_agent_api python -m pytest -q examples/fastapi_agent_api/tests
~~~

The API and worker examples have not yet been verified as one integrated deployment. Treat the tests as component-level until you run the full PostgreSQL + API + checkpoint + outbox + worker integration suite.

## 12. Production readiness checklist

Before any real deployment, verify:
- [ ] OIDC or machine identity is configured; demo password route disabled.
- [ ] Persistent user store and tenant-aware authorization are enabled.
- [ ] API and worker run as separate least-privilege identities.
- [ ] All MCP tools have server-side authorization and narrow credentials.
- [ ] Write-capable tools are allow-listed and require approval.
- [ ] Secrets are injected from a secret manager and rotated.
- [ ] TLS is enabled for public and service-to-service traffic.
- [ ] Request, model, MCP, SQL, and workflow deadlines are bounded.
- [ ] Concurrency and database connection budgets are documented.
- [ ] Liveness/readiness/startup probes are tested.
- [ ] Logs, metrics, traces, dashboards, and alerts are configured.
- [ ] Backups and point-in-time recovery are tested.
- [ ] Duplicate delivery and unknown external outcomes are reconciled.
- [ ] Restore, crash, dependency outage, and SIGTERM drills pass.
- [ ] Dependency/image scans and SBOM are part of release review.
- [ ] Incident response and rollback procedures are documented.

## 13. Exercises

1. Draw your deployment topology and identify each trust boundary.
2. Calculate a database connection budget for three API replicas and two workers.
3. Define an end-to-end deadline and derive per-stage timeouts.
4. Stop PostgreSQL and explain the difference between liveness and readiness.
5. Kill the worker after claim and verify lease-based recovery.
6. Restore a backup into a separate database and validate graph thread continuity.
7. Write an incident runbook for a growing outbox backlog.
8. Explain why an outbox is at-least-once and where idempotency must live.

## Completion criteria

You can deploy API and worker independently, explain the health and timeout model, restore persistent state, run the failure drills, and produce evidence that duplicate delivery does not cause duplicate external actions. The final lesson integrates these components into the capstone.
