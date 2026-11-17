# Testing, evaluation, observability

## Test pyramid
Unit: prompt formatting, schemas, tool functions, chunking, metadata filters. Component: model/retriever/vector store/MCP adapters with fakes. Integration: database, Ollama/provider, MCP server, API. Evaluation: quality datasets. Load/chaos: concurrency, provider outage, DB saturation, slow tools.

Do not make every unit test call a live LLM. Model outputs are probabilistic, slow, and costly. Mock deterministic logic; maintain a separately managed live evaluation suite.

## Agent/RAG evaluation
Was the right tool selected? Were arguments valid? Was unauthorized action blocked? Did answer use supplied evidence? Are citations correct? Did agent stop within limits? Did it abstain when evidence was missing? LLM-as-judge scores are signals, not ground truth; use human review for high impact cases.

## Observability fields
Trace/run ID, request ID, safe pseudonymous tenant/user ID, model/provider, prompt version, tool name/duration/status/retries, retrieval count and source IDs, token usage/cost, stage and end-to-end latency, exceptions/cancellation. Avoid logging full prompts, raw documents, secrets, or personal data without approval and protection.

LangSmith can trace LangChain runs and support datasets/evaluation. OpenTelemetry and standard logs/metrics/traces provide broader application observability. Choose based on governance, integration, and cost.

## Lab
Add trace IDs and structured logs to FastAPI RAG. Build 20-question regression set including unanswerable/adversarial cases. Track p50/p95 latency and quality.