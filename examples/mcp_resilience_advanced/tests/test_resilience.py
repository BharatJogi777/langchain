from __future__ import annotations

import asyncio
import unittest

from app.investigation import investigate
from app.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    ResilientExecutor,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ResilienceTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_failure_is_retried(self):
        calls = 0

        async def operation():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ConnectionError("temporary")
            return "ok"

        async def no_sleep(_seconds):
            return None

        executor = ResilientExecutor(
            name="metrics",
            max_attempts=3,
            sleep=no_sleep,
            random_uniform=lambda low, high: 0,
        )
        self.assertEqual(await executor.run(operation), "ok")
        self.assertEqual(calls, 3)
        self.assertEqual(executor.breaker.state, CircuitState.CLOSED)

    async def test_non_retryable_error_is_not_retried(self):
        calls = 0

        async def operation():
            nonlocal calls
            calls += 1
            raise ValueError("invalid input")

        executor = ResilientExecutor(name="logs", max_attempts=4)
        with self.assertRaises(ValueError):
            await executor.run(operation)
        self.assertEqual(calls, 1)
        self.assertEqual(executor.breaker.state, CircuitState.CLOSED)

    async def test_timeout_is_retried_and_eventually_succeeds(self):
        calls = 0

        async def operation():
            nonlocal calls
            calls += 1
            if calls == 1:
                await asyncio.sleep(0.03)
            return "recovered"

        executor = ResilientExecutor(
            name="infra",
            timeout_seconds=0.005,
            max_attempts=2,
            sleep=_no_sleep,
        )
        self.assertEqual(await executor.run(operation), "recovered")
        self.assertEqual(calls, 2)

    async def test_breaker_opens_and_rejects_calls(self):
        clock = FakeClock()
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_seconds=5,
            clock=clock,
        )
        executor = ResilientExecutor(
            name="logs",
            breaker=breaker,
            max_attempts=1,
        )

        async def fail():
            raise ConnectionError("offline")

        with self.assertRaises(ConnectionError):
            await executor.run(fail)
        self.assertEqual(breaker.state, CircuitState.OPEN)
        with self.assertRaises(CircuitOpenError):
            await executor.run(fail)

    async def test_half_open_probe_can_recover(self):
        clock = FakeClock()
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_seconds=5,
            clock=clock,
        )
        await breaker.acquire_permission()
        await breaker.record_failure()
        self.assertEqual(breaker.state, CircuitState.OPEN)

        clock.advance(6)
        await breaker.acquire_permission()
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)
        await breaker.record_success()
        self.assertEqual(breaker.state, CircuitState.CLOSED)

    async def test_partial_report_keeps_successful_specialist_evidence(self):
        async def logs(_incident, _service, _task):
            return "two timeout records"

        async def metrics(_incident, _service, _task):
            raise ConnectionError("internal detail should not leak")

        specialists = {"logs_agent": logs, "metrics_agent": metrics}
        executors = {
            name: ResilientExecutor(name=name, max_attempts=1)
            for name in specialists
        }
        result = await investigate(
            incident="checkout latency",
            service="checkout-api",
            specialists=specialists,
            executors=executors,
        )
        self.assertIn("two timeout records", result["report"])
        self.assertIn("metrics_agent", result["unavailable"])
        self.assertNotIn("internal detail should not leak", result["report"])
        self.assertTrue(result["partial"])


async def _no_sleep(_seconds):
    return None


if __name__ == "__main__":
    unittest.main()
