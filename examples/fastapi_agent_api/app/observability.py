"""Structured logs and OpenTelemetry spans/metrics for investigations."""
from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Iterator

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def get_correlation_id() -> str | None:
    return _correlation_id.get()


@contextmanager
def correlation_scope(correlation_id: str | None = None) -> Iterator[str]:
    value = correlation_id or new_correlation_id()
    token = _correlation_id.set(value)
    try:
        yield value
    finally:
        _correlation_id.reset(token)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        span_context = trace.get_current_span().get_span_context()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
            "trace_id": f"{span_context.trace_id:032x}" if span_context.is_valid else None,
            "span_id": f"{span_context.span_id:016x}" if span_context.is_valid else None,
        }
        for key in ("specialist", "outcome", "duration_seconds", "error_type"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("devops_agent")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


class Observability:
    def __init__(self, *, tracer=None, meter=None, logger=None) -> None:
        self.tracer = tracer
        self.logger = logger or logging.getLogger("devops_agent")
        self.calls = meter.create_counter(
            "agent.specialist.calls",
            description="Number of specialist executions",
        ) if meter else None
        self.duration = meter.create_histogram(
            "agent.specialist.duration",
            unit="s",
            description="Specialist execution duration in seconds",
        ) if meter else None

    @asynccontextmanager
    async def specialist_span(self, specialist: str) -> AsyncIterator[None]:
        started = time.perf_counter()
        outcome = "success"
        if self.tracer is None:
            try:
                yield
            except Exception:
                outcome = "error"
                raise
            finally:
                self._record(specialist, outcome, time.perf_counter() - started)
            return

        with self.tracer.start_as_current_span("specialist.execute") as span:
            span.set_attribute("agent.specialist.name", specialist)
            correlation_id = get_correlation_id()
            if correlation_id:
                span.set_attribute("app.correlation_id", correlation_id)
            try:
                yield
            except Exception as exc:
                outcome = "error"
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                raise
            finally:
                elapsed = time.perf_counter() - started
                span.set_attribute("agent.specialist.outcome", outcome)
                span.set_attribute("agent.specialist.duration_seconds", elapsed)
                self._record(specialist, outcome, elapsed)

    @asynccontextmanager
    async def investigation_span(self, service: str) -> AsyncIterator[None]:
        if self.tracer is None:
            yield
            return
        with self.tracer.start_as_current_span("investigation.run") as span:
            span.set_attribute("service.name", service)
            correlation_id = get_correlation_id()
            if correlation_id:
                span.set_attribute("app.correlation_id", correlation_id)
            yield

    def _record(self, specialist: str, outcome: str, elapsed: float) -> None:
        attributes = {"specialist": specialist, "outcome": outcome}
        if self.calls:
            self.calls.add(1, attributes)
        if self.duration:
            self.duration.record(elapsed, attributes)


def configure_telemetry():
    """Configure console exporters for local learning; use a Collector in production."""
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        ConsoleMetricExporter,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    resource = Resource.create({"service.name": "devops-investigation-agent"})
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    reader = PeriodicExportingMetricReader(
        ConsoleMetricExporter(), export_interval_millis=10_000
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

    logger = configure_logging()
    telemetry = Observability(
        tracer=trace.get_tracer("devops-investigation-agent"),
        meter=metrics.get_meter("devops-investigation-agent"),
        logger=logger,
    )
    return telemetry, tracer_provider, meter_provider
