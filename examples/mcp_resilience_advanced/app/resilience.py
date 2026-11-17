"""Timeouts, bounded retries, and an in-process circuit breaker."""
from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when a dependency circuit is open or a probe is already running."""


class CircuitBreaker:
    """Single-process breaker; use shared state for multi-worker coordination."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_seconds: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if recovery_seconds <= 0:
            raise ValueError("recovery_seconds must be positive")
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: float | None = None
        self._probe_in_flight = False
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def acquire_permission(self) -> None:
        async with self._lock:
            if self._state == CircuitState.OPEN:
                assert self._opened_at is not None
                if self._clock() - self._opened_at < self.recovery_seconds:
                    raise CircuitOpenError("circuit is open")
                self._state = CircuitState.HALF_OPEN

            if self._state == CircuitState.HALF_OPEN:
                if self._probe_in_flight:
                    raise CircuitOpenError("half-open probe already in progress")
                self._probe_in_flight = True

    async def record_success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._opened_at = None
            self._probe_in_flight = False
            self._state = CircuitState.CLOSED

    async def record_failure(self) -> None:
        async with self._lock:
            self._probe_in_flight = False
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()
                return

            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()


class ResilientExecutor:
    """Run a repeatable async operation with timeout, retries, and a breaker."""

    def __init__(
        self,
        *,
        name: str,
        breaker: CircuitBreaker | None = None,
        timeout_seconds: float = 5.0,
        max_attempts: int = 2,
        base_delay_seconds: float = 0.2,
        max_delay_seconds: float = 1.0,
        retryable_exceptions: tuple[type[Exception], ...] = (
            TimeoutError,
            ConnectionError,
            OSError,
        ),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random_uniform: Callable[[float, float], float] = random.uniform,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if base_delay_seconds < 0 or max_delay_seconds < 0:
            raise ValueError("retry delays cannot be negative")
        self.name = name
        self.breaker = breaker or CircuitBreaker()
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.retryable_exceptions = retryable_exceptions
        self._sleep = sleep
        self._random_uniform = random_uniform

    async def run(self, operation: Callable[[], Awaitable[T]]) -> T:
        await self.breaker.acquire_permission()
        try:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    result = await asyncio.wait_for(
                        operation(),
                        timeout=self.timeout_seconds,
                    )
                except self.retryable_exceptions:
                    if attempt >= self.max_attempts:
                        raise
                    cap = min(
                        self.max_delay_seconds,
                        self.base_delay_seconds * (2 ** (attempt - 1)),
                    )
                    if cap:
                        await self._sleep(self._random_uniform(0.0, cap))
                except Exception:
                    # A non-retryable response proves the dependency responded;
                    # do not count validation/auth/domain errors as outages.
                    await self.breaker.record_success()
                    raise
                else:
                    await self.breaker.record_success()
                    return result

            raise RuntimeError("retry loop exited unexpectedly")
        except self.retryable_exceptions:
            await self.breaker.record_failure()
            raise
        except BaseException:
            # Release a HALF_OPEN probe if the caller cancels the task.
            if self.breaker.state == CircuitState.HALF_OPEN:
                await self.breaker.record_failure()
            raise
