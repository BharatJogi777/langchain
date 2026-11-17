# Course roadmap

## Outcome
Build, test, secure, evaluate, deploy, and operate production LangChain applications. Reading alone does not create mastery: complete the labs, troubleshoot failures, and explain design trade-offs.

## Sequence
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
15. MCP clients, servers, transports, security
16. LangGraph and multi-agent orchestration
17. FastAPI application architecture
18. Testing, evaluation, observability
19. Production security, reliability, cost, deployment
20. Capstone and mastery assessment

## Current hands-on extension: multiple MCP servers
After learning the one-server MCP integration, complete [Lesson 21 — Multiple MCP Servers](21-multiple-mcp-servers.md). It connects separate logs and infrastructure servers to one LangChain agent and includes a runnable example in `examples/multi_mcp_servers/`.

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
LangChain: https://python.langchain.com/docs/ ; LangGraph: https://langchain-ai.github.io/langgraph/ ; MCP: https://modelcontextprotocol.io/ ; Ollama: https://docs.ollama.com/ ; FastAPI: https://fastapi.tiangolo.com/ .
