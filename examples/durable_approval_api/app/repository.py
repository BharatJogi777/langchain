from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from psycopg_pool import AsyncConnectionPool


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS approval_requests (
    request_id UUID PRIMARY KEY,
    thread_id TEXT NOT NULL UNIQUE,
    requester_id TEXT NOT NULL,
    action TEXT NOT NULL,
    service TEXT NOT NULL,
    environment TEXT NOT NULL,
    reason TEXT NOT NULL,
    change_reference TEXT NOT NULL,
    status TEXT NOT NULL,
    decision TEXT,
    approver_id TEXT,
    approver_role TEXT,
    decision_comment TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS approval_audit_events (
    event_id BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL REFERENCES approval_requests(request_id),
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS approval_requests_status_expiry_idx
    ON approval_requests(status, expires_at);
CREATE INDEX IF NOT EXISTS approval_audit_request_idx
    ON approval_audit_events(request_id, event_id);
"""


class ApprovalRepository:
    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    async def setup(self) -> None:
        async with self.pool.connection() as conn:
            # Execute DDL individually to avoid multi-command prepared-statement issues.
            for statement in SCHEMA_SQL.split(';'):
                if statement.strip():
                    await conn.execute(statement)
            await conn.commit()

    async def create(
        self,
        *,
        request_id: UUID,
        thread_id: str,
        requester_id: str,
        proposal: dict[str, Any],
        expires_in_minutes: int,
    ) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO approval_requests
                (request_id, thread_id, requester_id, action, service,
                 environment, reason, change_reference, status, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending',
                        now() + (%s * interval '1 minute'))
                """,
                (
                    request_id, thread_id, requester_id, proposal["action"],
                    proposal["service"], proposal["environment"], proposal["reason"],
                    proposal["change_reference"], expires_in_minutes,
                ),
            )
            await conn.execute(
                """
                INSERT INTO approval_audit_events
                (request_id, actor_id, event_type, event_data)
                VALUES (%s, %s, 'proposal_created', %s::jsonb)
                """,
                (request_id, requester_id, json.dumps(proposal)),
            )
            await conn.commit()

    async def get(self, request_id: UUID):
        async with self.pool.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM approval_requests WHERE request_id = %s",
                (request_id,),
            )
            return await cursor.fetchone()

    async def record_decision(
        self,
        *,
        request_id: UUID,
        approver_id: str,
        approver_role: str,
        decision: str,
        comment: str,
    ):
        """Atomically record one decision; safe to retry after API process restart."""
        async with self.pool.connection() as conn:
            async with conn.transaction():
                cursor = await conn.execute(
                    """
                    SELECT status, requester_id, environment, expires_at,
                           decision, approver_id, approver_role, decision_comment
                    FROM approval_requests
                    WHERE request_id = %s
                    FOR UPDATE
                    """,
                    (request_id,),
                )
                row = await cursor.fetchone()
                if row is None:
                    return None, "not_found"
                if row["requester_id"] == approver_id:
                    return None, "self_approval"
                if row["environment"] == "production" and approver_role != "incident_commander":
                    return None, "production_role_required"
                if row["status"] == "expired":
                    return None, "expired"
                if row["expires_at"] <= datetime.now(timezone.utc):
                    await conn.execute(
                        "UPDATE approval_requests SET status='expired', updated_at=now() WHERE request_id=%s",
                        (request_id,),
                    )
                    await conn.execute(
                        """
                        INSERT INTO approval_audit_events
                        (request_id, actor_id, event_type)
                        VALUES (%s, %s, 'approval_expired')
                        """,
                        (request_id, approver_id),
                    )
                    return None, "expired"
                if row["status"] in {"decision_recorded", "completed", "rejected"}:
                    if row["decision"] == decision and row["approver_id"] == approver_id:
                        return row, "duplicate"
                    return None, "already_decided"
                if row["status"] != "pending":
                    return None, "not_pending"

                await conn.execute(
                    """
                    UPDATE approval_requests
                    SET status='decision_recorded', decision=%s, approver_id=%s,
                        approver_role=%s, decision_comment=%s, updated_at=now()
                    WHERE request_id=%s
                    """,
                    (decision, approver_id, approver_role, comment, request_id),
                )
                await conn.execute(
                    """
                    INSERT INTO approval_audit_events
                    (request_id, actor_id, event_type, event_data)
                    VALUES (%s, %s, 'approval_decided', %s::jsonb)
                    """,
                    (
                        request_id, approver_id,
                        json.dumps({"decision": decision, "role": approver_role, "comment": comment}),
                    ),
                )
                return row, "recorded"

    async def mark_result(self, request_id: UUID, status: str, actor_id: str, result: dict):
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE approval_requests SET status=%s, updated_at=now() WHERE request_id=%s",
                (status, request_id),
            )
            await conn.execute(
                """
                INSERT INTO approval_audit_events
                (request_id, actor_id, event_type, event_data)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (request_id, actor_id, f"workflow_{status}", json.dumps(result, default=str)),
            )
            await conn.commit()

    async def audit(self, request_id: UUID):
        async with self.pool.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT event_id, actor_id, event_type, event_data, created_at
                FROM approval_audit_events
                WHERE request_id=%s ORDER BY event_id
                """,
                (request_id,),
            )
            return await cursor.fetchall()
