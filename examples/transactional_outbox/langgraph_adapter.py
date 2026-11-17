"""Adapter boundary for resuming the Lesson 36 compiled graph."""
from langgraph.types import Command

class LangGraphApprovalResumer:
    def __init__(self, graph):
        self.graph = graph

    async def resume(self, *, thread_id: str, decision: str,
                     reviewer_id: str, proposal_sha256: str) -> None:
        await self.graph.ainvoke(
            Command(resume={
                "decision": decision,
                "reviewer_id": reviewer_id,
                "proposal_sha256": proposal_sha256,
            }),
            config={"configurable": {"thread_id": thread_id}},
        )
