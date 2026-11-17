from mcp.server.fastmcp import FastMCP

mcp = FastMCP("infrastructure-server")

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
