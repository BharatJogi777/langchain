# Model Context Protocol (MCP)

## Concepts
MCP standardizes how a client discovers and invokes server capabilities such as tools, resources, and prompts. It does not replace authentication, authorization, business logic, or orchestration. The host application decides which servers and tools are trusted.

## Example server

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("Read-only DevOps Demo")
@mcp.tool()
def get_service_status(service: str) -> dict:
    """Return a mocked service status."""
    allowed = {"checkout", "payments", "orders"}
    if service not in allowed:
        raise ValueError("Unknown service")
    return {"service": service, "status": "degraded", "source": "demo"}
if __name__ == "__main__":
    mcp.run(transport="stdio")
```

## LangChain adapter pattern
Install MCP SDK and langchain-mcp-adapters. Configure MultiServerMCPClient with a server transport, retrieve tools asynchronously, then pass those tools to create_agent. Example transport/configuration changes across adapter versions; follow current docs for the installed version. For local stdio, the client starts the server process; do not separately start the same process unless the transport design requires it.

## Multiple servers
Group by trust boundary and responsibility: logs, Kubernetes read-only, metrics, ticketing. Expose only necessary tools to each agent. Enforce allowlists and authorization per tool.

## Security
Use TLS and authentication for remote transports. Restrict network egress and filesystem access. Validate inputs/outputs. Set timeouts, quotas, and response-size limits. Treat MCP results as untrusted. Pin server versions. Never expose unrestricted production shell access.

## Lab
Create separate log and pod-health MCP servers, connect both to one agent, and test that an unauthorized namespace is rejected by server code.