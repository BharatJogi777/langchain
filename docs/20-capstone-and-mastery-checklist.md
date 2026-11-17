# Capstone and mastery checklist

## Capstone
Build the DevOps Investigation Agent described in projects/devops-investigation-agent/README.md. It investigates incidents using read-only log, Kubernetes, and metrics tools, returns evidence-backed findings, and persists state. No remediation in the first release.

## Required capabilities
FastAPI with auth boundary and Pydantic schemas; LangChain agent or LangGraph workflow with bounded execution; at least two MCP servers; explicit state and durable checkpoint strategy; evidence provenance/citations; PostgreSQL persistence and optional pgvector RAG; unit/integration/evaluation tests; logs/traces/metrics/health; secrets handling and threat model; Docker Compose.

## Final review
Foundations: explain message types, tool-call messages, Runnable composition, and chain vs agent vs graph. Retrieval: explain character vs token chunk size, cosine distance, hybrid retrieval, reranking, Recall@k, faithfulness. Agents/MCP: explain agent loop/stop conditions, validate tool arguments, enforce auth, explain MCP discovery/invocation, design human approval. Production: trace request end-to-end, handle timeout/retry/duplicate/partial failure, prevent tenant leakage, estimate cost, rollback prompt/model/dependency changes.

## Completion standard
Implement without copying, write tests, explain trade-offs, and diagnose at least one failure mode per topic. Reading is the beginning, not the finish.