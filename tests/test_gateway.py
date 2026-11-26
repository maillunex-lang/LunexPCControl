import http.client
import os
import time
import tempfile
import sqlite3
from pathlib import Path
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from server.gateway import GatewayRegistry, make_handler


class FakeMCP(BaseHTTPRequestHandler):
    def do_POST(self):
        self.reply()

    def do_GET(self):
        self.reply()

    def do_DELETE(self):
        self.reply()

    def reply(self):
        self.server.last_path = self.path
        self.server.last_auth = self.headers.get("Authorization")
        self.server.last_session = self.headers.get("Mcp-Session-Id")
        if self.path.endswith("stream=1"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(b"event: ping\ndata: first\n\n")
            self.wfile.flush()
            time.sleep(.6)
            self.wfile.write(b"event: ping\ndata: second\n\n")
            self.wfile.flush()
            return
        if self.path.endswith("redirect=1"):
            self.send_response(302)
            self.send_header("Location", "https://example.org/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        data = b'{"jsonrpc":"2.0","result":{"screenshot":"iVBOR"}}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", "session-1")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


def start(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.upstream = start(FakeMCP)
        self.db = GatewayRegistry(os.path.join(self.tmp.name, "registry.sqlite"))
        # Fake upstream port is ephemeral, so inject an allowed route without opening service.
        with __import__("sqlite3").connect(self.db.path) as db:
            db.execute("INSERT INTO routes VALUES(?,?,?)", ("pc", self.upstream.server_port, "a" * 32))
        self.token = self.db.create_client("pc")
        self.gateway = start(make_handler(self.db))

    def tearDown(self):
        self.gateway.shutdown()
        self.gateway.server_close()
        self.upstream.shutdown()
        self.upstream.server_close()
        self.tmp.cleanup()

    def call(self, method, path="/devices/pc/mcp", token=None, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.gateway.server_port, timeout=3)
        hdrs = {"Authorization": "Bearer " + (self.token if token is None else token)}
        if headers:
            hdrs.update(headers)
        conn.request(method, path, body, hdrs)
        resp = conn.getresponse()
        result = (resp.status, dict(resp.getheaders()), resp.read())
        conn.close()
        return result

    def test_mcp_and_screenshot_result_passthrough(self):
        code, headers, body = self.call("POST", body=b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"Screenshot","arguments":{}}}', headers={
            "Content-Type": "application/json", "Mcp-Session-Id": "client-session",
        })
        self.assertEqual(code, 200)
        self.assertIn(b"screenshot", body)
        self.assertEqual(headers["Mcp-Session-Id"], "session-1")
        self.assertEqual(self.upstream.last_auth, "Bearer " + "a" * 32)
        self.assertEqual(self.upstream.last_session, "client-session")

    def test_sse_is_streamed_without_buffering(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.gateway.server_port, timeout=3)
        started = time.monotonic()
        conn.request("GET", "/devices/pc/mcp?stream=1", headers={
            "Authorization": "Bearer " + self.token, "Accept": "text/event-stream",
            "Last-Event-ID": "7",
        })
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "text/event-stream")
        self.assertEqual(resp.getheader("X-Accel-Buffering"), "no")
        self.assertEqual(resp.read(25), b"event: ping\ndata: first\n\n")
        self.assertLess(time.monotonic() - started, .55)
        self.assertEqual(resp.read(), b"event: ping\ndata: second\n\n")
        conn.close()

    def test_duplicate_auth_is_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.gateway.server_port, timeout=3)
        conn.putrequest("GET", "/devices/pc/mcp")
        conn.putheader("Authorization", "Bearer " + self.token)
        conn.putheader("Authorization", "Bearer " + self.token)
        conn.endheaders()
        res = conn.getresponse()
        self.assertEqual(res.status, 401)
        res.read()
        conn.close()

    def test_duplicate_content_length_is_rejected(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.gateway.server_port, timeout=3)
        conn.putrequest("POST", "/devices/pc/mcp")
        conn.putheader("Authorization", "Bearer " + self.token)
        conn.putheader("Content-Length", "1")
        conn.putheader("Content-Length", "1")
        conn.endheaders()
        res = conn.getresponse()
        self.assertEqual(res.status, 400)
        res.read()
        conn.close()

    def test_registry_mode_and_symlink(self):
        path = Path(self.tmp.name) / "protected.sqlite"
        reg = GatewayRegistry(str(path))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        link = Path(self.tmp.name) / "alias.sqlite"
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            GatewayRegistry(str(link))
        path.chmod(0o644)
        with self.assertRaises(PermissionError):
            GatewayRegistry(str(path))

    def test_reject_bad_auth(self):
        self.assertEqual(self.call("GET", token="invalid")[0], 403)
        self.assertEqual(self.call("GET", token="x"*300)[0], 403)
        self.db.revoke_client(self.token)
        self.assertEqual(self.call("GET")[0], 403)

    def test_reject_arbitrary_paths_and_redirects(self):
        self.assertEqual(self.call("GET", path="/devices/pc/../../../etc/passwd")[0], 404)
        self.assertEqual(self.call("GET", path="/devices/pc/mcp?redirect=1")[0], 502)

    def test_revoke_device(self):
        self.db.revoke_device("pc")
        self.assertEqual(self.call("GET")[0], 403)

    def test_invalid_config(self):
        for port in ("20001", -1, 50000):
            with self.assertRaises(ValueError):
                self.db.configure_route("new", port, "a"*32)

    def test_get_and_delete(self):
        for method in ("GET", "DELETE"):
            self.assertEqual(self.call(method)[0], 200)


if __name__ == "__main__":
    unittest.main()
