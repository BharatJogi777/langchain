"""FastAPI application factory with request correlation and HTTP metrics."""
from __future__ import annotations

import logging
import re
import time
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.observability import correlation_scope, new_correlation_id

logger = logging.getLogger("devops_agent")
_CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str = Field(min_length=2, max_length=100, pattern=r"^[a-zA-Z0-9._-]+$")
    incident: str = Field(min_length=5, max_length=2000)
    task: str = Field(
        default="Collect read-only logs, metrics, and infrastructure evidence.",
        min_length=5,
        max_length=1000,
    )


class InvestigationResponse(BaseModel):
    service: str
    report: str
    partial: bool
    evidence: dict[str, str]
    unavailable: dict[str, str]
    correlation_id: str


Investigator = Callable[..., Awaitable[dict[str, Any]]]
RuntimeFactory = Callable[[], Awaitable[tuple[Investigator, Callable[[], Awaitable[None]]]]]


def create_app(
    *,
    runtime_factory: RuntimeFactory,
    meter=None,
    tracer_provider=None,
    meter_provider=None,
    instrument_http: bool = True,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        investigator, cleanup = await runtime_factory()
        app.state.investigator = investigator
        app.state.runtime_ready = True
        try:
            yield
        finally:
            app.state.runtime_ready = False
            try:
                await cleanup()
            finally:
                if tracer_provider is not None:
                    tracer_provider.shutdown()
                if meter_provider is not None:
                    meter_provider.shutdown()

    app = FastAPI(
        title="DevOps Investigation Agent API",
        version="1.0.0",
        lifespan=lifespan,
    )

    request_counter = meter.create_counter(
        "http.server.requests",
        description="HTTP requests handled by the agent API",
    ) if meter else None
    request_duration = meter.create_histogram(
        "http.server.duration",
        unit="s",
        description="HTTP server request duration",
    ) if meter else None

    @app.middleware("http")
    async def correlation_and_metrics(request: Request, call_next):
        supplied = request.headers.get("x-correlation-id", "")
        correlation_id = supplied if _CORRELATION_PATTERN.fullmatch(supplied) else new_correlation_id()
        request.state.correlation_id = correlation_id
        started = time.perf_counter()
        status_code = 500
        route_label = request.url.path
        try:
            with correlation_scope(correlation_id):
                response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            route = request.scope.get("route")
            if route is not None:
                route_label = getattr(route, "path", route_label)
            attributes = {
                "http.request.method": request.method,
                "http.route": route_label,
                "http.response.status_class": f"{status_code // 100}xx",
            }
            elapsed = time.perf_counter() - started
            if request_counter:
                request_counter.add(1, attributes)
            if request_duration:
                request_duration.record(elapsed, attributes)

    if instrument_http:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(
                app,
                tracer_provider=tracer_provider,
                meter_provider=meter_provider,
            )
        except ImportError as exc:
            raise RuntimeError(
                "Install opentelemetry-instrumentation-fastapi to enable HTTP tracing"
            ) from exc

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        correlation_id = getattr(request.state, "correlation_id", None) or new_correlation_id()
        logger.exception(
            "unhandled API exception",
            extra={"outcome": "error", "error_type": type(exc).__name__},
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "correlation_id": correlation_id,
            },
            headers={"X-Correlation-ID": correlation_id},
        )

    @app.get("/health/live")
    async def liveness():
        return {"status": "alive"}

    @app.get("/health/ready")
    async def readiness(request: Request):
        if not getattr(request.app.state, "runtime_ready", False):
            raise HTTPException(status_code=503, detail="Runtime is not ready")
        return {"status": "ready"}

    @app.post(
        "/v1/investigations",
        response_model=InvestigationResponse,
    )
    async def create_investigation(
        payload: InvestigationRequest,
        request: Request,
    ):
        if not getattr(request.app.state, "runtime_ready", False):
            raise HTTPException(status_code=503, detail="Runtime is not ready")
        result = await request.app.state.investigator(
            incident=payload.incident,
            service=payload.service,
            task=payload.task,
        )
        return InvestigationResponse(
            service=payload.service,
            report=result["report"],
            partial=result["partial"],
            evidence=result["evidence"],
            unavailable=result["unavailable"],
            correlation_id=request.state.correlation_id,
        )

    return app
