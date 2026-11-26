"""Constrained MCP HTTP gateway (stdlib-only; place behind a trusted TLS proxy).

Only targets a per-device port on 127.0.0.1. The upstream Windows-MCP
server stays independently authenticated through the reverse SSH tunnel.
"""
from __future__ import annotations

import hashlib
import http.client
import re
import secrets
import sqlite3
import os
import stat
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
        if path != ":memory:":
            if os.path.islink(path):
                raise ValueError("registry symlinks are forbidden")
            if os.path.exists(path) and not stat.S_ISREG(os.stat(path).st_mode):
                raise ValueError("registry must be a regular file")
            # Temporarily tighten process permissions for a newly created SQLite file.
            old_umask = os.umask(0o077)
        else:
            old_umask = None
        try:
            self._initialize()
        finally:
            if old_umask is not None:
                os.umask(old_umask)
        if path != ":memory:":
            mode = stat.S_IMODE(os.stat(path).st_mode)
            if mode & 0o077:
                raise PermissionError("registry must be private (0600)")

    def _initialize(self):
        with sqlite3.connect(self.path) as db:
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
        if not isinstance(token, str) or len(token) > 256:
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
            if len(self.headers.get_all("Authorization", [])) != 1:
                self._respond(401)
                return
            if len(self.headers.get_all("Content-Length", [])) > 1 or len(self.headers.get_all("Transfer-Encoding", [])) > 1:
                self._respond(400)
                self.close_connection = True
                return
            if self.headers.get("Connection", "").lower() == "upgrade" or self.headers.get("Upgrade"):
                self._respond(400)
                self.close_connection = True
                return
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer ") or not auth[7:] or "," in auth:
                self._respond(401)
                return
            route = registry.authenticate(match.group(1), auth[7:])
            if route is None:
                self._respond(403)
                return
            # Defend against ambiguous request framing before proxying.
            if any(k.lower() == "transfer-encoding" for k in self.headers.keys()):
                self._respond(400)
                self.close_connection = True
                return
            raw_length = self.headers.get("Content-Length")
            if self.command == "POST":
                if raw_length is None or not raw_length.isdecimal():
                    self._respond(411)
                    return
                length = int(raw_length)
                if length > MAX_BODY:
                    self._respond(413)
                    self.close_connection = True
                    return
                body = self.rfile.read(length)
                if len(body) != length:
                    self.close_connection = True
                    return
            else:
                if raw_length not in (None, "0"):
                    self._respond(400)
                    return
                body = None
            if len(split.query) > 2048 or any(c in split.query for c in "\r\n"):
                self._respond(400)
                return
            request_headers = {
                key: value for key, value in self.headers.items()
                if key.lower() in PASSTHROUGH_HEADERS
            }
            request_headers["Authorization"] = f"Bearer {route[1]}"
            conn = None
            headers_sent = False
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
                media = response.getheader("Content-Type", "")
                is_stream = "text/event-stream" in media.lower()
                if is_stream and response.status == 200:
                    # Send headers immediately; never buffer an unbounded SSE stream.
                    self.send_response(response.status)
                    for key, value in response.getheaders():
                        if key.lower() in RESPONSE_HEADERS and "\r" not in value and "\n" not in value:
                            self.send_header(key, value)
                    self.send_header("Cache-Control", "no-cache, no-transform")
                    self.send_header("X-Accel-Buffering", "no")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    headers_sent = True
                    self.close_connection = True
                    # Upstream emits heartbeat/events; a read timeout ends a stale stream.
                    # Stream is intentionally unbounded in duration and closes with its client.
                    while True:
                        chunk = response.read1(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                else:
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
            except (BrokenPipeError, ConnectionResetError):
                # Client disconnected during SSE; shut down only its upstream socket.
                self.close_connection = True
            except (OSError, http.client.HTTPException, TimeoutError):
                if not headers_sent and not self.wfile.closed:
                    # Error before response headers: produce a valid gateway error.
                    try:
                        self._respond(502, b"Windows agent unavailable")
                    except OSError:
                        pass
                self.close_connection = True
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
