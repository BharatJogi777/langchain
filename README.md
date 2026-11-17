# Production-Grade LangChain Mastery

A structured, hands-on curriculum for learning modern LangChain from foundations to production AI applications. The course uses Python, Ollama (for local learning), FastAPI, PostgreSQL/pgvector, and MCP. Provider-specific examples are kept portable.

> **Learning promise:** completing the lessons, labs, assessments, and capstone should give you the skills to design, build, test, operate, and explain production LangChain applications. No document can guarantee mastery by reading alone: mastery comes from implementing, debugging, measuring, and reviewing the projects.

## Start here

1. Read [the course roadmap](docs/00-roadmap.md).
2. Follow [the setup guide](docs/01-environment-setup.md).
3. Study each module in order. Do not skip the labs.
4. Build the capstone described in [the production project guide](projects/devops-investigation-agent/README.md).

## Course map

| Module | Subject |
|---|---|
| 00 | Roadmap, prerequisites, and learning method |
| 01 | Environment, packages, versions, and local Ollama |
| 02 | LLM fundamentals and LangChain architecture |
| 03 | Models, messages, invocation, streaming, and batching |
| 04 | Prompt templates, chat prompts, and prompt management |
| 05 | Output parsing, structured output, and validation |
| 06 | Runnables, LCEL, composition, branching, and async |
| 07 | Tools, schemas, tool calling, and error handling |
| 08 | Agents, agent loops, middleware, and human approval |
| 09 | State, checkpointers, stores, and memory engineering |
| 10 | Document loading, metadata, and ingestion |
| 11 | Text splitting and chunking strategies |
| 12 | Embeddings, vector search, and vector databases |
| 13 | RAG architecture, retrieval, grounding, and citations |
| 14 | Advanced RAG: hybrid search, reranking, evaluation |
| 15 | MCP clients, servers, transports, security, [multiple servers](docs/21-multiple-mcp-servers.md), and [resilience](docs/22-mcp-reliability.md) |
| 21 | [Multiple MCP servers](docs/21-multiple-mcp-servers.md) |
| 22 | [MCP reliability](docs/22-mcp-reliability.md) |
| 23 | [LangGraph production workflows](docs/23-langgraph-production-workflows.md) |
| 24 | [LangGraph state, reducers, and checkpointing](docs/24-langgraph-state-reducers-checkpointing.md) |
| 25 | [LangGraph conditional routing and loops](docs/25-langgraph-conditional-routing-loops.md) |
| 26 | [LangGraph dynamic fan-out with Send and map-reduce](docs/26-langgraph-dynamic-fanout-send-map-reduce.md) |
| 27 | [LangGraph subgraphs and multi-agent architecture](docs/27-langgraph-subgraphs-multi-agent-architecture.md) |
| 28 | [LangGraph supervisor pattern and agent handoffs](docs/28-langgraph-supervisor-agent-handoffs.md) |
| 29 | [LLM-powered supervisor with structured routing](docs/29-llm-powered-supervisor-structured-routing.md) |
| 30 | [Specialist agents connected to multiple MCP servers](docs/30-specialist-agents-multiple-mcp-servers.md) |
| 31 | [MCP timeouts, retries, circuit breakers, and failure recovery](docs/31-mcp-timeouts-retries-circuit-breakers.md) |
| 32 | [MCP observability and distributed tracing](docs/32-mcp-observability-distributed-tracing.md) |
| 16 | Multi-agent patterns and LangGraph orchestration |
| 17 | FastAPI integration and application architecture |
| 18 | Testing, evaluation, observability, and tracing |
| 19 | Production security, reliability, cost, and deployment |
| 20 | Capstone, interview questions, and mastery checklist |

## Repository structure

- `docs/`: sequential lessons and reference material.
- `examples/`: small runnable examples, including [multiple MCP servers](examples/multi_mcp_servers/), [MCP resilience](examples/mcp_resilience/), and [LangGraph workflows](examples/langgraph_workflows/), and [LangGraph state/checkpointing](examples/langgraph_state/), and [LangGraph routing/loops](examples/langgraph_routing/), and [LangGraph Send/map-reduce](examples/langgraph_send/), and [LangGraph subgraphs](examples/langgraph_subgraphs/), and [LangGraph supervisor and handoffs](examples/langgraph_supervisor/), and [LLM-powered supervisor routing](examples/langgraph_llm_supervisor/), and [MCP-backed specialist agents](examples/langgraph_mcp_specialists/), and [advanced MCP resilience](examples/mcp_resilience_advanced/), and [MCP observability](examples/mcp_observability/).
- `projects/`: end-to-end capstone and architecture.
- `checklists/`: review gates for production readiness.

## Core principles

- Use the current documented APIs for the versions pinned in each example; LangChain APIs evolve.
- Prefer explicit model objects such as `ChatOllama(...)` over ambiguous provider inference.
- Treat model output and tool arguments as untrusted input. Validate at every boundary.
- A tool call is a request from the model; trusted application code performs the action.
- Memory is not a magical property of an LLM. Persist and scope state deliberately.
- RAG quality depends on ingestion, retrieval, context construction, and evaluation—not merely adding a vector database.
- Use least privilege, timeouts, retries with limits, idempotency, audit logs, and human approval for consequential actions.
- Never commit API keys, passwords, production logs, personal data, or real infrastructure credentials.

## Suggested pace

A focused learner can work through the material in 6–10 weeks at 1–2 hours per day. Move at the pace required to complete labs and explain trade-offs, not by calendar.

## Version policy

LangChain, LangGraph, provider integrations, and MCP packages change. Start with the setup guide, use a virtual environment, pin tested dependencies, and consult the linked official documentation when an API differs. Do not mix snippets from different major versions without checking compatibility.

## Official references

- [LangChain documentation](https://python.langchain.com/docs/)
- [LangGraph documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain integrations](https://python.langchain.com/docs/integrations/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Ollama documentation](https://docs.ollama.com/)
- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [Pydantic documentation](https://docs.pydantic.dev/)
