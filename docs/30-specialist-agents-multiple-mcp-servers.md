# Lesson 30 — Specialist Agents Connected to Multiple MCP Servers

## 1. Goal

Lesson 29 introduced an LLM-powered supervisor and mock specialist workers. This lesson replaces those mock workers with specialist agents backed by three independent MCP servers:

- **Logs MCP server:** searches application logs and counts errors.
- **Metrics MCP server:** returns latency and resource measurements.
- **Infrastructure MCP server:** checks service health and recent deployments.

Each specialist receives only the tools from its own server. The supervisor routes the investigation; specialists gather evidence; the final report combines their findings.

## 2. Architecture

```text
                    Incident
                       |
                       v
              LangGraph Supervisor
               structured routing
                 /      |      \
                v       v       v
             Logs    Metrics  Infrastructure
             agent    agent       agent
               |       |           |
               v       v           v
           Logs MCP  Metrics MCP  Infra MCP
            server    server      server
               \       |           /
                +------v----------+
                  Evidence state
                       |
                       v
                  Final report
```

The MCP servers are separate processes using stdio for this local learning example. The client discovers each server's tools and converts them into LangChain tools. The agents then use only their assigned tool lists. The adapter supports multiple named server connections and can retrieve tools for an individual server. Tool name prefixing helps make tool provenance clear. See the official [MultiServerMCPClient reference](https://reference.langchain.com/python/langchain-mcp-adapters/client/MultiServerMCPClient) and [multiple-server guide](https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/mcp/connections.mdx). 

## 3. Project structure

```text
examples/langgraph_mcp_specialists/
├── main.py
├── requirements.txt
├── README.md
├── app/
│   ├── __init__.py
│   └── graph.py
├── servers/
│   ├── __init__.py
│   ├── logs_server.py
│   ├── metrics_server.py
│   └── infrastructure_server.py
└── tests/
    ├── __init__.py
    └── test_graph.py
```

## 4. Install

Use Python 3.12 and a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r examples/langgraph_mcp_specialists/requirements.txt
ollama pull llama3.2:3b
```

Ollama must be running locally. The example defaults to `llama3.2:3b`; set `OLLAMA_MODEL` to use another local model.

## 5. Understand the server/client boundary

Each MCP server owns its tools and data access. The client configuration maps a server name to a process command. `MultiServerMCPClient.get_tools(server_name="logs")` retrieves only the tools exposed by the logs server. The same pattern is used for metrics and infrastructure.

The adapter can also retrieve all tools from every configured server. That is useful for a single agent with a broad tool catalog, but this lesson deliberately avoids that approach: **do not give every specialist every tool**.

The example uses `tool_name_prefix=True`. This namespaces discovered tool names by server, reducing collisions and making provenance visible. The adapter's `handle_tool_errors` behavior defaults to converting MCP tool execution errors into error-status tool messages; transport and session failures still raise exceptions. See the [adapter reference](https://reference.langchain.com/python/langchain-mcp-adapters/client/MultiServerMCPClient).

## 6. Read the implementation in this order

1. `servers/*.py`: inspect the tools and their input contracts.
2. `main.py`: inspect server process configuration and per-server tool discovery.
3. `app/graph.py`: inspect route validation, specialist execution, and graph state.
4. `tests/test_graph.py`: inspect deterministic tests that do not need Ollama or live MCP processes.

The specialist agents are created with `create_agent(model=..., tools=...)`. Each agent receives only one server's discovered tools. Its final answer is captured as a finding and returned to the graph supervisor.

## 7. Run

From the repository root:

```bash
python examples/langgraph_mcp_specialists/main.py
```

The MCP server processes are started by the client using the current Python interpreter. You do not need to start the three stdio servers manually.

Run deterministic graph tests:

```bash
PYTHONPATH=examples/langgraph_mcp_specialists pytest -q examples/langgraph_mcp_specialists/tests
```

These tests use fake route models and specialist executors. They do not need Ollama or MCP subprocesses. The main program is the live integration smoke test.

## 8. Execution sequence

1. Application configures the three MCP server connections.
2. Client discovers tools separately for logs, metrics, and infrastructure.
3. Application creates three specialist agents, each with a scoped tool list.
4. LangGraph starts at the supervisor.
5. Supervisor model returns a structured route proposal.
6. Python validates the route, visited-agent list, task size, and remaining delegation budget.
7. LangGraph invokes the chosen specialist.
8. Specialist agent chooses among its approved MCP tools and receives their results.
9. Specialist output is added to graph findings.
10. Control returns to the supervisor; it either chooses another specialist or finishes.
11. Finalize node produces a report from the collected evidence.

## 9. Security model: tool scoping is necessary, not sufficient

The example uses read-only mock tools. For a real environment:

- Give each server its own service identity and least-privilege credentials.
- Enforce authorization inside the MCP server; hiding a tool from an agent is not an authorization boundary.
- Scope every query by tenant, account, environment, and allowed service.
- Validate service names against an application-owned allow-list.
- Bound query time ranges, result sizes, and log text length.
- Apply per-tool timeouts, concurrency limits, and bounded retries.
- Treat log lines, deployment descriptions, and tool output as untrusted content; they can contain prompt injection.
- Never pass raw secrets or unrestricted credentials to a model.
- Keep investigation tools read-only. Put remediation in a separate workflow with explicit authorization and human approval.
- Record audit events: actor, server, tool, resource scope, timestamp, outcome, duration, and correlation ID.

A specialist having access to a read-only tool does not mean it is safe to expose every record that tool can retrieve. Authorization and data filtering belong at the server/backend boundary.

## 10. Error handling

There are two important classes of failure:

**Tool execution error:** the server received the request and returned an MCP error result. With the adapter's default `handle_tool_errors=True`, the error is surfaced to the agent as an error-status tool message, allowing the agent to respond or recover.

**Transport/session error:** the process is unavailable, the connection fails, or the protocol response is invalid. These failures raise outside normal tool-result handling. Catch them at the orchestration boundary, record a sanitized error, and decide whether a bounded retry or partial report is appropriate.

Do not retry every error. Validation errors and authorization denials should generally not be retried. Use deadlines and idempotency if a future tool has side effects.

## 11. Tests and what they prove

The unit tests verify:
- the supervisor can route to a specialist and continue;
- a finish decision creates a report;
- repeated specialist routing is rejected;
- exhausted budgets bypass model routing;
- failed routing closes safely;
- a missing specialist executor is rejected during graph construction.

They do not prove that a live MCP server starts correctly, that the local model makes accurate decisions, or that a real backend enforces authorization. Run the integration example and add contract tests against your own MCP servers before deployment.

## 12. Exercises

1. Add a database MCP server with a read-only `explain_query` tool that accepts only a pre-approved query identifier—not arbitrary SQL.
2. Add a database specialist and route to it from the supervisor.
3. Add a tool-level result limit and test it.
4. Simulate an unavailable metrics server. Produce a partial report that clearly labels missing evidence.
5. Add a correlation ID to graph state and include it in every specialist request.
6. Add a service allow-list on the MCP server, not only in the prompt.
7. Explain why a specialist should not receive the combined tools from all three servers.

## 13. Knowledge check

1. What does `get_tools(server_name="metrics")` return?
2. Why does this design use three specialist agents instead of one agent with every MCP tool?
3. Where must authorization be enforced?
4. How does an MCP tool execution error differ from a transport failure?
5. Why are read-only tools preferable for the investigation stage?
6. What must change before an agent can safely execute remediation?

## Completion criteria

You can run the three MCP servers through the client, explain how each specialist is scoped to its own tool catalog, trace a tool call from the model to the server and back, and explain the authorization boundary.

## References

- [MultiServerMCPClient API](https://reference.langchain.com/python/langchain-mcp-adapters/client/MultiServerMCPClient)
- [LangChain MCP multiple connections](https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/mcp/connections.mdx)
- [LangChain MCP tools and error handling](https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/mcp/tools.mdx)
- [LangChain MCP adapter repository](https://github.com/langchain-ai/langchain-mcp-adapters)
