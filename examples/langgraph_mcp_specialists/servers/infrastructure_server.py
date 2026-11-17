"""Read-only mock infrastructure MCP server for the specialist-agent lesson."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("infrastructure-server")

SERVICES = {
    "checkout-api": {"status": "degraded", "region": "ap-south-1"},
    "orders-api": {"status": "healthy", "region": "ap-south-1"},
}
DEPLOYMENTS = {
    "checkout-api": [{"version": "2026.11.18.2", "status": "completed", "minutes_ago": 24}],
    "orders-api": [{"version": "2026.11.17.4", "status": "completed", "minutes_ago": 960}],
}


@mcp.tool()
def check_service_health(service: str) -> dict:
    """Return mock service health and region information."""
    if not service.strip():
        raise ValueError("service is required")
    result = SERVICES.get(service)
    if result is None:
        return {"service": service, "found": False, "status": "unknown"}
    return {"service": service, "found": True, **result}


@mcp.tool()
def get_recent_deployments(service: str) -> list[dict]:
    """Return up to five mock deployment records for the service."""
    if not service.strip():
        raise ValueError("service is required")
    return DEPLOYMENTS.get(service, [])[:5]


if __name__ == "__main__":
    mcp.run(transport="stdio")
