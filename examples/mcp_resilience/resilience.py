import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def invoke_read_with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    timeout_seconds: float = 5.0,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.25,
    max_delay_seconds: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        OSError,
    ),
) -> T:
    """Invoke a repeatable read operation with timeout and bounded retries."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if base_delay_seconds < 0 or max_delay_seconds < 0:
        raise ValueError("retry delays cannot be negative")

    for attempt in range(1, max_attempts + 1):
        try:
            return await asyncio.wait_for(
                operation(),
                timeout=timeout_seconds,
            )
        except retryable_exceptions:
            if attempt == max_attempts:
                raise

            backoff = min(
                max_delay_seconds,
                base_delay_seconds * (2 ** (attempt - 1)),
            )
            await asyncio.sleep(random.uniform(0, backoff))

    raise RuntimeError("unreachable")
