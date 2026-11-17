"""Validated action proposals and trusted approval decisions."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ActionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    requested_by: str = Field(min_length=2, max_length=120)
    action: Literal["restart_service", "rollback_deployment"]
    service: str = Field(min_length=2, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    environment: Literal["staging", "production"]
    reason: str = Field(min_length=10, max_length=1000)
    change_reference: str = Field(min_length=3, max_length=80)


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    approver_id: str = Field(min_length=2, max_length=120)
    approver_role: Literal["platform_admin", "incident_commander", "operator"]
    comment: str = Field(default="", max_length=500)


APPROVAL_ROLES = {"platform_admin", "incident_commander"}


def validate_approval(proposal: ActionProposal, decision: ApprovalDecision) -> None:
    """Apply deterministic approval policy; never ask the LLM to authorize."""
    if decision.approver_role not in APPROVAL_ROLES:
        raise PermissionError("Approver role is not permitted to approve operations")
    if decision.approver_id == proposal.requested_by:
        raise PermissionError("Requester cannot approve their own operation")
    if proposal.environment == "production" and decision.approver_role != "incident_commander":
        raise PermissionError("Production operations require an incident commander")
    if decision.decision == "approve" and len(decision.comment.strip()) < 5:
        raise ValueError("An approval comment of at least 5 characters is required")
