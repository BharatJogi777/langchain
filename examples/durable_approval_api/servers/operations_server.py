"""Mock write-capable MCP tools; no real infrastructure calls."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the example package importable when this file is launched as a stdio child process.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.fastmcp import FastMCP

from app.mock_executor import MockOperationsExecutor

mcp = FastMCP("durable-mock-operations")
executor = MockOperationsExecutor(os.getenv("OPERATIONS_LEDGER_PATH", "durable_operations.sqlite3"))


@mcp.tool()
async def restart_service(service: str, environment: str, change_reference: str,
                          idempotency_key: str) -> dict:
    """SIMULATE a service restart; does not contact infrastructure."""
    return await executor(
        action="restart_service", service=service, environment=environment,
        change_reference=change_reference, idempotency_key=idempotency_key,
    )


@mcp.tool()
async def rollback_deployment(service: str, environment: str, change_reference: str,
                              idempotency_key: str) -> dict:
    """SIMULATE a deployment rollback; does not contact infrastructure."""
    return await executor(
        action="rollback_deployment", service=service, environment=environment,
        change_reference=change_reference, idempotency_key=idempotency_key,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
