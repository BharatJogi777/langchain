"""Run independent specialists and retain successful partial evidence."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.resilience import ResilientExecutor

Specialist = Callable[[str, str, str], Awaitable[str]]


async def investigate(
    *,
    incident: str,
    service: str,
    task: str = "Collect read-only evidence for this incident",
    specialists: dict[str, Specialist],
    executors: dict[str, ResilientExecutor],
) -> dict:
    """Run specialists independently; one failure must not erase other evidence."""
    if set(specialists) != set(executors):
        raise ValueError("Every specialist must have exactly one resilience executor")

    async def run_one(name: str, specialist: Specialist) -> tuple[str, str, str | None]:
        try:
            evidence = await executors[name].run(
                lambda: specialist(incident, service, task)
            )
            return name, str(evidence)[:4000], None
        except Exception as exc:
            # Keep user-facing output sanitized; log full details securely elsewhere.
            return name, "", type(exc).__name__

    outcomes = await asyncio.gather(
        *(run_one(name, specialist) for name, specialist in specialists.items())
    )

    evidence = {name: result for name, result, error in outcomes if error is None}
    unavailable = {name: error for name, result, error in outcomes if error is not None}
    lines = [
        "DevOps investigation report",
        f"Service: {service}",
        f"Incident: {incident}",
        "",
        "Collected evidence:",
    ]
    if evidence:
        lines.extend(f"- {name}: {result}" for name, result in evidence.items())
    else:
        lines.append("- No specialist returned evidence.")

    if unavailable:
        lines.extend(["", "Unavailable evidence (not interpreted as healthy):"])
        lines.extend(f"- {name}: {error}" for name, error in unavailable.items())

    return {
        "report": "\n".join(lines),
        "evidence": evidence,
        "unavailable": unavailable,
        "partial": bool(evidence and unavailable) or (not evidence),
    }
