from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from worker import OutboxWorker, retry_delay_seconds

class FakeRepository:
    def __init__(self, approval):
        self.approval = approval
        self.delivered, self.dead, self.retries = [], [], []
    async def get_approval(self, request_id):
        return self.approval
    async def mark_delivered(self, **kwargs):
        self.delivered.append(kwargs)
        return True
    async def mark_dead(self, **kwargs):
        self.dead.append(kwargs)
        return True
    async def schedule_retry(self, **kwargs):
        self.retries.append(kwargs)
        return True

class FakeResumer:
    def __init__(self, error=None):
        self.calls, self.error = [], error
    async def resume(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error

def make_event():
    request_id, event_id = uuid4(), uuid4()
    digest = "a" * 64
    approval = {
        "request_id": request_id, "thread_id": "thread-123",
        "status": "decision_recorded", "payload_sha256": digest,
        "decision": "approve", "decided_by": "reviewer-1",
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    event = {
        "event_id": event_id, "request_id": request_id,
        "event_type": "resume_approval_workflow",
        "payload": {"payload_sha256": digest}, "attempts": 1,
    }
    return event, approval

@pytest.mark.asyncio
async def test_valid_event_resumes_graph_and_marks_delivered():
    event, approval = make_event()
    repo, resumer = FakeRepository(approval), FakeResumer()
    worker = OutboxWorker(repo, resumer, worker_id="worker-a")
    token = uuid4()
    await worker.process_event(event, claim_token=token)
    assert len(resumer.calls) == 1
    assert resumer.calls[0]["thread_id"] == "thread-123"
    assert repo.delivered[0]["claim_token"] == token

@pytest.mark.asyncio
async def test_hash_mismatch_is_dead_lettered_without_resume():
    event, approval = make_event()
    event["payload"]["payload_sha256"] = "b" * 64
    repo, resumer = FakeRepository(approval), FakeResumer()
    worker = OutboxWorker(repo, resumer, worker_id="worker-a")
    await worker.process_event(event, claim_token=uuid4())
    assert not resumer.calls
    assert repo.dead[0]["error_code"] == "proposal_hash_mismatch"

@pytest.mark.asyncio
async def test_transient_error_is_scheduled_for_retry():
    event, approval = make_event()
    repo = FakeRepository(approval)
    resumer = FakeResumer(RuntimeError("secret text"))
    worker = OutboxWorker(repo, resumer, worker_id="worker-a")
    await worker.process_event(event, claim_token=uuid4())
    assert repo.retries[0]["error_code"] == "transient_handler_error"
    assert "secret text" not in str(repo.retries)

@pytest.mark.asyncio
async def test_expired_approval_is_not_resumed():
    event, approval = make_event()
    approval["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    repo, resumer = FakeRepository(approval), FakeResumer()
    worker = OutboxWorker(repo, resumer, worker_id="worker-a")
    await worker.process_event(event, claim_token=uuid4())
    assert not resumer.calls
    assert repo.dead[0]["error_code"] == "approval_expired"

def test_retry_delay_is_bounded():
    assert retry_delay_seconds(1, rng=lambda: 0.5) == 1.0
    assert retry_delay_seconds(30, rng=lambda: 1.0) == 300.0
