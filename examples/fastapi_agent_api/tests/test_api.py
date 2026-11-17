from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import create_app


def build_app(fake_result=None):
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
        instrument_http=False,
    )


def test_liveness_and_readiness():
    with TestClient(build_app()) as client:
        assert client.get("/health/live").json() == {"status": "alive"}
        assert client.get("/health/ready").status_code == 200


def test_investigation_returns_correlation_id_header_and_body():
    with TestClient(build_app()) as client:
        response = client.post(
            "/v1/investigations",
            headers={"X-Correlation-ID": "test-incident-123"},
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
        response = client.post(
            "/v1/investigations",
            headers={"X-Correlation-ID": "bad\r\nheader"},
            json={
                "service": "checkout-api",
                "incident": "Checkout requests are timing out",
                "task": "Inspect logs and metrics",
            },
        )

    assert response.status_code == 200
    generated = response.headers["X-Correlation-ID"]
    assert 1 <= len(generated) <= 64
    assert generated != "bad\r\nheader"


def test_partial_investigation_is_returned_as_partial_success():
    partial_result = {
        "report": "Partial evidence",
        "partial": True,
        "evidence": {"logs_agent": "No relevant error"},
        "unavailable": {"metrics_agent": "TimeoutError"},
        "correlation_id": "unused",
    }
    with TestClient(build_app(partial_result)) as client:
        response = client.post(
            "/v1/investigations",
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
        response = client.post(
            "/v1/investigations",
            json={"service": "x", "incident": "bad"},
        )
    assert response.status_code == 422
