"""Owner-approved OAuth authorization server and read-only MCP resource bridge.

Exposes loopback HTTP only; TLS termination and fixed Host at Nginx.
A valid OAuth token never becomes a privileged command token: the bridge
uses a separately scoped gateway client whose policy permits two tools.
"""
from __future__ import annotations

import argparse
import base64
from http import HTTPStatus
import html
import http.client
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sqlite3
import socket
import threading
from urllib.parse import parse_qsl, urlencode, urlsplit

from panel.auth import PanelAuth
from server.gateway import GatewayRegistry
from server.gateway_policy import RateLimiter
from server.oauth_store import (
    ACCESS_TTL, ISSUER, RESOURCE, SCOPE, OAuthError, OAuthStore, digest,
)

MAX_JSON = 8192
MAX_MCP = 131072
MAX_RESPONSE = 16 * 1024 * 1024
METADATA = {
    "issuer": ISSUER,
    # RFC 9207: every issued authorization redirect carries the matching iss.
    # Enables the stable ChatGPT connector callback for new connections.
    "authorization_response_iss_parameter_supported": True,
    "authorization_endpoint": ISSUER + "/oauth/authorize",
    "token_endpoint": ISSUER + "/oauth/token",
    "registration_endpoint": ISSUER + "/oauth/register",
    "revocation_endpoint": ISSUER + "/oauth/revoke",
    "response_types_supported": ["code"],
    "grant_types_supported": ["authorization_code", "refresh_token"],
    "token_endpoint_auth_methods_supported": ["none"],
    "code_challenge_methods_supported": ["S256"],
    "scopes_supported": [SCOPE],
    "service_documentation": ISSUER + "/portalmcp/",
}
RESOURCE_METADATA = {
    "resource": RESOURCE,
    "authorization_servers": [ISSUER],
    "scopes_supported": [SCOPE],
    "bearer_methods_supported": ["header"],
}

COOKIE_PREFIX = "__Host-lunexpc_oauth_"


def _cookie_name(request_id):
    # Distinct cookies keep parallel ChatGPT authorization tabs independent.
    # Do not leak random request IDs in cookie names.
    return COOKIE_PREFIX + digest(request_id)[:20]


AUTH_CHALLENGE = (f'Bearer resource_metadata="{ISSUER}'
                  f'/.well-known/oauth-protected-resource/lunexpc-mcp", '
                  f'scope="{SCOPE}"')


def _unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise OAuthError()
        result[key] = value
    return result


def _parse_urlencoded(data):
    try:
        parts = parse_qsl(data.decode("utf-8"), keep_blank_values=False,
                          strict_parsing=True, max_num_fields=20)
    except (UnicodeDecodeError, ValueError) as exc:
        raise OAuthError() from exc
    return _unique_pairs(parts)


def _decode_json(body):
    try:
        value = json.loads(body, object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise OAuthError() from exc
    if not isinstance(value, dict):
        raise OAuthError()
    return value


def _read_secret(file: Path):
    # PanelAuth already checks private file ownership/mode and max size.
    secret = PanelAuth(file)
    if not secret.configured or not secret.secret:
        raise ValueError("owner login unavailable")
    return secret.secret


def make_handler(store, owner_file, private_gateway_key, gateway_registry,
                 connection_factory=http.client.HTTPConnection):
    registration_limit = RateLimiter(limit=20, window=60, max_identities=2)
    login_limit = RateLimiter(limit=15, window=60, max_identities=2)
    request_limit = RateLimiter(limit=120, window=60, max_identities=2)

    class OAuthHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            # Never log authentication values, query strings, callbacks or JSON.
            pass

        def _send(self, status, payload=b"", content_type="application/json",
                  headers=None):
            if isinstance(payload, str):
                payload = payload.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if headers:
                for k, v in headers.items():
                    self.send_header(k, v)
            if status >= 400:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        def _json(self, status, value, headers=None):
            self._send(status, json.dumps(value, separators=(",", ":"),
                                          ensure_ascii=False), headers=headers)

        def _failure(self, exc):
            if urlsplit(self.path).path == "/oauth/approve":
                # Internal logs contain only fixed reason categories, never
                # passwords, client IDs, IPs, cookies, callback URLs or tokens.
                category = exc.reason if exc.reason in {
                    "invalid_form", "invalid_cookie", "unknown_request",
                    "expired_request", "attempt_limit", "csrf_mismatch",
                    "missing_cookie", "cookie_mismatch", "password_mismatch",
                    "origin_rejected", "fetch_site_rejected",
                    "unspecified",
                } else "unspecified"
                logging.warning("oauth_approval_rejected reason=%s status=%d",
                                category, exc.status)
                # A browser form expects HTML, not an OAuth JSON error object.
                # Explain how to start a fresh login; never echo user input.
                heading = "Не удалось подтвердить вход"
                hint = ("Вернись в ChatGPT, заново запусти подключение "
                        "LunexPCControl и открой новую страницу входа.")
                if category == "password_mismatch":
                    hint = ("Пароль не прошёл проверку. Убедись, что используешь "
                            "пароль портала LunexPCControl, затем начни "
                            "подключение заново.")
                elif category in ("missing_cookie", "cookie_mismatch",
                                  "csrf_mismatch", "expired_request",
                                  "unknown_request"):
                    hint = ("Сессия авторизации недоступна или устарела. "
                            "Вернись в ChatGPT и заново начни подключение.")
                page = f"""<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LunexPCControl — вход не подтверждён</title>
<style>
body{{margin:0;background:#101b2b;color:#e6f2ff;font:16px system-ui;padding:1.3rem}}
main{{max-width:520px;margin:3rem auto;padding:1.5rem;background:#182940;border-radius:16px}}
p{{line-height:1.5}}a{{display:inline-block;padding:14px 18px;background:#197d61;
color:white;text-decoration:none;border-radius:10px;margin-top:1rem}}
small{{color:#a7bfd2}}
</style></head><body><main><h1>{heading}</h1><p>{hint}</p>
<a href="https://chatgpt.com/plugins">Вернуться в ChatGPT</a>
<p><small>Не отправляй пароль в чат. Защита доступа осталась включённой.</small></p>
</main></body></html>"""
                self._send(exc.status, page, "text/html; charset=utf-8",
                           headers={
                               "Content-Security-Policy":
                                   "default-src 'none'; style-src 'unsafe-inline'; "
                                   "base-uri 'none'; frame-ancestors 'none'",
                               "X-Frame-Options": "DENY",
                           })
                return
            self._json(exc.status, {"error": exc.code})

        def _body(self, max_bytes, expected_type):
            if (self.headers.get("Transfer-Encoding") is not None
                    or len(self.headers.get_all("Content-Length", [])) != 1):
                raise OAuthError()
            length = self.headers["Content-Length"]
            if not length.isdecimal() or int(length) > max_bytes or int(length) == 0:
                raise OAuthError()
            media = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if media != expected_type:
                raise OAuthError()
            data = self.rfile.read(int(length))
            if len(data) != int(length):
                raise OAuthError()
            return data

        def _host(self):
            if (len(self.headers.get_all("Host", [])) != 1
                    or self.headers["Host"] != "rikagro.ru"):
                raise OAuthError()

        def do_GET(self):
            try:
                self._host()
                path = urlsplit(self.path)
                if path.fragment:
                    raise OAuthError()
                if path.path in (
                    "/.well-known/oauth-protected-resource",
                    "/.well-known/oauth-protected-resource/lunexpc-mcp",
                ) and not path.query:
                    self._json(200, RESOURCE_METADATA)
                elif path.path == "/.well-known/oauth-authorization-server" and not path.query:
                    self._json(200, METADATA)
                elif path.path == "/oauth/authorize":
                    if not request_limit.allow("authorize"):
                        raise OAuthError("temporarily_unavailable", 429)
                    query = _parse_urlencoded(path.query.encode("utf-8"))
                    flow = store.authorize(query)
                    client_name = html.escape(flow["client_name"], quote=True)
                    callback = html.escape(flow["redirect_uri"], quote=True)
                    request_id = html.escape(flow["request_id"], quote=True)
                    csrf = html.escape(flow["csrf"], quote=True)
                    nonce = secrets.token_urlsafe(18)
                    page = f'''<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LunexPCControl — разрешение доступа</title>
<style>
body{{background:#101b2b;color:#e6f2ff;font:16px system-ui;margin:0;padding:1.5rem}}
main{{max-width:520px;margin:3rem auto;background:#182940;padding:1.5rem;border-radius:16px}}
label{{display:block;margin:1rem 0 .3rem}}
input{{width:100%;box-sizing:border-box;padding:13px;background:#0c1422;color:white;border:1px solid #577089;border-radius:10px}}
button{{margin-top:1rem;padding:14px 18px;background:#197d61;color:white;border:0;border-radius:10px;cursor:pointer}}
small{{color:#a7bfd2}}.warning{{background:#24344a;padding:12px;border-radius:8px}}
</style></head><body><main><h1>LunexPCControl</h1>
<p>Приложение <strong>{client_name}</strong> запрашивает доступ к экрану Windows.</p>
<p class="warning">Разрешено только чтение: Screenshot и ControlStatus.
Мышь, клавиатура, файлы и команды остаются недоступными.</p>
<p><small>Адрес возврата: {callback}</small></p>
<form id="oauth-approval-form" method="post" action="/oauth/approve" autocomplete="off">
<input type="hidden" name="request_id" value="{request_id}">
<input type="hidden" name="csrf" value="{csrf}">
<label for="password">Пароль владельца портала LunexPCControl</label>
<input id="password" type="password" name="password" maxlength="128"
required autocomplete="current-password">
<button id="oauth-approval-button" type="submit">Разрешить просмотр</button></form>
<script nonce="{nonce}">
document.getElementById("oauth-approval-form").addEventListener("submit", function() {{
 const button = document.getElementById("oauth-approval-button");
 button.disabled = true;
 button.textContent = "Подтверждение...";
}});
</script>
<p><small>Вводите пароль только на https://rikagro.ru.
Не передавайте пароль или токены в чат.</small></p></main></body></html>'''
                    self._send(200, page, "text/html; charset=utf-8", headers={
                        "Set-Cookie": f"{_cookie_name(flow['request_id'])}={flow['cookie']}; Path=/; Max-Age=300; Secure; HttpOnly; SameSite=Lax",
                        "Content-Security-Policy": f"default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-{nonce}'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
                        "X-Frame-Options": "DENY",
                    })
                else:
                    self._send(404, b"", "text/plain")
            except OAuthError as exc:
                self._failure(exc)
            except (OSError, ValueError):
                self._failure(OAuthError("temporarily_unavailable", 503))

        def do_HEAD(self):
            self._send(405, b"", "text/plain")

        def do_POST(self):
            try:
                self._host()
                path = urlsplit(self.path)
                if path.query or path.fragment:
                    raise OAuthError()
                if path.path == "/oauth/register":
                    if not registration_limit.allow("register"):
                        raise OAuthError("temporarily_unavailable", 429)
                    body = _decode_json(self._body(MAX_JSON, "application/json"))
                    self._json(201, store.register(body), headers={
                        "Location": ISSUER + "/oauth/register",
                    })
                elif path.path == "/oauth/token":
                    body = _parse_urlencoded(
                        self._body(MAX_JSON, "application/x-www-form-urlencoded"))
                    self._json(200, store.token(body))
                elif path.path == "/oauth/revoke":
                    body = _parse_urlencoded(
                        self._body(MAX_JSON, "application/x-www-form-urlencoded"))
                    store.revoke(body)
                    self._send(200, b"", "text/plain")
                elif path.path == "/oauth/approve":
                    if not login_limit.allow("approve"):
                        raise OAuthError("temporarily_unavailable", 429)
                    origin = self.headers.get("Origin")
                    # Android browsers may send Origin: null on a top-level
                    # form submission returning from an external application.
                    # Never trust it as same-origin. Accept only if the exact
                    # server-issued session cookie and CSRF both validate.
                    opaque_origin = origin == "null"
                    if (origin is not None and origin != ISSUER
                            and not opaque_origin):
                        raise OAuthError("access_denied", 403,
                                         reason="origin_rejected")
                    fetch_site = self.headers.get("Sec-Fetch-Site")
                    if (fetch_site is not None
                            and fetch_site not in ("same-origin", "none")
                            and not (fetch_site == "same-site" and origin == ISSUER)
                            and not (opaque_origin and fetch_site == "cross-site")):
                        raise OAuthError("access_denied", 403,
                                         reason="fetch_site_rejected")
                    fields = _parse_urlencoded(
                        self._body(MAX_JSON, "application/x-www-form-urlencoded"))
                    if set(fields) != {"request_id", "csrf", "password"}:
                        raise OAuthError()
                    cookie = self._get_cookie(fields["request_id"])
                    # Some Android Chrome flows lose a transient cookie while
                    # switching from ChatGPT to the browser. A *missing* cookie
                    # may be tolerated only if the browser also proves its
                    # exact same origin, and the hidden high-entropy CSRF token
                    # matches the server-side pending authorization request.
                    # An incorrect but PRESENT cookie is always rejected.
                    fallback = (not cookie and origin == ISSUER
                                and fetch_site in ("same-origin", "same-site"))
                    if store.previously_approved(fields["request_id"],fields["csrf"],cookie):
                        self._send(200, """<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LunexPCControl — подтверждено</title></head><body>
<h1>Вход уже подтверждён</h1>
<p>Разрешение уже отправлено в ChatGPT. Вернись в приложение.
Если подключение не завершилось, начни новый вход.</p>
<p><a href="https://chatgpt.com/">Открыть ChatGPT</a></p>
</body></html>""","text/html; charset=utf-8",headers={
                            "Content-Security-Policy":
                                "default-src 'none'; base-uri 'none'; frame-ancestors 'none'",
                            "X-Frame-Options":"DENY"})
                        return
                    if opaque_origin and not cookie:
                        raise OAuthError("access_denied", 403,
                                         reason="missing_cookie")
                    result = store.approve(fields["request_id"], fields["csrf"],
                                           cookie, fields["password"],
                                           _read_secret(owner_file),
                                           trusted_cookie_fallback=fallback)
                    if fallback:
                        logging.info("oauth_approval_browser_cookie_fallback")
                    redirect = result["redirect_uri"] + "?" + urlencode({
                        "code": result["code"],
                        "state": result["state"],
                        "iss": ISSUER,
                    })
                    # A blank cross-site 303 does not reliably complete in
                    # some embedded and external browsers. Show an explicit,
                    # user-activated callback link instead. The single-use
                    # code is not logged, cached, or reissued on a second POST.
                    safe_callback = html.escape(redirect, quote=True)
                    page = f"""<!doctype html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>LunexPCControl — подтверждение выполнено</title>
<style>
body{{margin:0;background:#101b2b;color:#e6f2ff;font:16px system-ui;padding:1.3rem}}
main{{max-width:520px;margin:3rem auto;padding:1.5rem;background:#182940;border-radius:16px}}
p{{line-height:1.5}}
a{{display:inline-block;padding:14px 18px;background:#197d61;color:white;
text-decoration:none;border-radius:10px;margin:1rem 0}}
small{{color:#a7bfd2}}
</style></head><body><main>
<h1>Доступ подтверждён</h1>
<p>Теперь нажми кнопку ниже, чтобы завершить подключение в ChatGPT.</p>
<a id="continue" href="{safe_callback}">Перейти в ChatGPT</a>
<p><small>Ссылка одноразовая и действует примерно две минуты.
Если она устареет, запусти новое подключение в ChatGPT.</small></p>
</main></body></html>"""
                    self._send(200, page, "text/html; charset=utf-8", headers={
                        "Content-Security-Policy":
                            "default-src 'none'; style-src 'unsafe-inline'; "
                            "base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
                        "X-Frame-Options": "DENY",
                    })
                elif path.path == "/lunexpc-mcp":
                    self._mcp()
                else:
                    self._send(404, b"", "text/plain")
            except OAuthError as exc:
                self._failure(exc)
            except (OSError, sqlite3.Error, ValueError, http.client.HTTPException, TimeoutError):
                self._failure(OAuthError("temporarily_unavailable", 503))

        def _get_cookie(self, request_id):
            raw = self.headers.get_all("Cookie", [])
            if len(raw) != 1 or len(raw[0]) > 2048:
                return ""
            try:
                cookie = SimpleCookie()
                cookie.load(raw[0])
                name = _cookie_name(request_id)
                return cookie[name].value if name in cookie else ""
            except (ValueError, KeyError, TypeError):
                return ""

        def _mcp(self):
            if not request_limit.allow("mcp"):
                raise OAuthError("temporarily_unavailable", 429)
            headers = self.headers.get_all("Authorization", [])
            if len(headers) != 1 or not headers[0].startswith("Bearer "):
                self._unauthorized()
                return
            value = headers[0][7:]
            if not value or len(value) > 256 or "," in value:
                self._unauthorized()
                return
            # Preserve existing Alpha 0.1 owner-specific API-key plugin auth.
            is_legacy = gateway_registry.authenticate("lunex", value) is not None
            if is_legacy:
                internal_key = value
            elif store.validate(value):
                internal_key = private_gateway_key
            else:
                self._unauthorized()
                return
            body = self._body(MAX_MCP, "application/json")
            if len(self.headers.get_all("Transfer-Encoding", [])) != 0:
                raise OAuthError()
            upstream = None
            sent = False
            try:
                upstream = connection_factory("127.0.0.1", 18880, timeout=24)
                headers = {
                    "Authorization": "Bearer " + internal_key,
                    "Content-Type": "application/json",
                    "Accept": self.headers.get("Accept", "application/json, text/event-stream"),
                }
                for field in ("Mcp-Protocol-Version", "Mcp-Method", "Mcp-Name",
                              "Mcp-Session-Id", "Last-Event-ID"):
                    value = self.headers.get(field)
                    if field == "Mcp-Session-Id" and value:
                        # Keep the request and response session-id grammar
                        # identical to prevent dropping a legitimate ID.
                        if not re.fullmatch(r"[A-Za-z0-9._~-]{1,256}", value):
                            raise OAuthError("invalid_request", 400)
                    if value and len(value) <= 256 and "\r" not in value and "\n" not in value:
                        headers[field] = value
                upstream.request("POST", "/devices/lunex/mcp", body=body, headers=headers)
                reply = upstream.getresponse()
                content_type = reply.getheader("Content-Type", "application/json")
                # MCP sessions are created by the Windows agent during
                # initialize, then sent by the client on subsequent calls.
                # Forward only an explicitly validated, bounded session ID.
                # Without it ChatGPT's initialize succeeds but tools/call and
                # notifications/initialized fail with HTTP 400 upstream.
                session_id = reply.getheader("Mcp-Session-Id")
                session_headers = {}
                if (isinstance(session_id, str) and
                        re.fullmatch(r"[A-Za-z0-9._~-]{1,256}", session_id)):
                    session_headers["Mcp-Session-Id"] = session_id
                if (reply.status not in (200, 202, 204)
                        or "text/event-stream" not in content_type.lower()):
                    data = reply.read(MAX_RESPONSE + 1)
                    if len(data) > MAX_RESPONSE:
                        raise OAuthError("upstream_error", 502)
                    self._send(reply.status, data, content_type,
                               headers=session_headers)
                    sent = True
                    return
                self.send_response(reply.status)
                self.send_header("Content-Type", "text/event-stream")
                for field, val in session_headers.items():
                    self.send_header(field, val)
                self.send_header("Cache-Control", "no-cache, no-transform")
                self.send_header("X-Accel-Buffering", "no")
                self.send_header("Connection", "close")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                sent = True
                self.close_connection = True
                transferred = 0
                while True:
                    try:
                        chunk = reply.read1(32768)
                    except socket.timeout:
                        break
                    if not chunk:
                        break
                    transferred += len(chunk)
                    if transferred > MAX_RESPONSE:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (OSError, TimeoutError, http.client.HTTPException):
                if not sent:
                    self._failure(OAuthError("upstream_unavailable", 502))
                self.close_connection = True
            finally:
                if upstream is not None:
                    upstream.close()

        def _unauthorized(self):
            self._json(401, {"error": "unauthorized"}, headers={
                "WWW-Authenticate": AUTH_CHALLENGE,
            })

    return OAuthHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18882)
    parser.add_argument("--state", type=Path, default=Path("/var/lib/lunexpc-gateway/oauth/issuer.sqlite"))
    parser.add_argument("--owner-key", type=Path, default=Path("/var/lib/lunexpc-gateway/panel-auth.key"))
    parser.add_argument("--proxy-key", type=Path, default=Path("/var/lib/lunexpc-gateway/oauth/proxy.key"))
    parser.add_argument("--gateway-registry", type=Path,
                        default=Path("/var/lib/lunexpc-gateway/registry.sqlite"))
    args = parser.parse_args()
    if args.bind != "127.0.0.1" or not 1024 <= args.port <= 65535:
        parser.error("loopback and an unprivileged port required")
    from installer.chatgpt_key import _read_token
    private = _read_token(args.proxy_key)
    registry = GatewayRegistry(str(args.gateway_registry))
    if registry.authenticate("lunex", private) is None:
        parser.error("proxy gateway credential not authorized")
    _read_secret(args.owner_key)
    store = OAuthStore(args.state)
    server = ThreadingHTTPServer(
        (args.bind, args.port), make_handler(store, args.owner_key, private, registry))
    server.daemon_threads = True
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
