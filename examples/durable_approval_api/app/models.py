from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["restart_service", "rollback_deployment"]
    service: str = Field(min_length=2, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    environment: Literal["staging", "production"]
    reason: str = Field(min_length=10, max_length=1000)
    change_reference: str = Field(min_length=3, max_length=80)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    comment: str = Field(min_length=5, max_length=500)


class DemoPrincipal(BaseModel):
    """LOCAL DEMO ONLY. Replace with the authenticated principal from Lesson 34."""
    user_id: str
    role: Literal["platform_admin", "incident_commander", "operator"]
