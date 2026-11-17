# DevOps Investigation Agent — Capstone

This directory is the integration home for the final LangChain course project.

## Status

**Architecture and integration plan documented; full end-to-end integration is not yet verified.**

The repository already contains component examples:
- `../../examples/langgraph_mcp_specialists/`
- `../../examples/fastapi_agent_api/`
- `../../examples/transactional_outbox/`
- Lessons 35–39 for approval, checkpointing, outbox, worker, and operations.

Do not infer that separate component tests prove the integrated system works. Follow the phase gates in [Lesson 40](../../docs/40-devops-investigation-agent-capstone.md).

## What the application does

An authenticated engineer starts an incident investigation. LangGraph coordinates read-only MCP specialists for logs, metrics, and infrastructure, plus a RAG runbook retriever. The application validates evidence and produces a structured diagnosis. Consequential recommendations pause for human approval. The decision and outbox event are persisted atomically; a separate worker validates the decision and resumes the graph.

The initial version uses mock operational evidence and mock action execution only.

## Architecture and build plan

Read:
- [Final capstone lesson](../../docs/40-devops-investigation-agent-capstone.md)
- [Production deployment and recovery](../../docs/39-production-deployment-recovery-failure-testing.md)
- [Production readiness checklist](../../checklists/production-deployment-recovery.md)

## Integration phases

1. Read-only specialist graph and evidence validation.
2. FastAPI, identity, authorization, and persistent checkpoints.
3. RAG ingestion, scoped retrieval, and citations.
4. Approval interrupt, transactional outbox, and separate worker.
5. Docker deployment, observability, failure drills, and restore test.

## Local prerequisites

- Python 3.12+
- Docker Desktop
- Ollama installed on the host for local inference
- `llama3.2:3b` model (or configure another compatible model)
- PostgreSQL 16 for local integration

On an 8 GB Apple Silicon laptop, run one small model with low concurrency and use fake model responses for unit tests.

## Safety

- Never connect this learning project to real production write credentials.
- Keep MCP tools read-only until the authorization and approval system has been independently reviewed.
- Do not trust the model to decide permissions.
- Do not store credentials or secrets in prompts, graph state, checkpoints, logs, or traces.
- Treat logs, retrieved documents, and tool outputs as untrusted input.
