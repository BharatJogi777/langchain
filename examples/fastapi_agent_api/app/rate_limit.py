"""Small in-process sliding-window limiter for a single-process learning API."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """Limit calls per key; use Redis or a gateway for multi-worker production."""

    def __init__(self, *, limit: int, window_seconds: float) -> None:
        if limit < 1 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> int | None:
        """Return retry-after seconds, or None when the call is permitted."""
        now = time.monotonic()
        async with self._lock:
            events = self._events[key]
            cutoff = now - self.window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return max(1, int(self.window_seconds - (now - events[0]) + 0.999))
            events.append(now)
            return None
