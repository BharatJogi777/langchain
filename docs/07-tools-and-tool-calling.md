# Tools and tool calling

## Lifecycle
1. Register a function with a name, description, and input schema.
2. The model sees the available tools and may request one.
3. Runtime validates the request and invokes trusted code.
4. Tool result is returned as a ToolMessage.
5. Model uses result or requests another tool.

```python
from langchain.tools import tool
@tool
def calculate_total(values: list[float]) -> float:
    """Return the sum of supplied numeric values."""
    if len(values) > 100:
        raise ValueError("At most 100 values are allowed")
    return sum(values)
```

Function signatures and docstrings help create the tool schema. Prefer explicit typed arguments; variadic signatures such as *numbers are awkward for JSON tool calling. Test the Python function independently of the model.

## Tool design rules
One narrow responsibility; clear name/docstring; typed bounded inputs; authorization inside service/tool code; concise bounded output; read-only by default; separate proposal from execution; timeout, rate limit, audit, idempotency. Never expose arbitrary shell, SQL, filesystem, or unrestricted HTTP access.

## Error classes
Validation/permission errors should not retry. Transient network failures may use bounded backoff. Missing resources return safe not-found results. Timeouts stop work. Unexpected errors return a correlation ID to the user and details only to protected logs. Do not expose stack traces, credentials, or internal hostnames.

## Tests
Invalid schema, unauthorized tenant, timeout, duplicate invocation, oversized result, and external-system outage. Small local models may produce malformed tool arguments; schema validation is mandatory.

## Lab
Create read-only tools for log search, pod status, and database connection metrics using mock adapters. Enforce service allowlists, caller authorization, time windows, and response-size limits.