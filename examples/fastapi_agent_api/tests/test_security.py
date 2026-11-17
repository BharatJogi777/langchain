from __future__ import annotations

from pwdlib import PasswordHash
from fastapi.testclient import TestClient

from app.api import create_app
from app.security import SecurityManager, SecuritySettings, UserRecord


def make_security():
    hasher = PasswordHash.recommended()
    users = {
        "admin": UserRecord("admin", hasher.hash("admin-test-password"), "admin", frozenset({"*"})),
        "investigator": UserRecord(
            "investigator", hasher.hash("investigator-test-password"),
            "investigator", frozenset({"checkout-api", "payments-api"}),
        ),
        "viewer": UserRecord(
            "viewer", hasher.hash("viewer-test-password"),
            "viewer", frozenset({"checkout-api"}),
        ),
    }
    return SecurityManager(SecuritySettings(secret_key="test-secret-key-" * 4, users=users))


def build_secure_app(limit=20):
    async def investigator(**kwargs):
        return {
            "report": "Collected read-only evidence",
            "partial": False,
            "evidence": {"logs_agent": "No errors"},
            "unavailable": {},
            "correlation_id": "internal",
        }

    async def runtime_factory():
        async def cleanup():
            return None
        return investigator, cleanup

    from app.rate_limit import SlidingWindowRateLimiter
    return create_app(
        runtime_factory=runtime_factory,
        security=make_security(),
        rate_limiter=SlidingWindowRateLimiter(limit=limit, window_seconds=60),
        instrument_http=False,
    )


def login(client, username, password):
    return client.post(
        "/token",
        data={"username": username, "password": password},
    )


def payload(service="checkout-api"):
    return {
        "service": service,
        "incident": "Checkout requests are timing out",
        "task": "Inspect logs and metrics",
    }


def test_investigation_requires_authentication():
    with TestClient(build_secure_app()) as client:
        response = client.post("/v1/investigations", json=payload())
    assert response.status_code == 401


def test_investigator_can_run_allowed_service():
    with TestClient(build_secure_app()) as client:
        token_response = login(client, "investigator", "investigator-test-password")
        assert token_response.status_code == 200
        token = token_response.json()["access_token"]
        response = client.post(
            "/v1/investigations",
            headers={"Authorization": f"Bearer {token}"},
            json=payload("checkout-api"),
        )
    assert response.status_code == 200


def test_investigator_cannot_access_unassigned_service():
    with TestClient(build_secure_app()) as client:
        token = login(client, "investigator", "investigator-test-password").json()["access_token"]
        response = client.post(
            "/v1/investigations",
            headers={"Authorization": f"Bearer {token}"},
            json=payload("unassigned-service"),
        )
    assert response.status_code == 403


def test_viewer_cannot_start_investigation():
    with TestClient(build_secure_app()) as client:
        token = login(client, "viewer", "viewer-test-password").json()["access_token"]
        response = client.post(
            "/v1/investigations",
            headers={"Authorization": f"Bearer {token}"},
            json=payload(),
        )
    assert response.status_code == 403


def test_wrong_password_is_rejected():
    with TestClient(build_secure_app()) as client:
        response = login(client, "admin", "incorrect-password")
    assert response.status_code == 401


def test_rate_limit_returns_429():
    with TestClient(build_secure_app(limit=1)) as client:
        token = login(client, "investigator", "investigator-test-password").json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        first = client.post("/v1/investigations", headers=headers, json=payload())
        second = client.post("/v1/investigations", headers=headers, json=payload())
    assert first.status_code == 200
    assert second.status_code == 429
    assert "Retry-After" in second.headers
