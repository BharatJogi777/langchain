"""Mock write-capable MCP server. All operations are simulations."""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from app.mock_executor import MockOperationsExecutor

mcp = FastMCP("mock-operations")
executor = MockOperationsExecutor(
    os.getenv("OPERATIONS_LEDGER_PATH", "operations_ledger.sqlite3")
)


@mcp.tool()
async def restart_service(
    service: str,
    environment: str,
    change_reference: str,
    idempotency_key: str,
) -> dict:
    """SIMULATE restarting a service. Does not contact real infrastructure."""
    return await executor(
        action="restart_service",
        service=service,
        environment=environment,
        change_reference=change_reference,
        idempotency_key=idempotency_key,
    )


@mcp.tool()
async def rollback_deployment(
    service: str,
    environment: str,
    change_reference: str,
    idempotency_key: str,
) -> dict:
    """SIMULATE rolling back a deployment. Does not contact real infrastructure."""
    return await executor(
        action="rollback_deployment",
        service=service,
        environment=environment,
        change_reference=change_reference,
        idempotency_key=idempotency_key,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
