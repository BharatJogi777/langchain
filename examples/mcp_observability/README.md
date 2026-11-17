# MCP observability example

This example adds structured JSON logs, correlation IDs, OpenTelemetry spans, and specialist-call metrics to the multi-MCP DevOps investigation architecture. It reuses the read-only MCP servers from Lesson 30 and resilience wrapper from Lesson 31.

## Requirements

- Python 3.12+
- Ollama running locally with a chat model
- Lesson 30 and Lesson 31 example directories in this repository

## Install and run

From the repository root:

~~~bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/mcp_observability/requirements.txt
ollama pull llama3.2:3b
python examples/mcp_observability/main.py
~~~

The example emits JSON logs and console-exported OpenTelemetry spans/metrics. Metric export is periodic (10 seconds), so a short run may flush metrics during shutdown.

## Run tests

~~~bash
PYTHONPATH=examples/mcp_observability python -m unittest discover -s examples/mcp_observability/tests -v
~~~

Tests use an in-memory span exporter and do not require Ollama, MCP subprocesses, or a telemetry backend.

## Optional LangSmith tracing

~~~bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="your-key"
export LANGSMITH_PROJECT="devops-investigation-learning"
~~~

Never commit credentials. Review trace privacy, redaction, and retention before enabling hosted tracing for real production data.

## Important boundaries

- Correlation IDs are application request identifiers; trace IDs and span IDs are OpenTelemetry identifiers.
- The example creates app-level investigation/specialist spans. It does not automatically instrument each MCP tool call.
- Do not assume trace context automatically crosses MCP stdio subprocess boundaries. Add explicit propagation and server-side instrumentation if you need end-to-end spans across those processes.
- Metric attributes use bounded specialist/outcome values. Never use prompts, correlation IDs, trace IDs, or arbitrary user identifiers as metric labels.
- Console exporters are for local learning. Use an OpenTelemetry Collector and production backend with batching, timeouts, access controls, and retention policies.

See [Lesson 32](../../docs/32-mcp-observability-distributed-tracing.md) for the complete explanation.
