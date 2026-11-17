"""Testable retry and claim helpers for the Lesson 37 outbox lab."""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Optional
from uuid import UUID


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    DEAD = "dead"


@dataclass(frozen=True)
class OutboxEvent:
    event_id: UUID
    request_id: UUID
    event_type: str
    status: OutboxStatus
    attempts: int
    available_at: datetime
    locked_by: Optional[str] = None
    locked_until: Optional[datetime] = None


CLAIM_SQL = """
WITH candidates AS (
    SELECT event_id
    FROM approval_outbox
    WHERE (status = 'pending'
       OR (status = 'processing' AND locked_until < now()))
      AND available_at <= now()
    ORDER BY available_at, created_at
    FOR UPDATE SKIP LOCKED
    LIMIT %s
)
UPDATE approval_outbox AS o
SET status = 'processing',
    locked_by = %s,
    claim_token = %s,
    locked_until = now() + (%s * interval '1 second'),
    attempts = attempts + 1
FROM candidates
WHERE o.event_id = candidates.event_id
RETURNING o.*;
"""


def retry_delay_seconds(attempt: int, *, base: float = 2.0,
                        cap: float = 300.0, rng=random.random) -> float:
    """Full-jitter exponential backoff with a bounded exponent."""
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    if base <= 0 or cap <= 0:
        raise ValueError("base and cap must be positive")
    ceiling = min(cap, base * (2 ** min(attempt - 1, 30)))
    return rng() * ceiling


def can_retry(attempts: int, *, max_attempts: int = 8) -> bool:
    if attempts < 0 or max_attempts < 1:
        raise ValueError("invalid retry budget")
    return attempts < max_attempts


def is_lease_expired(event: OutboxEvent, *, now: datetime) -> bool:
    return (
        event.status == OutboxStatus.PROCESSING
        and event.locked_until is not None
        and event.locked_until <= now
    )
