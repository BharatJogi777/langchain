"""Uvicorn entry point for the FastAPI DevOps investigation service."""
from __future__ import annotations

from app.api import create_app
from opentelemetry import metrics

from app.observability import configure_telemetry
from app.runtime import build_runtime

telemetry, tracer_provider, meter_provider = configure_telemetry()


async def runtime_factory():
    return await build_runtime(telemetry)


app = create_app(
    runtime_factory=runtime_factory,
    meter=metrics.get_meter("devops-investigation-api"),
    tracer_provider=tracer_provider,
    meter_provider=meter_provider,
    instrument_http=True,
)
