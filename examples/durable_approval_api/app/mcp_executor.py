"""Connect the durable workflow to the local mock operations MCP server."""
from __future__ import annotations

import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "servers" / "operations_server.py"


async def build_mcp_executor():
    client = MultiServerMCPClient(
        {
            "operations": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(SERVER)],
            }
        },
        tool_name_prefix=True,
        handle_tool_errors=False,
    )
    tools = await client.get_tools(server_name="operations")
    by_name = {tool.name: tool for tool in tools}
    expected = {"operations_restart_service", "operations_rollback_deployment"}
    if set(by_name) != expected:
        raise RuntimeError(f"Unexpected MCP tool catalog: {sorted(by_name)}")

    async def execute_action(**proposal):
        tool_name = f"operations_{proposal['action']}"
        return await by_name[tool_name].ainvoke({
            "service": proposal["service"],
            "environment": proposal["environment"],
            "change_reference": proposal["change_reference"],
            "idempotency_key": proposal["idempotency_key"],
        })

    return execute_action
