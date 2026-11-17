"""Independent specialist execution with correlated logs and telemetry."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.observability import Observability, get_correlation_id
from app.resilience import ResilientExecutor

Specialist = Callable[[str, str, str], Awaitable[str]]
logger = logging.getLogger("devops_agent")


async def investigate(
    *,
    incident: str,
    service: str,
    task: str,
    specialists: dict[str, Specialist],
    executors: dict[str, ResilientExecutor],
    telemetry: Observability,
) -> dict:
    if set(specialists) != set(executors):
        raise ValueError("Every specialist must have exactly one resilience executor")

    correlation_id = get_correlation_id()
    logger.info("investigation started", extra={"outcome": "started"})

    async def run_one(name: str, specialist: Specialist) -> tuple[str, str, str | None]:
        try:
            async with telemetry.specialist_span(name):
                evidence = await executors[name].run(
                    lambda: specialist(incident, service, task)
                )
            logger.info(
                "specialist completed",
                extra={"specialist": name, "outcome": "success"},
            )
            return name, str(evidence)[:4000], None
        except Exception as exc:
            logger.warning(
                "specialist unavailable",
                extra={
                    "specialist": name,
                    "outcome": "error",
                    "error_type": type(exc).__name__,
                },
            )
            return name, "", type(exc).__name__

    async with telemetry.investigation_span(service):
        outcomes = await asyncio.gather(
            *(run_one(name, specialist) for name, specialist in specialists.items())
        )

    evidence = {name: result for name, result, error in outcomes if error is None}
    unavailable = {name: error for name, result, error in outcomes if error is not None}
    lines = [
        "DevOps investigation report",
        f"Service: {service}",
        f"Incident: {incident}",
        f"Correlation ID: {correlation_id or 'not-set'}",
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

    partial = bool(unavailable)
    logger.info(
        "investigation completed",
        extra={"outcome": "partial" if partial else "success"},
    )
    return {
        "report": "\n".join(lines),
        "evidence": evidence,
        "unavailable": unavailable,
        "partial": partial,
        "correlation_id": correlation_id,
    }
