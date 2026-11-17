# Course roadmap

## Outcome

Build, test, secure, evaluate, deploy, and operate production LangChain applications. Reading alone does not create mastery: complete labs, troubleshoot failures, and explain design trade-offs.

## Core sequence

1. Environment and version discipline
2. LLM fundamentals and LangChain architecture
3. Chat models, messages, invocation, streaming, batching
4. Prompt templates and context engineering
5. Structured output, parsers, Pydantic validation
6. Runnables and LCEL composition
7. Tools, schemas, tool calling, error handling
8. Agents, bounded loops, middleware, human approval
9. State, checkpointers, stores, memory engineering
10. Document loading and ingestion
11. Chunking strategies
12. Embeddings and vector search
13. RAG architecture, grounding, citations
14. Advanced RAG and evaluation
15. MCP clients, servers, transports, security, multi-server composition, resilience
16. LangGraph and multi-agent orchestration
17. FastAPI application architecture
18. Testing, evaluation, observability
19. Production security, reliability, cost, deployment
20. Capstone and mastery assessment

## Advanced extension sequence

- Lessons 21–29: MCP integration, reliability, LangGraph workflows, state, routing, fan-out, subgraphs, supervisor patterns, and structured routing.
- [Lesson 30 — Multiple MCP Specialist Agents](30-specialist-agents-multiple-mcp-servers.md)
- [Lesson 31 — MCP Resilience](31-mcp-timeouts-retries-circuit-breakers.md)
- [Lesson 32 — MCP Observability](32-mcp-observability-distributed-tracing.md)
- [Lesson 33 — FastAPI Agent API](33-fastapi-langchain-agent-api.md)
- [Lesson 34 — Production API Security](34-production-agent-api-security.md)
- [Lesson 35 — Human Approval and Safe MCP Actions](35-human-in-the-loop-safe-mcp-actions.md)
- [Lesson 36 — PostgreSQL Checkpointing and Durable Approval APIs](36-postgres-checkpointing-durable-approval-api.md)
- [Lesson 37 — Transactional Outbox](37-transactional-outbox-durable-agent-workers.md)
- [Lesson 38 — Async PostgreSQL Outbox Worker](38-async-postgres-outbox-worker.md)
- [Lesson 39 — Production Deployment, Recovery, and Failure Testing](39-production-deployment-recovery-failure-testing.md).
- Lesson 40 — Integrated DevOps Investigation Agent capstone and mastery assessment (planned).

## Prerequisites

Python functions, classes, typing, exceptions, virtual environments, modules, async/await; HTTP/JSON; SQL; basic Docker. The course explains embeddings and RAG from first principles.

## Learning loop

Read → draw the flow → type and run code → inspect intermediate state → change a requirement → test success and failure → document trade-offs → explain without notes.

## Choose the right abstraction

- Model + prompt: one request/response.
- LCEL: deterministic composable pipeline.
- Agent: model selects among approved tools.
- LangGraph: explicit stateful workflow, branches, retries, interrupts, persistence.
- RAG: retrieve trusted evidence and provide it to a model.
- MCP: protocol for capability discovery and invocation; not an agent framework.

## Exit criteria

Do not mark a topic complete because you read it. Complete its lab, add tests, explain failure modes, and implement a small variation without copying.

## Official references

- [LangChain](https://python.langchain.com/docs/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [MCP](https://modelcontextprotocol.io/)
- [Ollama](https://docs.ollama.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
