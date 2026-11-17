# Production-Grade LangChain Mastery

A structured, hands-on curriculum for learning modern LangChain from foundations to production AI applications. The course uses Python, Ollama (for local learning), FastAPI, PostgreSQL/pgvector, and MCP.

## Start here

1. Read the [course roadmap](docs/00-roadmap.md).
2. Follow [the setup guide](docs/01-environment-setup.md).
3. Study each lesson and complete its lab.
4. Build the DevOps Investigation Agent capstone.

## Course map

Lessons 01–20 cover LangChain foundations, RAG, agents, FastAPI, testing, production design, and the initial capstone.
Lessons 21–40 extend the course through MCP, LangGraph, specialist agents, resilience, observability, API security, human approval, PostgreSQL checkpointing, the transactional outbox, production operations, and the integrated capstone.

| Lesson | Subject |
|---|---|
| 30 | [Multiple MCP specialist agents](docs/30-mcp-specialist-agents-multiple-mcp-servers.md) |
| 31 | [MCP timeouts, retries, circuit breakers](docs/31-mcp-timeouts-retries-circuit-breakers.md) |
| 32 | [MCP observability and tracing](docs/32-mcp-observability-distributed-tracing.md) |
| 33 | [FastAPI agent API](docs/33-fastapi-langchain-agent-api.md) |
| 34 | [Production API security](docs/34-production-agent-api-security.md) |
| 35 | [Human approval and safe MCP actions](docs/35-human-in-the-loop-safe-mcp-actions.md) |
| 36 | [PostgreSQL checkpointing and durable approvals](docs/36-postgres-checkpointing-durable-approval-api.md) |
| 37 | [Transactional outbox pattern](docs/37-transactional-outbox-durable-agent-workers.md) |
| 38 | [Async PostgreSQL outbox worker](docs/38-async-postgres-outbox-worker.md) |
| 39 | [Production deployment, recovery, and failure testing](docs/39-production-deployment-recovery-failure-testing.md) |
| 40 | [Integrated DevOps Investigation Agent capstone](docs/40-devops-investigation-agent-capstone.md) |

## Repository structure

- docs/: sequential lessons and reference material.
- examples/: runnable examples, including FastAPI agent API, human approval, durable approvals, and transactional outbox.
- projects/: [DevOps Investigation Agent capstone](projects/devops_investigation_agent/README.md) and architecture decisions.
- checklists/: production-readiness reviews.

## Core principles

- Use current documented APIs and pinned dependencies; LangChain APIs evolve.
- Treat model output and tool arguments as untrusted input.
- A tool call is a request from the model; trusted application code authorizes and executes it.
- Persist state deliberately; memory is not a magical property of an LLM.
- Evaluate RAG retrieval, grounding, and answer quality.
- Use least privilege, timeouts, bounded retries, idempotency, audit logs, and human approval for consequential actions.
- Never commit credentials, personal data, or real production logs.

## Completion plan

The structured 40-lesson course is complete. Lessons 38–40 cover the durable worker, production operations, and integrated capstone plan. Lesson 39 adds a [deployment and recovery checklist](checklists/production-deployment-recovery.md). The capstone components are learning examples and must pass the documented integration gates before being described as one production-ready system. Mastery still requires completing labs, debugging failures, and explaining trade-offs; reading alone cannot guarantee it.

## Official references

- [LangChain](https://python.langchain.com/docs/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Ollama](https://docs.ollama.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Pydantic](https://docs.pydantic.dev/)
