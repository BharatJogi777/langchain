"""Enforce a service boundary around each model-invoked MCP tool."""
from __future__ import annotations

from langchain_core.tools import BaseTool, StructuredTool


def bind_tool_to_service(tool: BaseTool, authorized_service: str) -> StructuredTool:
    """Return a schema-preserving tool that rejects cross-service arguments.

    The LLM can propose tool arguments, but this wrapper enforces the API
    principal's already-authorized service at the actual tool invocation edge.
    """
    schema = tool.args_schema
    if schema is None:
        raise ValueError(f"Tool {tool.name} has no declared argument schema")
    properties = schema.model_json_schema().get("properties", {})
    if "service" not in properties:
        raise ValueError(f"Tool {tool.name} has no service argument to constrain")

    async def guarded_invoke(**arguments):
        requested_service = arguments.get("service")
        if requested_service != authorized_service:
            raise PermissionError(
                f"Tool {tool.name} is scoped to {authorized_service!r}"
            )
        return await tool.ainvoke(arguments)

    return StructuredTool.from_function(
        name=tool.name,
        description=tool.description,
        args_schema=schema,
        coroutine=guarded_invoke,
    )
