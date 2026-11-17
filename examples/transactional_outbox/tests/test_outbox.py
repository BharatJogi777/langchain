from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from outbox import (
    OutboxEvent,
    OutboxStatus,
    can_retry,
    is_lease_expired,
    retry_delay_seconds,
)


def test_retry_delay_uses_full_jitter():
    assert retry_delay_seconds(1, rng=lambda: 0.5) == 1.0
    assert retry_delay_seconds(3, rng=lambda: 0.5) == 4.0


def test_retry_delay_is_capped():
    assert retry_delay_seconds(20, cap=10, rng=lambda: 1.0) == 10


def test_invalid_attempt_is_rejected():
    with pytest.raises(ValueError):
        retry_delay_seconds(0)


def test_retry_budget_is_bounded():
    assert can_retry(7, max_attempts=8)
    assert not can_retry(8, max_attempts=8)


def test_expired_lease_can_be_reclaimed():
    now = datetime.now(timezone.utc)
    event = OutboxEvent(
        event_id=uuid4(), request_id=uuid4(), event_type="resume",
        status=OutboxStatus.PROCESSING, attempts=2,
        available_at=now - timedelta(seconds=5),
        locked_by="worker-a", locked_until=now - timedelta(seconds=1),
    )
    assert is_lease_expired(event, now=now)


def test_active_lease_is_not_expired():
    now = datetime.now(timezone.utc)
    event = OutboxEvent(
        event_id=uuid4(), request_id=uuid4(), event_type="resume",
        status=OutboxStatus.PROCESSING, attempts=1,
        available_at=now, locked_by="worker-a",
        locked_until=now + timedelta(seconds=30),
    )
    assert not is_lease_expired(event, now=now)
