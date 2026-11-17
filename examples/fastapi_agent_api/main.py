"""Uvicorn entry point for the secured FastAPI DevOps investigation API."""
from __future__ import annotations

from app.api import create_app
from app.observability import configure_telemetry
from app.rate_limit import SlidingWindowRateLimiter
from app.runtime import build_runtime
from app.security import build_demo_security_from_environment
from opentelemetry import metrics

telemetry, tracer_provider, meter_provider = configure_telemetry()
security = build_demo_security_from_environment()


async def runtime_factory():
    return await build_runtime(telemetry)


app = create_app(
    runtime_factory=runtime_factory,
    security=security,
    rate_limiter=SlidingWindowRateLimiter(limit=5, window_seconds=60),
    meter=metrics.get_meter("devops-investigation-api"),
    tracer_provider=tracer_provider,
    meter_provider=meter_provider,
    instrument_http=True,
)
