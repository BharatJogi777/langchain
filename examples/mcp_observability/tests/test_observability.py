from __future__ import annotations

import io
import json
import logging
import unittest

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.observability import (
    JsonLogFormatter,
    Observability,
    correlation_scope,
    get_correlation_id,
    new_correlation_id,
)


class ObservabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_correlation_scope_sets_and_restores_context(self):
        self.assertIsNone(get_correlation_id())
        with correlation_scope("test-correlation-123") as value:
            self.assertEqual(value, "test-correlation-123")
            self.assertEqual(get_correlation_id(), value)
        self.assertIsNone(get_correlation_id())

    async def test_correlation_id_is_unique(self):
        self.assertNotEqual(new_correlation_id(), new_correlation_id())

    async def test_json_log_contains_correlation_id(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonLogFormatter())
        logger = logging.getLogger("observability-test")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        with correlation_scope("corr-abc"):
            logger.info("specialist completed", extra={"specialist": "logs_agent"})
        record = json.loads(stream.getvalue())
        self.assertEqual(record["correlation_id"], "corr-abc")
        self.assertEqual(record["message"], "specialist completed")
        self.assertEqual(record["specialist"], "logs_agent")

    async def test_specialist_span_records_success(self):
        provider = TracerProvider()
        exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        telemetry = Observability(tracer=provider.get_tracer("test"))

        with correlation_scope("corr-span"):
            async with telemetry.specialist_span("logs_agent"):
                pass

        spans = exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].name, "specialist.execute")
        self.assertEqual(spans[0].attributes["agent.specialist.name"], "logs_agent")
        self.assertEqual(spans[0].attributes["app.correlation_id"], "corr-span")
        provider.shutdown()

    async def test_specialist_span_records_error(self):
        provider = TracerProvider()
        exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        telemetry = Observability(tracer=provider.get_tracer("test"))

        with self.assertRaises(ValueError):
            async with telemetry.specialist_span("metrics_agent"):
                raise ValueError("synthetic failure")

        span = exporter.get_finished_spans()[0]
        self.assertEqual(span.status.status_code.name, "ERROR")
        provider.shutdown()


if __name__ == "__main__":
    unittest.main()
