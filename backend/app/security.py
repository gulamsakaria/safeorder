"""Request limits and basic response headers for the whole API (BLUEPRINT.md Step 15).

A small ASGI middleware, deliberately simple:

* **Body size:** a request whose body is larger than ``api.max_body_bytes`` is refused with 413,
  whether it announces its size or streams it.
* **Rate limit:** at most ``api.rate_limit_per_minute`` requests per client address in any sliding
  60 seconds, then 429 with ``Retry-After``. ``/health`` is exempt; 0 switches the limit off.
  It is in-memory and per process, enough for a sandbox demo and not a defence against a
  distributed attack.
* **Headers:** ``X-Content-Type-Options: nosniff``, ``X-Frame-Options: DENY`` and
  ``Cache-Control: no-store`` on every response.
"""

import json
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

WINDOW_SECONDS = 60.0
EXEMPT_PATHS = ("/health",)
SECURITY_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"cache-control", b"no-store"),
)


class BodyTooLarge(Exception):
    pass


def _error(status: int, code: str, message: str, extra: list[tuple[bytes, bytes]] | None = None):
    payload = json.dumps({"error": {"code": code, "message": message}}).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(payload)).encode()),
    ]
    return status, headers + (extra or []) + list(SECURITY_HEADERS), payload


class SecurityMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        max_body_bytes: int,
        rate_limit_per_minute: int,
        trust_proxy: bool = False,
        clock: Callable[[], float] = time.monotonic,
        upload_max_body_bytes: int | None = None,
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.upload_max_body_bytes = upload_max_body_bytes or max_body_bytes
        self.limit = rate_limit_per_minute
        self.trust_proxy = trust_proxy
        self.clock = clock
        self.hits: dict[str, deque[float]] = {}

    def _allowed(self, client: str) -> float | None:
        """None when allowed, otherwise the seconds to wait."""
        now = self.clock()
        window = self.hits.setdefault(client, deque())
        while window and now - window[0] >= WINDOW_SECONDS:
            window.popleft()
        if len(window) >= self.limit:
            return WINDOW_SECONDS - (now - window[0])
        window.append(now)
        if len(self.hits) > 10_000:  # forget idle clients so the table cannot grow without bound
            for key in [k for k, w in self.hits.items() if not w or now - w[-1] >= WINDOW_SECONDS]:
                del self.hits[key]
        return None

    def _client(self, scope: Scope) -> str:
        """The caller's address; behind a trusted proxy, the first X-Forwarded-For entry."""
        if self.trust_proxy:
            forwarded = dict(scope["headers"]).get(b"x-forwarded-for", b"").decode("latin-1")
            first = forwarded.split(",")[0].strip()
            if first:
                return first
        return (scope.get("client") or ("unknown", 0))[0]

    async def _respond(self, send: Send, status: int, headers: list, body: bytes) -> None:
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self.limit > 0 and scope["path"] not in EXEMPT_PATHS:
            client = self._client(scope)
            wait = self._allowed(client)
            if wait is not None:
                retry = [(b"retry-after", str(int(wait) + 1).encode())]
                await self._respond(send, *_error(429, "RATE_LIMITED", "too many requests", retry))
                return

        # only the proof upload (a small photo) may be larger than a normal request
        max_body = (
            self.upload_max_body_bytes if scope["path"].endswith("/proof") else self.max_body_bytes
        )
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > max_body:
            await self._respond(
                send, *_error(413, "PAYLOAD_TOO_LARGE", "request body is too large")
            )
            return

        received = 0
        too_large = False
        replaced = False

        async def limited_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > max_body:
                    too_large = True
                    raise BodyTooLarge
            return message

        async def secured_send(message: Message) -> None:
            nonlocal replaced
            if too_large:
                # The framework turns the aborted read into its own 400: answer 413 instead.
                if not replaced:
                    replaced = True
                    await self._respond(
                        send, *_error(413, "PAYLOAD_TOO_LARGE", "request body is too large")
                    )
                return
            if message["type"] == "http.response.start":
                present = {name for name, _ in message["headers"]}
                message["headers"] = list(message["headers"]) + [
                    h for h in SECURITY_HEADERS if h[0] not in present
                ]
            await send(message)

        try:
            await self.app(scope, limited_receive, secured_send)
        except BodyTooLarge:
            if not replaced:
                await self._respond(
                    send, *_error(413, "PAYLOAD_TOO_LARGE", "request body is too large")
                )


def install(app: Any, api_cfg: dict[str, Any], upload_max_body_bytes: int | None = None) -> None:
    app.add_middleware(
        SecurityMiddleware,
        max_body_bytes=api_cfg["max_body_bytes"],
        rate_limit_per_minute=api_cfg["rate_limit_per_minute"],
        trust_proxy=api_cfg.get("trust_proxy_headers", False),
        upload_max_body_bytes=upload_max_body_bytes,
    )
