# FastAPI integration and service architecture

## Separation of concerns
API routes handle HTTP validation, authentication, and response mapping. Application services orchestrate use cases. LangChain layer owns prompts/chains/agents/retrievers. Tool adapters connect external systems. Persistence owns conversations/checkpoints/documents/audit. Infrastructure owns configuration, logging, tracing, and clients.

## Layout
app/main.py; config.py; api/routes/{chat,documents,health}.py; schemas/; services/; llm/{models,prompts,chains,agents}.py; tools/; retrieval/; repositories/; observability/; tests/{unit,integration,evals}/.

## Endpoint examples
POST /v1/chat; GET /v1/conversations/{id}; POST /v1/documents; GET /v1/documents/{id}; POST /v1/documents/{id}/reprocess; GET /health/live; GET /health/ready. Use Pydantic request/response models. Define streaming and cancellation semantics before exposing streaming endpoints.

## Async correctness
Use ainvoke in async endpoints when supported. Do not block the event loop with sync network/database calls. Bound expensive model calls. Use a worker queue for long ingestion. Initialize reusable clients in application lifespan and close them cleanly.

## Reliability
Authenticate and authorize before loading state/retrieval. Add request-size/rate limits, timeouts, cancellation, correlation IDs, idempotency, backpressure, graceful shutdown, and health checks.

## Lab
Expose a RAG chain through FastAPI with auth dependency, request validation, fake-model unit tests, integration tests, and per-user rate limits.