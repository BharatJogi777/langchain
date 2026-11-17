"""Read-only mock logs MCP server for the specialist-agent lesson."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("logs-server")

LOGS = [
    {"service": "checkout-api", "level": "ERROR", "message": "database pool acquisition timeout"},
    {"service": "checkout-api", "level": "ERROR", "message": "upstream payment request timeout"},
    {"service": "checkout-api", "level": "INFO", "message": "request accepted"},
    {"service": "orders-api", "level": "ERROR", "message": "checkout-api returned 503"},
]


@mcp.tool()
def search_logs(service: str, keyword: str, limit: int = 20) -> list[dict]:
    """Search mock logs for a service and keyword; returns at most 20 records."""
    if not service.strip() or not keyword.strip():
        raise ValueError("service and keyword are required")
    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20")
    matches = [
        row for row in LOGS
        if row["service"] == service and keyword.lower() in row["message"].lower()
    ]
    return matches[:limit]


@mcp.tool()
def count_errors(service: str) -> dict:
    """Count mock ERROR log entries for one service."""
    if not service.strip():
        raise ValueError("service is required")
    count = sum(1 for row in LOGS if row["service"] == service and row["level"] == "ERROR")
    return {"service": service, "error_count": count}


if __name__ == "__main__":
    mcp.run(transport="stdio")
