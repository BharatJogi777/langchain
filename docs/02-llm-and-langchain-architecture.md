# LLM fundamentals and LangChain architecture

## LLM mental model
A language model tokenizes input, processes token IDs through learned weights, and predicts a distribution over the next token. Decoding selects a token; generation repeats until a stop condition. Weights encode learned patterns; request context is not durable memory. Temperature affects sampling, not truthfulness. A larger context window does not guarantee correct use of every detail.

## Typical request path
Application builds messages → tokenizer encodes → model generates → provider returns content/metadata/tool-call requests → application validates and uses the result.

## LangChain building blocks
- Model integrations: chat and embedding models.
- Messages: system, human, AI, tool results.
- Prompt templates: reusable message construction.
- Output parsers/structured output: parsing and validation.
- Runnables/LCEL: composition.
- Tools: typed functions the model may request.
- Agents: model-driven tool-selection loops.
- Documents/retrievers: content plus metadata and retrieval interfaces.
- Callbacks/tracing: observability.
- LangGraph: explicit stateful orchestration, checkpoints, interrupts, routing.

## Request is not execution
The model may emit a request such as search_logs(service="payments"). The runtime validates it, invokes trusted application code, captures the result, and returns a tool message. The model does not directly execute Python, SQL, shell, or Kubernetes commands. Your application grants and enforces capabilities.

## Architecture exercise
Draw a sequence diagram for a user question that authenticates, retrieves tenant-scoped documents, calls a model, validates the answer, and returns citations. Mark deterministic code versus LLM decisions. Identify the authorization boundary.

## Selection guide
Use a chain for fixed steps; an agent when adaptive tool choice is useful; LangGraph for explicit branches, retries, parallelism, state, and human review; RAG for grounded search; MCP for standardized external capability interfaces.