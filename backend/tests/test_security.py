"""Request limits, rate limit, headers, and malformed input (BLUEPRINT.md Step 15)."""

import copy
import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import load_config
from app.main import create_app
from app.security import SecurityMiddleware
from app.seed import seed_minimal


def make_client(engine, **api) -> TestClient:
    cfg = copy.deepcopy(load_config())
    cfg["api"].update(api)
    with Session(engine) as session:
        seed_minimal(session)
    return TestClient(create_app(engine, None, None, cfg), raise_server_exceptions=False)


def test_oversized_body_is_refused_with_413(engine) -> None:
    client = make_client(engine, max_body_bytes=500)
    body = {"order_id": "O-1", "claim_text": "x" * 2000}
    response = client.post("/api/disputes", json=body)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_a_streamed_body_over_the_limit_is_refused_too(engine) -> None:
    client = make_client(engine, max_body_bytes=500)

    def chunks():
        for _ in range(10):
            yield b"x" * 200

    response = client.post(
        "/api/disputes", content=chunks(), headers={"content-type": "application/json"}
    )
    assert response.status_code == 413


def test_normal_sized_requests_still_work(engine) -> None:
    client = make_client(engine)
    assert client.get("/api/sellers/search", params={"q": "Demo"}).status_code == 200


def test_rate_limit_answers_429_with_retry_after_and_exempts_health(engine) -> None:
    client = make_client(engine, rate_limit_per_minute=5)
    codes = [client.get("/api/sellers/search", params={"q": "Demo"}).status_code for _ in range(8)]
    assert codes == [200] * 5 + [429] * 3
    limited = client.get("/api/sellers/search", params={"q": "Demo"})
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert int(limited.headers["retry-after"]) >= 1
    assert all(client.get("/health").status_code == 200 for _ in range(20))


def test_rate_limit_window_slides() -> None:
    now = [0.0]
    seen = []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = SecurityMiddleware(
        app, max_body_bytes=1000, rate_limit_per_minute=2, clock=lambda: now[0]
    )

    async def call() -> int:
        out = []

        async def send(message):
            out.append(message)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {"type": "http", "path": "/api/x", "headers": [], "client": ("1.2.3.4", 1)}
        await middleware(scope, receive, send)
        return out[0]["status"]

    import asyncio

    seen.append(asyncio.run(call()))
    seen.append(asyncio.run(call()))
    seen.append(asyncio.run(call()))
    now[0] = 61.0
    seen.append(asyncio.run(call()))
    assert seen == [200, 200, 429, 200]


def test_rate_limit_can_be_switched_off(engine) -> None:
    client = make_client(engine, rate_limit_per_minute=0)
    assert all(
        client.get("/api/sellers/search", params={"q": "Demo"}).status_code == 200
        for _ in range(30)
    )


def test_security_headers_are_on_every_response(engine) -> None:
    client = make_client(engine)
    for response in (
        client.get("/health"),
        client.get("/api/nothing"),
        client.post("/api/orders", json={}),
    ):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["cache-control"] == "no-store"


HOSTILE = [
    None, "", " ", "x" * 5000, -1, 0, 10**30, 1.5, float("1e400") if False else 1e308, True, [],
    {}, [[]], {"a": {"b": [1, 2, {"c": None}]}}, "' OR 1=1 --", "<script>alert(1)</script>",
    "\u0000", "‮", "😀" * 50, "../../etc/passwd", "0" * 400,
]  # fmt: skip

ENDPOINTS = [
    ("post", "/api/trust/check", ["seller_id", "wallet_no"]),
    ("post", "/api/orders", ["buyer_id", "seller_id", "amount_bdt", "product_category"]),
    ("post", "/api/orders/O-0001/confirm-delivery", ["code"]),
    ("post", "/api/disputes", ["order_id", "claim_text", "claim_type", "evidence_text"]),
    ("post", "/api/disputes/D-0001/seller-response", ["response_text", "evidence_text"]),
    ("post", "/api/disputes/D-0001/buyer-evidence", ["evidence_text"]),
    ("post", "/api/sim/courier-event", ["order_id", "status"]),
    ("post", "/api/sim/advance-clock", ["hours"]),
    ("post", "/api/analyst/disputes/D-0001/decision", ["decision", "note", "analyst_id"]),
    ("post", "/api/demo/reset", ["scenario_set"]),
]


@pytest.mark.parametrize("method,path,fields", ENDPOINTS)
def test_hostile_input_never_causes_a_server_error(engine, method, path, fields) -> None:
    client = make_client(engine, rate_limit_per_minute=0)
    for field in fields:
        for value in HOSTILE:
            body = {f: "S-0001" for f in fields}
            body[field] = value
            try:
                response = client.request(method, path, json=body)
            except ValueError:
                continue  # the test client itself cannot serialise this value
            assert response.status_code < 500, (path, field, repr(value)[:40], response.text[:200])
            if response.headers.get("content-type", "").startswith("application/json"):
                json.loads(response.text)


@pytest.mark.parametrize("raw", [b"", b"{", b"[1,2", b"null", b"\xff\xfe", b'{"a":' + b"[" * 5000])
def test_malformed_json_is_a_422_not_a_crash(engine, raw) -> None:
    client = make_client(engine, rate_limit_per_minute=0)
    response = client.post("/api/orders", content=raw, headers={"content-type": "application/json"})
    assert response.status_code in (400, 413, 422), response.text[:200]
