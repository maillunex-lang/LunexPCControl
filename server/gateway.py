"""Constrained MCP HTTP gateway (stdlib-only; place behind a trusted TLS proxy).

Only targets a per-device port on 127.0.0.1. The upstream Windows-MCP
server stays independently authenticated through the reverse SSH tunnel.
"""
from __future__ import annotations

import hashlib
import hmac
import http.client
import re
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

MAX_BODY = 4 * 1024 * 1024
MAX_RESPONSE = 16 * 1024 * 1024
MCP_METHODS = frozenset({"POST", "GET", "DELETE"})
PASSTHROUGH_HEADERS = frozenset({
    "accept", "content-type", "mcp-protocol-version", "mcp-session-id",
    "last-event-id",
})
RESPONSE_HEADERS = frozenset({
    "content-type", "mcp-protocol-version", "mcp-session-id",
    "cache-control", "retry-after",
})


class GatewayRegistry:
    """Independent client and upstream credentials; only their hashes persist for clients."""

    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    device TEXT NOT NULL,
                    token_digest TEXT PRIMARY KEY,
                    allowed INTEGER NOT NULL DEFAULT 1
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS routes (
                    device TEXT PRIMARY KEY,
                    port INTEGER NOT NULL UNIQUE,
                    upstream_key TEXT NOT NULL
                )
            """)

    def configure_route(self, device, port, upstream_key):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", device):
            raise ValueError("invalid device")
        if type(port) is not int or port < 20000 or port > 29999:
            raise ValueError("invalid port")
        if not isinstance(upstream_key, str) or len(upstream_key) < 24:
            raise ValueError("invalid upstream credential")
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO routes(device,port,upstream_key) VALUES (?,?,?) "
                "ON CONFLICT(device) DO UPDATE SET port=excluded.port, upstream_key=excluded.upstream_key",
                (device, port, upstream_key),
            )

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_client(self, device):
        token = secrets.token_urlsafe(32)
        with sqlite3.connect(self.path) as db:
            if not db.execute("SELECT 1 FROM routes WHERE device=?", (device,)).fetchone():
                raise ValueError("device not configured")
            db.execute(
                "INSERT INTO clients(device,token_digest) VALUES (?,?)",
                (device, self.digest(token)),
            )
        return token

    def revoke_client(self, token):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE clients SET allowed=0 WHERE token_digest=?", (self.digest(token),))

    def revoke_device(self, device):
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM clients WHERE device=?", (device,))
            db.execute("DELETE FROM routes WHERE device=?", (device,))

    def authenticate(self, device, token):
        if not isinstance(token, str):
            return None
        digest = self.digest(token)
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT r.port,r.upstream_key FROM clients c "
                "JOIN routes r ON r.device=c.device "
                "WHERE c.device=? AND c.token_digest=? AND c.allowed=1",
                (device, digest),
            ).fetchone()
        return row


def make_handler(registry, upstream_factory=http.client.HTTPConnection):
    class GatewayHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _respond(self, code, data=b"", media="text/plain"):
            self.send_response(code)
            self.send_header("Content-Type", media)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def do_POST(self):
            self._handle()

        def do_GET(self):
            self._handle()

        def do_DELETE(self):
            self._handle()

        def do_HEAD(self):
            self._respond(405)

        def _handle(self):
            # Only /devices/<device>/mcp and its query are permitted.
            split = urlsplit(self.path)
            match = re.fullmatch(r"/devices/([A-Za-z0-9_-]{1,64})/mcp", split.path)
            if not match or split.fragment or split.username or split.password:
                self._respond(404)
                return
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer ") or not auth[7:] or "," in auth:
                self._respond(401)
                return
            route = registry.authenticate(match.group(1), auth[7:])
            if route is None:
                self._respond(403)
                return
            if "Transfer-Encoding" in self.headers:
                self._respond(400)
                return
            raw_length = self.headers.get("Content-Length")
            if self.command == "POST":
                if raw_length is None or not raw_length.isdecimal():
                    self._respond(411)
                    return
                length = int(raw_length)
                if length > MAX_BODY:
                    self._respond(413)
                    return
                body = self.rfile.read(length)
            else:
                if raw_length not in (None, "0"):
                    self._respond(400)
                    return
                body = None
            request_headers = {
                key: value for key, value in self.headers.items()
                if key.lower() in PASSTHROUGH_HEADERS
            }
            request_headers["Authorization"] = f"Bearer {route[1]}"
            conn = None
            try:
                conn = upstream_factory("127.0.0.1", route[0], timeout=20)
                target = "/mcp" + ("?" + split.query if split.query else "")
                conn.request(self.command, target, body=body, headers=request_headers)
                response = conn.getresponse()
                if response.status in (301, 302, 303, 307, 308):
                    self._respond(502, b"upstream redirect rejected")
                    return
                size = response.getheader("Content-Length")
                if size is not None and (not size.isdecimal() or int(size) > MAX_RESPONSE):
                    self._respond(502, b"upstream response size exceeded")
                    return
                # Buffering means SSE support is bounded; see docs/GATEWAY.md.
                output = response.read(MAX_RESPONSE + 1)
                if len(output) > MAX_RESPONSE:
                    self._respond(502, b"upstream response size exceeded")
                    return
                self.send_response(response.status)
                for key, value in response.getheaders():
                    if key.lower() in RESPONSE_HEADERS and "\r" not in value and "\n" not in value:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(output)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(output)
            except (OSError, http.client.HTTPException, TimeoutError):
                self._respond(502, b"Windows agent unavailable")
            finally:
                if conn is not None:
                    conn.close()

        def log_message(self, fmt, *args):
            # Never print URLs/query parameters or auth material in production logs.
            pass

    return GatewayHandler


def serve(registry_path, bind="127.0.0.1", port=18880):
    if bind not in ("127.0.0.1", "::1"):
        raise ValueError("gateway must remain loopback-only behind TLS proxy")
    registry = GatewayRegistry(registry_path)
    httpd = ThreadingHTTPServer((bind, port), make_handler(registry))
    httpd.serve_forever()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--port", type=int, default=18880)
    args = parser.parse_args()
    serve(args.registry, port=args.port)
