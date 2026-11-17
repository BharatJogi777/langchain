CREATE TABLE approval_requests (
    request_id UUID PRIMARY KEY,
    thread_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'decision_recorded', 'executing', 'succeeded',
                   'rejected', 'expired', 'failed', 'unknown')
    ),
    payload_sha256 CHAR(64) NOT NULL,
    decision TEXT,
    decided_by TEXT,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE approval_outbox (
    event_id UUID PRIMARY KEY,
    request_id UUID NOT NULL REFERENCES approval_requests(request_id),
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'delivered', 'dead')),
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_by TEXT,
    locked_until TIMESTAMPTZ,
    claim_token UUID,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at TIMESTAMPTZ,
    UNIQUE (request_id, event_type)
);

CREATE INDEX approval_outbox_claim_idx
ON approval_outbox (available_at, created_at)
WHERE status IN ('pending', 'processing');

-- In the approval transaction, update the request, insert an outbox event,
-- and append the audit event together. Check that the UPDATE changed one row.
-- The outbox payload is a wake-up hint; reload approval_requests before resume.
