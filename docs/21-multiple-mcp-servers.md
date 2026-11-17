# Lesson 21 — Connecting Multiple MCP Servers to One LangChain Agent

## Learning objectives

By the end of this lesson, you should be able to:

1. Explain why an application may use multiple MCP servers.
2. Configure `MultiServerMCPClient` with more than one server.
3. Discover tools from all configured servers.
4. Pass the combined tools to LangChain's `create_agent`.
5. Understand the difference between stateless tool calls and explicitly managed MCP sessions.
6. Diagnose common connection, discovery, and tool-execution failures.

## 1. The architecture

A DevOps investigation agent may need logs, infrastructure health, metrics, deployments, and incident records. These capabilities should not all be implemented in one enormous MCP server.

For this lesson:

- **Logs MCP server** exposes `search_logs` and `count_errors`.
- **Infrastructure MCP server** exposes `check_service_health` and `get_cpu_usage`.
- **LangChain agent** receives the tools discovered from both servers.

The MCP client is the integration layer. It connects to each server, discovers tools, and presents those tools to the agent. The model chooses which tool to call; the MCP server executes the selected tool.

## 2. Project structure

```text
multi_mcp_servers/
├── .venv/
├── requirements.txt
├── servers/
│   ├── logs_server.py
│   └── infrastructure_server.py
└── app/
    └── main.py
```

## 3. Environment setup

Use Python 3.12 in a virtual environment. From the project root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create `requirements.txt`:

```text
langchain
langchain-ollama
langchain-mcp-adapters
mcp
```

The packages evolve independently. For a team or production deployment, validate the combination, then pin tested versions in a lock file rather than assuming that an unpinned install is reproducible.

Ensure Ollama is running and the model is available:

```bash
ollama pull llama3.2:3b
ollama list
```

## 4. MCP server 1: logs

Create `servers/logs_server.py`:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("logs-server")

# Mock data for learning. Replace this with a controlled log backend later.
LOGS = [
    {"service": "payment-service", "level": "ERROR", "message": "database connection timeout"},
    {"service": "payment-service", "level": "ERROR", "message": "payment provider timeout"},
    {"service": "payment-service", "level": "INFO", "message": "request accepted"},
    {"service": "order-service", "level": "ERROR", "message": "payment-service returned 503"},
]


@mcp.tool()
def search_logs(service: str, keyword: str) -> list[dict]:
    """Search mock application logs by service name and message keyword."""
    service_lower = service.lower()
    keyword_lower = keyword.lower()

    return [
        entry
        for entry in LOGS
        if entry["service"].lower() == service_lower
        and keyword_lower in entry["message"].lower()
    ]


@mcp.tool()
def count_errors(service: str) -> int:
    """Count ERROR-level entries for the specified service."""
    return sum(
        1
        for entry in LOGS
        if entry["service"].lower() == service.lower()
        and entry["level"] == "ERROR"
    )


if __name__ == "__main__":
    # MCP stdio transport uses stdout for the protocol.
    # Do not add print() debugging to stdout in an MCP stdio server.
    mcp.run(transport="stdio")
```

## 5. MCP server 2: infrastructure

Create `servers/infrastructure_server.py`:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("infrastructure-server")

# Mock data only. These tools do not inspect or change real infrastructure.
SERVICES = {
    "payment-service": {"status": "degraded", "cpu_percent": 87.5},
    "order-service": {"status": "healthy", "cpu_percent": 32.0},
}


@mcp.tool()
def check_service_health(service: str) -> dict:
    """Return the mock health status for a named service."""
    result = SERVICES.get(service.lower())

    if result is None:
        return {"service": service, "status": "unknown", "found": False}

    return {"service": service, "status": result["status"], "found": True}


@mcp.tool()
def get_cpu_usage(service: str) -> dict:
    """Return mock CPU utilization percentage for a named service."""
    result = SERVICES.get(service.lower())

    if result is None:
        return {"service": service, "cpu_percent": None, "found": False}

    return {
        "service": service,
        "cpu_percent": result["cpu_percent"],
        "found": True,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

## 6. Connect both servers to one LangChain agent

Create `app/main.py`:

```python
import asyncio
import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    client = MultiServerMCPClient(
        {
            "logs": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(PROJECT_ROOT / "servers" / "logs_server.py")],
            },
            "infrastructure": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [
                    str(PROJECT_ROOT / "servers" / "infrastructure_server.py")
                ],
            },
        }
    )

    # Discover tools exposed by every configured server.
    tools = await client.get_tools()

    print("Discovered tools:")
    for tool in tools:
        print(f"- {tool.name}: {tool.description}")

    model = ChatOllama(
        model="llama3.2:3b",
        temperature=0,
    )

    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=(
            "You are a cautious DevOps investigation assistant. "
            "Use available tools to gather evidence before drawing conclusions. "
            "Clearly distinguish tool results from hypotheses. "
            "Never claim that mock data represents a real production system."
        ),
    )

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Investigate payment-service. Search its logs for "
                        "timeout errors, count its errors, check its health, "
                        "and inspect its CPU usage. Summarize the evidence."
                    ),
                }
            ]
        }
    )

    print("\nAgent response:")
    print(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
```

## 7. Run the project

Run these commands from the project root:

```bash
python app/main.py
```

You should see four discovered tools:

- `search_logs`
- `count_errors`
- `check_service_health`
- `get_cpu_usage`

The exact wording and order of the model's tool calls can vary. Verify that the final answer is supported by the returned tool results; do not grade the exercise only by whether the model uses a particular sequence.

## 8. Understand what happens internally

1. Your application constructs a `MultiServerMCPClient` with two named server configurations.
2. `get_tools()` connects to the configured servers and discovers their tool definitions.
3. The adapter converts the discovered MCP tools into LangChain-compatible tools.
4. `create_agent()` receives the combined tool list.
5. The model decides whether to call one or more tools.
6. The adapter routes each tool call to the server that exposed that tool.
7. Tool results are returned to the agent, which can reason over them and produce a response.

The model does not directly open MCP connections. Your application and adapter manage those connections.

## 9. Stateless calls versus persistent sessions

The example uses the simple `get_tools()` pattern. In the adapter's default stateless mode, tool invocations are handled using sessions managed by the adapter; do not assume that a server-side session or in-memory state persists between calls.

Some workflows require an explicitly managed session. The adapter also supports opening a named session and loading tools from it:

```python
from langchain_mcp_adapters.tools import load_mcp_tools

async with client.session("logs") as session:
    session_tools = await load_mcp_tools(session)
    # Use session_tools while this session remains open.
```

Use the session pattern when you need session-scoped behavior or resources. Keep the session open for the complete period in which its tools are used. Consult the installed adapter version's documentation for supported transports and session options.

## 10. Common errors and troubleshooting

| Symptom | What to check |
|---|---|
| Server process exits immediately | Run the server directly and inspect stderr; verify imports and Python environment. |
| No tools discovered | Confirm each server calls `mcp.run(transport="stdio")` and has decorated tool functions. |
| Module not found | Activate the same virtual environment used by the client and server processes. |
| Ollama connection error | Check that Ollama is running and the model is present with `ollama list`. |
| Agent ignores a tool | Improve the tool description and user task; inspect discovered tool names and results. |
| Debug output corrupts stdio | Do not print logs to stdout in a stdio MCP server; use stderr or proper logging. |

## 11. Production design principles

This example uses mock data and is for learning only. Before connecting real systems:

- Give each MCP server a narrow responsibility and least-privilege credentials.
- Prefer read-only tools for investigation agents.
- Validate every tool input and cap result sizes.
- Apply timeouts, retries with bounded backoff, and concurrency limits.
- Avoid returning secrets, tokens, personal data, or entire log payloads.
- Record tool name, server identity, duration, outcome, and correlation ID.
- Treat tool output as untrusted data; it may contain malicious or misleading text.
- Do not let log content override system instructions or authorize actions.
- Add tests for successful calls, malformed input, server unavailability, and oversized output.
- Use explicit approval and separate authorization for any future write or remediation tool.

## 12. Exercises

Complete these before moving on:

1. Add a third MCP server named `metrics` with a `get_memory_usage(service)` tool.
2. Connect all three servers using the same client.
3. Print every discovered tool's name and description.
4. Ask the agent to investigate `order-service` using both logs and infrastructure tools.
5. Temporarily change one server's script path to an invalid path. Observe and explain the failure.
6. Add input validation that rejects an empty service name.
7. Explain why a tool call should not be trusted just because the model requested it.

## 13. Knowledge check

1. What is the responsibility of `MultiServerMCPClient`?
2. Does the LLM connect directly to MCP servers?
3. Where does tool selection happen?
4. How does the adapter know which MCP server should execute a selected tool?
5. Why should stdio MCP servers avoid printing debug messages to stdout?
6. When would you use an explicitly managed MCP session?
7. Why should a production investigation agent begin with read-only tools?

**Completion criteria:** You can run the project, explain the complete request path, add a third server without changing the agent's core logic, and diagnose a failed server connection.

## Next lesson

After completing this lesson, continue with MCP tool errors, timeouts, retries, and resilient orchestration across multiple servers. Then move to LangGraph state and production agent workflows.
