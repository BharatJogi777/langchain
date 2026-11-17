# Production security, reliability, cost

## Security
Authenticate requests. Authorize tenant/document/conversation/tool access in deterministic code. Use least-privilege credentials. Treat user input, retrieved text, model output, and tool results as untrusted. Validate schemas and invariants. Restrict outbound network and file access. Externalize secrets. Encrypt data. Redact traces/logs. Audit privileged actions.

Prompt injection defenses include source labeling, untrusted-context delimiters, tool allowlists, least privilege, output validation, and retrieval ACL enforcement. Prompt wording alone is not a security control.

## Reliability
Timeouts/cancellation; bounded retries with exponential backoff and jitter; circuit breakers; bulkheads and concurrency limits; queues for long tasks; idempotency keys; dead-letter queues; graceful degradation; human approval for irreversible actions.

## Cost and latency
Estimate input/output tokens, model calls per workflow, embedding volume/reprocessing, retrieval/reranking calls, concurrency/queue depth, storage and tracing. Reduce waste with context trimming, safe caching, smaller models for low-risk tasks, embedding batches, deterministic pre/post-processing. Cache keys and invalidation must preserve user/tenant permissions.

## Deployment
Reproducible build and lockfile; non-root minimal container; resource limits; health/readiness; TLS/network policy; migrations/backups; runtime secrets; rollback; load/failure tests; SLOs/alerts. Benchmark model quality, tool reliability, latency, cost, context, data residency, and availability.

## Lab
Threat-model the capstone. Simulate provider timeout, MCP crash, database outage, repeated tool call, cross-tenant retrieval attempt, and prompt injection in a log line.