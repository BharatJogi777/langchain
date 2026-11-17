"""Read-only mock metrics MCP server for the specialist-agent lesson."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("metrics-server")

METRICS = {
    "checkout-api": {"request_rate_per_minute": 820, "error_rate_percent": 4.2, "p95_latency_ms": 1850, "cpu_percent": 38.0, "memory_percent": 71.0},
    "orders-api": {"request_rate_per_minute": 460, "error_rate_percent": 0.3, "p95_latency_ms": 210, "cpu_percent": 26.0, "memory_percent": 48.0},
}


@mcp.tool()
def get_service_metrics(service: str) -> dict:
    """Return mock request rate, error rate, latency, CPU, and memory metrics."""
    if not service.strip():
        raise ValueError("service is required")
    data = METRICS.get(service)
    if data is None:
        return {"service": service, "found": False}
    return {"service": service, "found": True, **data}


@mcp.tool()
def get_latency_percentiles(service: str) -> dict:
    """Return mock p50, p95, and p99 request latency in milliseconds."""
    if not service.strip():
        raise ValueError("service is required")
    if service not in METRICS:
        return {"service": service, "found": False}
    p95 = METRICS[service]["p95_latency_ms"]
    return {"service": service, "found": True, "p50_ms": round(p95 * 0.18), "p95_ms": p95, "p99_ms": round(p95 * 1.35)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
