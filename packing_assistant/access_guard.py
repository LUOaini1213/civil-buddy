"""Who may use the web apps: this machine, or whoever holds CIVIL_TOKEN.

Shared by gateway/app.py and demo/app.py. Loopback trust never survives a proxy:
any forwarding header, a non-loopback Host/Origin, or HTTP/1.0 (nginx's upstream
default) makes a request remote, so a proxied deployment always needs the token.
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import os
import sys
from pathlib import Path
from typing import Callable, Iterable, Optional
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit

COOKIE = "cb_token"
OPEN_LAN_ENV = "CIVIL_ALLOW_OPEN_LAN"
LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}
_FORWARDED = {b"forwarded", b"x-forwarded-for", b"x-forwarded-host", b"x-forwarded-proto",
              b"x-forwarded-port", b"x-real-ip", b"via"}
NEED_TOKEN = "需要访问口令（CIVIL_TOKEN）"
LOCAL_ONLY = "这台服务只接受本机访问。要给其他电脑用，请在服务器上设置 CIVIL_TOKEN（访问口令）后重启。"


def configured_token() -> str:
    return (os.environ.get("CIVIL_TOKEN") or "").strip()


def open_lan() -> bool:
    return (os.environ.get(OPEN_LAN_ENV) or "").strip() == "1"


def _loopback_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    return (mapped or ip).is_loopback


def _loopback_name(host: str) -> bool:
    return host in LOOPBACK_NAMES or _loopback_ip(host)


def _headers(scope) -> dict:
    return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers") or []}


def _hostname(url: str) -> Optional[str]:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return None


def is_local(scope) -> bool:
    """True only for a request that reached us straight from this machine."""
    if {k.lower() for k, _ in scope.get("headers") or []} & _FORWARDED or scope.get("http_version") == "1.0":
        return False
    h = _headers(scope)
    host = _hostname("//" + h.get("host", ""))
    client = (scope.get("client") or ("", 0))[0] or ""
    # Starlette TestClient: no socket peer is ever this string, and uvicorn only makes a
    # non-IP client from X-Forwarded-For, which was refused above.
    testing = client == "testclient"
    if not (host == "testserver" if testing else _loopback_ip(client) and _loopback_name(host or "")):
        return False
    for name in ("origin", "referer"):
        value = h.get(name)
        if value and value != "null":
            other = _hostname(value)
            if other is None or not (_loopback_name(other) or (testing and other == "testserver")):
                return False
    return h.get("sec-fetch-site") != "cross-site"


def _cookie(h: dict) -> Optional[str]:
    for part in h.get("cookie", "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE:
            return unquote(value).strip()
    return None


def presented_token(scope) -> str:
    h = _headers(scope)
    auth = h.get("authorization", "")
    if auth[:7].lower() == "bearer ":  # the scheme is case-insensitive (RFC 7235)
        return auth[7:].strip()
    return _cookie(h) or ""


def token_ok(presented: str, expected: str) -> bool:
    return bool(expected) and hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def authorised(scope) -> bool:
    expected = configured_token()
    if expected:
        # Required from everyone, loopback included: behind a proxy every request is loopback.
        return token_ok(presented_token(scope), expected)
    return open_lan() or is_local(scope)


class AccessGuard:
    """Pure ASGI (covers WebSocket too): public paths pass; everything else needs `authorised`."""

    def __init__(self, app, public: Callable[[str], bool]):
        self.app = app
        self.public = public

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        path = scope.get("path") or "/"
        pairs = parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
        if scope["type"] == "http" and any(k == "token" for k, _ in pairs):
            return await self._url_token(scope, send, path, pairs)
        if self.public(path) or authorised(scope):
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        expected = configured_token()
        extra = []
        stale = _cookie(_headers(scope))
        if expected and stale is not None and not token_ok(stale, expected):
            extra.append((b"set-cookie", f"{COOKIE}=; Max-Age=0; Path=/; SameSite=Strict".encode()))
        status, detail = (401, NEED_TOKEN) if expected else (403, LOCAL_ONLY)
        await _json(send, status, {"detail": detail}, extra)

    async def _url_token(self, scope, send, path, pairs):
        """?token= only sets the HttpOnly cookie and redirects to the same URL without it."""
        given = next(v for k, v in pairs if k == "token")
        expected = configured_token()
        if scope.get("method") not in ("GET", "HEAD") or not token_ok(given.strip(), expected):
            return await _json(send, 401, {"detail": NEED_TOKEN}, [])
        rest = urlencode([(k, v) for k, v in pairs if k != "token"])
        location = quote("/" + path.lstrip("/")) + ("?" + rest if rest else "")  # never //host
        proto = _headers(scope).get("x-forwarded-proto", "").split(",")[0].strip().lower()
        secure = "; Secure" if "https" in (scope.get("scheme"), proto) else ""
        cookie = f"{COOKIE}={quote(expected, safe='')}; Max-Age=2592000; Path=/; HttpOnly; SameSite=Strict{secure}"
        await send({"type": "http.response.start", "status": 303, "headers": [
            (b"location", location.encode("latin-1")), (b"set-cookie", cookie.encode("latin-1")),
            (b"referrer-policy", b"no-referrer"), (b"cache-control", b"no-store"), (b"content-length", b"0")]})
        await send({"type": "http.response.body", "body": b""})


async def _json(send, status, payload, extra):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    await send({"type": "http.response.start", "status": status, "headers": [
        (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), *extra]})
    await send({"type": "http.response.body", "body": body})


def open_bind_refusal(host: str) -> Optional[str]:
    """Chinese refusal text when binding `host` would open the app to the network without a token."""
    host = (host or "").strip().strip("[]")
    if _loopback_name(host.lower()) or configured_token() or open_lan():
        return None
    return (f"拒绝启动：监听 {host} 会把服务开放给其他电脑，但没有设置 CIVIL_TOKEN（访问口令）。"
            f"请设置 CIVIL_TOKEN，或改回 127.0.0.1；确实要不设口令开放局域网，设 {OPEN_LAN_ENV}=1。")


def uvicorn_cli_host(argv: Iterable[str] = (), env=None) -> Optional[str]:
    """--host of a `uvicorn ...` / `python -m uvicorn ...` command line; None when not started that way."""
    argv = list(argv or sys.argv)
    env = os.environ if env is None else env
    if not argv:
        return None
    exe = Path(argv[0])
    if not (exe.name.lower().startswith("uvicorn") or exe.parent.name.lower() == "uvicorn"):
        return None
    host = env.get("UVICORN_HOST") or "127.0.0.1"
    for i, arg in enumerate(argv):
        if arg == "--host" and i + 1 < len(argv):
            host = argv[i + 1]
        elif arg.startswith("--host="):
            host = arg.split("=", 1)[1]
    return host


def check_startup_bind() -> None:
    """Operator aid for `uvicorn --host 0.0.0.0`; the per-request guard is the actual boundary."""
    host = uvicorn_cli_host()
    reason = open_bind_refusal(host) if host is not None else None
    if reason:
        print(reason, file=sys.stderr)
        raise RuntimeError(reason)
