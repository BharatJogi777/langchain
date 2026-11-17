# Advanced MCP resilience example

This example wraps the Lesson 30 logs, metrics, and infrastructure specialists with per-specialist timeouts, bounded retries, exponential backoff with jitter, and an in-process circuit breaker. Specialists run independently, so a failed dependency produces a partial report instead of erasing successful evidence.

## Requirements

- Python 3.12+
- Ollama running locally
- The Lesson 30 MCP server files in this same repository
- A local Ollama chat model (default: `llama3.2:3b`)

## Install and run

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/mcp_resilience_advanced/requirements.txt
ollama pull llama3.2:3b
python examples/mcp_resilience_advanced/main.py
```

Choose a different local model with `OLLAMA_MODEL`.

## Run deterministic tests

```bash
PYTHONPATH=examples/mcp_resilience_advanced python -m unittest discover -s examples/mcp_resilience_advanced/tests -v
```

Tests use fake operations and do not require Ollama, network access, or MCP subprocesses.

## Important design boundaries

- Only `TimeoutError`, `ConnectionError`, and `OSError` are retryable by default. Verify actual exception types from your pinned MCP SDK and adapter before adding mappings.
- Do not retry validation, authentication, authorization, or domain errors.
- Do not blindly retry side-effecting tools. A client timeout does not prove the server did not complete the operation.
- `CircuitBreaker` is in-memory and process-local. Use shared state or a mature library when multiple workers must coordinate.
- The example's specialist timeout is 20 seconds per attempt. Add an overall investigation deadline before exposing it through a production API.
- MCP tool execution errors and transport/session errors are different. With `handle_tool_errors=True`, execution errors can be returned to the agent as error-status tool messages; transport/session failures still raise.

See [Lesson 31](../../docs/31-mcp-timeouts-retries-circuit-breakers.md) for the detailed walkthrough and production checklist.
