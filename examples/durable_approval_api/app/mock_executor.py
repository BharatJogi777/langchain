"""SQLite idempotency ledger used only by the mock operations MCP server."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class MockOperationsExecutor:
    def __init__(self, database_path: str | Path = "durable_operations.sqlite3"):
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

    async def __call__(self, *, action: str, service: str, environment: str,
                       change_reference: str, idempotency_key: str) -> dict[str, Any]:
        payload = {
            "action": action,
            "service": service,
            "environment": environment,
            "change_reference": change_reference,
        }
        encoded = json.dumps(payload, sort_keys=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT action_payload, result_payload FROM operation_results WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row:
                if row[0] != encoded:
                    raise ValueError("Idempotency key reused for a different operation")
                return json.loads(row[1])
            result = {
                "executed": True,
                "mode": "simulation",
                **payload,
                "message": f"SIMULATED {action} for {service} in {environment}",
            }
            connection.execute(
                "INSERT INTO operation_results VALUES (?, ?, ?)",
                (idempotency_key, encoded, json.dumps(result, sort_keys=True)),
            )
            connection.commit()
            return result
