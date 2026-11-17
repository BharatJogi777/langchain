"""Async outbox worker with fenced updates and bounded retries."""
from __future__ import annotations
import asyncio
import random
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

class Repository(Protocol):
    async def claim_batch(self, **kwargs: Any) -> list[dict[str, Any]]: ...
    async def get_approval(self, request_id: UUID) -> dict[str, Any] | None: ...
    async def mark_delivered(self, **kwargs: Any) -> bool: ...
    async def schedule_retry(self, **kwargs: Any) -> bool: ...
    async def mark_dead(self, **kwargs: Any) -> bool: ...

class ApprovalResumer(Protocol):
    async def resume(self, *, thread_id: str, decision: str,
                     reviewer_id: str, proposal_sha256: str) -> None: ...

class PermanentEventError(Exception):
    """Invalid event; retrying cannot repair it."""

def retry_delay_seconds(attempt: int, *, rng=random.random) -> float:
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    ceiling = min(300.0, 2.0 * (2 ** min(attempt - 1, 30)))
    return rng() * ceiling

class OutboxWorker:
    def __init__(self, repository: Repository, resumer: ApprovalResumer, *,
                 worker_id: str, poll_seconds: float = 1.0,
                 batch_size: int = 10, lease_seconds: int = 60,
                 max_attempts: int = 8):
        if not worker_id or poll_seconds <= 0 or batch_size < 1:
            raise ValueError("invalid worker configuration")
        self.repository, self.resumer = repository, resumer
        self.worker_id, self.poll_seconds = worker_id, poll_seconds
        self.batch_size, self.lease_seconds = batch_size, lease_seconds
        self.max_attempts = max_attempts
        self._stopping = asyncio.Event()

    def stop(self) -> None:
        self._stopping.set()

    async def run(self) -> None:
        while not self._stopping.is_set():
            token = uuid4()
            events = await self.repository.claim_batch(
                worker_id=self.worker_id, claim_token=token,
                batch_size=self.batch_size, lease_seconds=self.lease_seconds,
                max_attempts=self.max_attempts,
            )
            if not events:
                try:
                    await asyncio.wait_for(self._stopping.wait(), self.poll_seconds)
                except asyncio.TimeoutError:
                    pass
                continue
            for event in events:
                if self._stopping.is_set():
                    return
                await self.process_event(event, claim_token=token)

    async def process_event(self, event: dict[str, Any], *, claim_token: UUID) -> None:
        fence = {
            "event_id": event["event_id"],
            "worker_id": self.worker_id,
            "claim_token": claim_token,
        }
        try:
            if event["event_type"] != "resume_approval_workflow":
                raise PermanentEventError("unsupported_event_type")
            approval = await self.repository.get_approval(event["request_id"])
            if approval is None:
                raise PermanentEventError("approval_missing")
            if approval["status"] != "decision_recorded":
                await self.repository.mark_delivered(**fence)
                return
            if approval["expires_at"] <= datetime.now(timezone.utc):
                raise PermanentEventError("approval_expired")
            if event["payload"].get("payload_sha256") != approval["payload_sha256"]:
                raise PermanentEventError("proposal_hash_mismatch")
            if approval["decision"] not in {"approve", "reject"}:
                raise PermanentEventError("invalid_decision")
            await self.resumer.resume(
                thread_id=approval["thread_id"], decision=approval["decision"],
                reviewer_id=approval["decided_by"],
                proposal_sha256=approval["payload_sha256"],
            )
            await self.repository.mark_delivered(**fence)
        except asyncio.CancelledError:
            raise
        except PermanentEventError as exc:
            await self.repository.mark_dead(**fence, error_code=str(exc))
        except Exception:
            # Persist a safe error code, never raw exception text or secrets.
            delay = retry_delay_seconds(max(1, int(event["attempts"])))
            await self.repository.schedule_retry(
                **fence, delay_seconds=delay,
                error_code="transient_handler_error",
                max_attempts=self.max_attempts,
            )
