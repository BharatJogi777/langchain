"""Async PostgreSQL repository for the Lesson 38 worker."""
from __future__ import annotations
from typing import Any
from uuid import UUID
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

CLAIM_SQL = """
WITH candidates AS (
    SELECT event_id FROM approval_outbox
    WHERE (status = 'pending' OR (status = 'processing' AND locked_until < now()))
      AND available_at <= now() AND attempts < %s
    ORDER BY available_at, created_at
    FOR UPDATE SKIP LOCKED LIMIT %s
)
UPDATE approval_outbox AS o
SET status = 'processing', locked_by = %s, claim_token = %s,
    locked_until = now() + (%s * interval '1 second'), attempts = attempts + 1
FROM candidates WHERE o.event_id = candidates.event_id
RETURNING o.*;
"""

class OutboxRepository:
    def __init__(self, database_url: str, *, min_size: int = 1, max_size: int = 5):
        self.pool = AsyncConnectionPool(
            conninfo=database_url, min_size=min_size, max_size=max_size,
            open=False, kwargs={"row_factory": dict_row},
        )

    async def open(self) -> None:
        await self.pool.open()
        await self.pool.wait()

    async def close(self) -> None:
        await self.pool.close()

    async def claim_batch(self, *, worker_id: str, claim_token: UUID,
                          batch_size: int = 10, lease_seconds: int = 60,
                          max_attempts: int = 8) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            async with conn.transaction():
                # A worker may crash on its final permitted attempt. Once its
                # lease expires, quarantine it instead of leaving it stuck.
                await conn.execute(
                    """UPDATE approval_outbox
                       SET status='dead', last_error='retry_budget_exhausted',
                           locked_by=NULL, locked_until=NULL, claim_token=NULL
                       WHERE status='processing' AND locked_until < now()
                         AND attempts >= %s""",
                    (max_attempts,),
                )
                cur = await conn.execute(
                    CLAIM_SQL,
                    (max_attempts, batch_size, worker_id, claim_token, lease_seconds),
                )
                return await cur.fetchall()

    async def get_approval(self, request_id: UUID) -> dict[str, Any] | None:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT request_id, thread_id, status, payload_sha256,
                          decision, decided_by, expires_at
                   FROM approval_requests WHERE request_id = %s""",
                (request_id,),
            )
            return await cur.fetchone()

    async def mark_delivered(self, *, event_id: UUID, worker_id: str,
                             claim_token: UUID) -> bool:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """UPDATE approval_outbox
                   SET status='delivered', delivered_at=now(),
                       locked_by=NULL, locked_until=NULL, claim_token=NULL
                   WHERE event_id=%s AND status='processing'
                     AND locked_by=%s AND claim_token=%s RETURNING event_id""",
                (event_id, worker_id, claim_token),
            )
            return await cur.fetchone() is not None

    async def schedule_retry(self, *, event_id: UUID, worker_id: str,
                             claim_token: UUID, delay_seconds: float,
                             error_code: str, max_attempts: int = 8) -> bool:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """UPDATE approval_outbox
                   SET status=CASE WHEN attempts >= %s THEN 'dead' ELSE 'pending' END,
                       available_at=now() + (%s * interval '1 second'),
                       last_error=%s, locked_by=NULL, locked_until=NULL, claim_token=NULL
                   WHERE event_id=%s AND status='processing'
                     AND locked_by=%s AND claim_token=%s RETURNING status""",
                (max_attempts, delay_seconds, error_code, event_id, worker_id, claim_token),
            )
            return await cur.fetchone() is not None

    async def mark_dead(self, *, event_id: UUID, worker_id: str,
                        claim_token: UUID, error_code: str) -> bool:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """UPDATE approval_outbox
                   SET status='dead', last_error=%s, locked_by=NULL,
                       locked_until=NULL, claim_token=NULL
                   WHERE event_id=%s AND status='processing'
                     AND locked_by=%s AND claim_token=%s RETURNING event_id""",
                (error_code, event_id, worker_id, claim_token),
            )
            return await cur.fetchone() is not None
