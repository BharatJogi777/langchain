from __future__ import annotations

import asyncio

import pytest
from langchain_core.tools import StructuredTool

from app.tool_policy import bind_tool_to_service


def test_tool_wrapper_allows_only_authorized_service():
    original = StructuredTool.from_function(
        func=lambda service: {"service": service, "count": 2},
        name="count_errors",
        description="Count errors for a service",
    )
    guarded = bind_tool_to_service(original, "checkout-api")

    result = asyncio.run(guarded.ainvoke({"service": "checkout-api"}))
    assert result == {"service": "checkout-api", "count": 2}


def test_tool_wrapper_rejects_cross_service_arguments():
    original = StructuredTool.from_function(
        func=lambda service: {"service": service},
        name="count_errors",
        description="Count errors for a service",
    )
    guarded = bind_tool_to_service(original, "checkout-api")

    with pytest.raises(PermissionError):
        asyncio.run(guarded.ainvoke({"service": "orders-api"}))


def test_tool_without_service_argument_is_rejected():
    original = StructuredTool.from_function(
        func=lambda keyword: keyword,
        name="search",
        description="Search",
    )
    with pytest.raises(ValueError):
        bind_tool_to_service(original, "checkout-api")
