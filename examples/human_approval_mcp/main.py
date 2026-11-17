"""CLI demonstration of propose -> pause -> approve/reject -> execute."""
from __future__ import annotations

import asyncio
import json
import uuid

from app.mcp_executor import build_mcp_executor
from app.models import ActionProposal, ApprovalDecision
from app.workflow import build_approval_workflow, resume_approval, start_approval


async def main():
    execute_action = await build_mcp_executor()
    graph = build_approval_workflow(execute_action)

    proposal = ActionProposal(
        request_id=f"incident-{uuid.uuid4().hex[:12]}",
        requested_by="operator-alex",
        action="restart_service",
        service="checkout-api",
        environment="staging",
        reason="The service health check has failed repeatedly.",
        change_reference="CHG-2026-1042",
    )

    result = start_approval(graph, proposal)
    interrupts = result.get("__interrupt__", [])
    if not interrupts:
        print(json.dumps(result, indent=2, default=str))
        return

    print("\nApproval required:")
    print(json.dumps(interrupts[0].value, indent=2))
    decision = input("\nType approve or reject: ").strip().lower()
    if decision not in {"approve", "reject"}:
        print("Invalid decision. No action executed.")
        return

    # In a real API, approver identity and role must come from the verified
    # JWT/session principal, never from a client-supplied approver_id field.
    approver_id = input("Approver identity (demo): ").strip()
    approver_role = input("Approver role (platform_admin/incident_commander): ").strip()
    comment = input("Approval/rejection comment: ").strip()

    approval = ApprovalDecision(
        decision=decision,
        approver_id=approver_id,
        approver_role=approver_role,
        comment=comment,
    )
    final = resume_approval(
        graph,
        request_id=proposal.request_id,
        decision=approval,
    )
    print("\nWorkflow result:")
    print(json.dumps(final, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
