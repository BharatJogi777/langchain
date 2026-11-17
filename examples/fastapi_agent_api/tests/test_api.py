from __future__ import annotations

from pwdlib import PasswordHash
from fastapi.testclient import TestClient

from app.api import create_app
from app.rate_limit import SlidingWindowRateLimiter
from app.security import SecurityManager, SecuritySettings, UserRecord


def build_app(fake_result=None):
    hasher = PasswordHash.recommended()
    security = SecurityManager(SecuritySettings(
        secret_key="api-test-secret-" * 3,
        users={
            "investigator": UserRecord(
                "investigator", hasher.hash("investigator-test-password"),
                "investigator", frozenset({"checkout-api"}),
            )
        },
    ))

    async def investigator(**kwargs):
        return fake_result or {
            "report": "Collected logs evidence",
            "partial": False,
            "evidence": {"logs_agent": "No errors found"},
            "unavailable": {},
            "correlation_id": "internal-value",
        }

    async def runtime_factory():
        async def cleanup():
            return None
        return investigator, cleanup

    return create_app(
        runtime_factory=runtime_factory,
        security=security,
        rate_limiter=SlidingWindowRateLimiter(limit=20, window_seconds=60),
        instrument_http=False,
    )


def auth_headers(client):
    response = client.post(
        "/token",
        data={"username": "investigator", "password": "investigator-test-password"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_liveness_and_readiness():
    with TestClient(build_app()) as client:
        assert client.get("/health/live").json() == {"status": "alive"}
        assert client.get("/health/ready").status_code == 200


def test_investigation_returns_correlation_id_header_and_body():
    with TestClient(build_app()) as client:
        headers = auth_headers(client)
        headers["X-Correlation-ID"] = "test-incident-123"
        response = client.post(
            "/v1/investigations",
            headers=headers,
            json={
                "service": "checkout-api",
                "incident": "Checkout requests are timing out",
                "task": "Inspect logs and metrics",
            },
        )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "test-incident-123"
    assert response.json()["correlation_id"] == "test-incident-123"
    assert response.json()["partial"] is False


def test_invalid_correlation_id_is_replaced():
    with TestClient(build_app()) as client:
        headers = auth_headers(client)
        headers["X-Correlation-ID"] = "bad value!"
        response = client.post(
            "/v1/investigations",
            headers=headers,
            json={
                "service": "checkout-api",
                "incident": "Checkout requests are timing out",
                "task": "Inspect logs and metrics",
            },
        )

    assert response.status_code == 200
    generated = response.headers["X-Correlation-ID"]
    assert 1 <= len(generated) <= 64
    assert generated != "bad value!"


def test_partial_investigation_is_returned_as_partial_success():
    partial_result = {
        "report": "Partial evidence",
        "partial": True,
        "evidence": {"logs_agent": "No relevant error"},
        "unavailable": {"metrics_agent": "TimeoutError"},
        "correlation_id": "unused",
    }
    with TestClient(build_app(partial_result)) as client:
        headers = auth_headers(client)
        response = client.post(
            "/v1/investigations",
            headers=headers,
            json={
                "service": "checkout-api",
                "incident": "Checkout requests are timing out",
            },
        )

    assert response.status_code == 200
    assert response.json()["partial"] is True
    assert response.json()["unavailable"] == {"metrics_agent": "TimeoutError"}


def test_invalid_payload_is_rejected():
    with TestClient(build_app()) as client:
        headers = auth_headers(client)
        response = client.post(
            "/v1/investigations",
            headers=headers,
            json={"service": "x", "incident": "bad"},
        )
    assert response.status_code == 422
