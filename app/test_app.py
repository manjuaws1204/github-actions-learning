import re

import pytest

from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config.update(TESTING=True)
    with flask_app.test_client() as c:
        yield c


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_create_order_returns_201_or_500(client):
    # The endpoint deliberately fails ~10% of the time to simulate a
    # flaky downstream dependency - both outcomes are "correct".
    resp = client.post("/order")
    assert resp.status_code in (201, 500)


def test_metrics_endpoint_exposes_prometheus_format(client):
    # Hit /order first so the counters have at least one sample.
    client.post("/order")

    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)

    # Prometheus text format sanity checks.
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert re.search(r"http_requests_total\{.*\}\s+\d+", body)


def test_orders_created_counter_present_after_success(client):
    # Run a handful of requests so we very likely see at least one success.
    for _ in range(20):
        client.post("/order")

    resp = client.get("/metrics")
    body = resp.get_data(as_text=True)
    assert "orders_created_total" in body
