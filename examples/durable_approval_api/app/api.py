from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from langgraph.types import Command
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.models import DemoPrincipal, DecisionRequest, ProposalRequest
from app.repository import ApprovalRepository
from app.workflow import build_graph, config


APPROVER_ROLES = {"platform_admin", "incident_commander"}


async def demo_principal(
    x_demo_user: str = Header(...),
    x_demo_role: str = Header(...),
) -> DemoPrincipal:
    """LOCAL DEMO ONLY. Replace with Lesson 34 JWT/RBAC authentication."""
    try:
        return DemoPrincipal(user_id=x_demo_user, role=x_demo_role)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid demo identity")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_url = os.environ["DATABASE_URL"]
    pool = AsyncConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=10,
        kwargs={"autocommit": True, "row_factory": dict_row},
        open=False,
    )
    await pool.open()
    await pool.wait()
    repository = ApprovalRepository(pool)
    await repository.setup()

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    # Use the same managed pool for checkpoint reads/writes.
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()

    from app.mcp_executor import build_mcp_executor
    action_executor = await build_mcp_executor()

    app.state.pool = pool
    app.state.repository = repository
    app.state.graph = build_graph(action_executor, checkpointer)
    yield
    await pool.close()


app = FastAPI(title="Durable Human Approval API", lifespan=lifespan)


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.post("/v1/approvals", status_code=202)
async def create_proposal(
    body: ProposalRequest,
    request: Request,
    principal: DemoPrincipal = Depends(demo_principal),
):
    if principal.role not in {"operator", "platform_admin", "incident_commander"}:
        raise HTTPException(status_code=403, detail="Cannot create proposals")

    request_id = uuid4()
    thread_id = str(uuid4())  # Opaque thread ID; do not expose sequential IDs.
    proposal = body.model_dump()
    await request.app.state.repository.create(
        request_id=request_id,
        thread_id=thread_id,
        requester_id=principal.user_id,
        proposal=proposal,
        expires_in_minutes=30,
    )

    # Persist graph checkpoint before returning the pending approval response.
    await request.app.state.graph.ainvoke(
        {"proposal": proposal},
        config=config(thread_id),
    )
    return {
        "request_id": str(request_id),
        "status": "pending",
        "expires_in_minutes": 30,
    }


@app.get("/v1/approvals/{request_id}")
async def get_proposal(
    request_id: UUID,
    request: Request,
    principal: DemoPrincipal = Depends(demo_principal),
):
    row = await request.app.state.repository.get(request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if principal.role == "operator" and row["requester_id"] != principal.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this approval")
    return {
        "request_id": str(row["request_id"]),
        "requester_id": row["requester_id"],
        "action": row["action"],
        "service": row["service"],
        "environment": row["environment"],
        "reason": row["reason"],
        "change_reference": row["change_reference"],
        "status": row["status"],
        "expires_at": row["expires_at"],
        "decision": row["decision"],
        "approver_id": row["approver_id"],
    }


@app.post("/v1/approvals/{request_id}/decision")
async def decide(
    request_id: UUID,
    body: DecisionRequest,
    request: Request,
    principal: DemoPrincipal = Depends(demo_principal),
):
    if principal.role not in APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="Approver role required")

    row, outcome = await request.app.state.repository.record_decision(
        request_id=request_id,
        approver_id=principal.user_id,
        approver_role=principal.role,
        decision=body.decision,
        comment=body.comment,
    )
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail="Approval not found")
    if outcome == "self_approval":
        raise HTTPException(status_code=403, detail="Requester cannot approve own proposal")
    if outcome == "expired":
        raise HTTPException(status_code=410, detail="Approval has expired")
    if outcome == "already_decided":
        raise HTTPException(status_code=409, detail="Approval already decided")
    if outcome == "production_role_required":
        raise HTTPException(status_code=403, detail="Production requires incident commander")
    if row is None:
        raise HTTPException(status_code=409, detail="Approval is not pending")

    # Environment policy was checked in the same transaction that recorded the decision.
    stored = await request.app.state.repository.get(request_id)
    decision = {
        "decision": body.decision,
        "approver_id": principal.user_id,
        "approver_role": principal.role,
        "comment": body.comment,
    }
    final = await request.app.state.graph.ainvoke(
        Command(resume=decision),
        config=config(stored["thread_id"]),
    )
    status = "completed" if body.decision == "approve" else "rejected"
    await request.app.state.repository.mark_result(
        request_id, status, principal.user_id, final
    )
    return {"request_id": str(request_id), "status": status, "result": final}


@app.get("/v1/approvals/{request_id}/audit")
async def get_audit(
    request_id: UUID,
    request: Request,
    principal: DemoPrincipal = Depends(demo_principal),
):
    row = await request.app.state.repository.get(request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if principal.role == "operator" and row["requester_id"] != principal.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this audit")
    events = await request.app.state.repository.audit(request_id)
    return {"events": events}
