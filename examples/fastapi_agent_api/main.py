"""Uvicorn entry point for the FastAPI DevOps investigation service."""
from __future__ import annotations

from app.api import create_app
from app.observability import configure_telemetry, configure_logging
from app.runtime import build_runtime

telemetry, tracer_provider, meter_provider = configure_telemetry()
logger = configure_logging()


async def runtime_factory():
    return await build_runtime(telemetry)


app = create_app(
    runtime_factory=runtime_factory,
    meter=__import__("opentelemetry").metrics.get_meter("devops-investigation-api"),
    tracer_provider=tracer_provider,
    meter_provider=meter_provider,
    instrument_http=True,
)
