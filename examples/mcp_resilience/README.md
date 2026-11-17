# MCP resilience helper example

This example demonstrates a transport-independent bounded retry helper for repeatable asynchronous read operations.

## Run

From the repository root:

~~~bash
python -m unittest discover -s examples/mcp_resilience -p "test_*.py" -v
~~~

The helper retries only configured exception types, uses a per-attempt timeout, and applies bounded exponential backoff with jitter.

It is intentionally not wired to a specific MCP adapter exception class. Inspect the exact exception types from your pinned MCP SDK and langchain-mcp-adapters version, then map only known transient transport failures at the application boundary. Do not retry every exception or blindly retry side-effecting operations.

A timeout cancels the local awaitable; it does not prove that a remote server did not complete an operation.
