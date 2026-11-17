"""Mock operations executor with a local SQLite idempotency ledger.

This module deliberately does not connect to Kubernetes, cloud APIs, or production.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class MockOperationsExecutor:
    def __init__(self, database_path: str | Path = "operations_ledger.sqlite3"):
        self.database_path = str(database_path)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS operation_results (
                    idempotency_key TEXT PRIMARY KEY,
                    action_payload TEXT NOT NULL,
                    result_payload TEXT NOT NULL
                )
                """
            )

    async def __call__(
        self,
        *,
        action: str,
        service: str,
        environment: str,
        change_reference: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        payload = {
            "action": action,
            "service": service,
            "environment": environment,
            "change_reference": change_reference,
        }
        payload_json = json.dumps(payload, sort_keys=True)

        # The mock operation and ledger insert share a transaction. A real
        # external API must itself accept an idempotency key or use an outbox.
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT action_payload, result_payload FROM operation_results "
                "WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                if existing[0] != payload_json:
                    raise ValueError("Idempotency key reused for a different action")
                return json.loads(existing[1])

            result = {
                "executed": True,
                "mode": "simulation",
                "action": action,
                "service": service,
                "environment": environment,
                "change_reference": change_reference,
                "message": f"SIMULATED {action} for {service} in {environment}",
            }
            connection.execute(
                "INSERT INTO operation_results "
                "(idempotency_key, action_payload, result_payload) VALUES (?, ?, ?)",
                (idempotency_key, payload_json, json.dumps(result, sort_keys=True)),
            )
            connection.commit()
            return result
