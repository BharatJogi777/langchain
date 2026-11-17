from mcp.server.fastmcp import FastMCP

mcp = FastMCP("logs-server")

LOGS = [
    {"service": "payment-service", "level": "ERROR", "message": "database connection timeout"},
    {"service": "payment-service", "level": "ERROR", "message": "payment provider timeout"},
    {"service": "payment-service", "level": "INFO", "message": "request accepted"},
    {"service": "order-service", "level": "ERROR", "message": "payment-service returned 503"},
]


@mcp.tool()
def search_logs(service: str, keyword: str) -> list[dict]:
    """Search mock application logs by service name and message keyword."""
    return [
        entry
        for entry in LOGS
        if entry["service"].lower() == service.lower()
        and keyword.lower() in entry["message"].lower()
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
    mcp.run(transport="stdio")
