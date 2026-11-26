"""Full HTTP path tests for fail-closed MCP restrictions."""
import http.client
import base64
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from server.gateway import GatewayRegistry, make_handler, serve
from server.gateway_policy import AuditLog, RateLimiter
from server.screen_history import ScreenHistory
from tests.test_screen_history import sample_png


TOOLS = [
    {"name": "Screenshot", "description": "view", "inputSchema": {"type":"object"}},
    {"name": "ControlStatus", "description": "status", "inputSchema": {"type":"object"}},
    {"name": "PowerShell", "description": "unsafe tool, don't publish",
     "inputSchema": {"type":"object"}},
    {"name": "Click", "description": "unsafe", "inputSchema": {}}
]


class UpstreamMCP(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        request = json.loads(body)
        self.server.received.append(request)
        if hasattr(self.server, "block_until"):
            self.server.request_arrived.set()
            self.server.block_until.wait(timeout=3)
        if request["method"] == "tools/list":
            result = {"tools": TOOLS, "nextCursor": "do-not-share",
                      "unexpected": "private-upstream-detail"}
            if isinstance(request.get("params",{}).get("_meta"),dict):
                result["resultType"]="complete"
        elif request["method"] == "server/discover":
            result = {"resultType":"complete","supportedVersions":["2026-07-28"],
                      "capabilities":{"tools":{"listChanged":True},"resources":{},
                                      "prompts":{}},
                      "instructions":"untrusted Windows agent capability text"}
        elif request["method"] == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {
                "tools": {}, "resources": {}, "prompts": {}},
                "serverInfo": {"name": "fake", "version": "1.0"},
                "instructions": "private-upstream-instructions"}
        else:
            result = {"content": [
                {"type": "image", "mimeType": "image/png", "data": base64.b64encode(sample_png()).decode()}
            ]}
        data = json.dumps({"jsonrpc": "2.0", "id": request.get("id"),
                           "result": result}).encode()
        if "text/event-stream" in self.headers.get("Accept", ""):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"event: message\r\n")
            self.wfile.flush()
            self.wfile.write(b"data: " + data + b"\r\n\r\n")
            self.wfile.flush()
            self.close_connection = True
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def log_message(self, *_):
        pass


def start(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class SecurityHTTPTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.upstream = start(UpstreamMCP)
        self.upstream.received = []
        self.registry = GatewayRegistry(os.path.join(self.folder.name, "registry.db"))
        with sqlite3.connect(self.registry.path) as db:
            db.execute("INSERT INTO routes VALUES (?,?,?)",
                       ("pc", self.upstream.server_port, "separate-upstream-" + "z"*32))
        self.token = self.registry.create_client("pc")
        self.audit_file = Path(self.folder.name) / "events.jsonl"
        self.audit = AuditLog(self.audit_file)
        self.screens = ScreenHistory(Path(self.folder.name) / "screens")
        self.gateway = start(make_handler(
            self.registry, audit=self.audit,
            rate_limiter=RateLimiter(limit=100,window=60),
            screen_history=self.screens))

    def tearDown(self):
        self.gateway.shutdown()
        self.gateway.server_close()
        self.upstream.shutdown()
        self.upstream.server_close()
        self.folder.cleanup()

    def rpc(self, method, params=None, token=None, sse=False):
        request = {"jsonrpc": "2.0", "id": 1, "method": method,
                   "params": params if params is not None else {}}
        conn = http.client.HTTPConnection("127.0.0.1", self.gateway.server_port, timeout=3)
        conn.request("POST", "/devices/pc/mcp",
                     body=json.dumps(request).encode(),
                     headers={
                         "Authorization": "Bearer " + (self.token if token is None else token),
                         "Content-Type": "application/json",
                         "Accept": "text/event-stream" if sse else "application/json"
                     })
        response = conn.getresponse()
        status = response.status
        output = response.read()
        conn.close()
        return status, output

    def wait_audit(self, minimum):
        for attempt in range(30):
            entries = self.audit_file.read_text().splitlines()
            if len(entries) >= minimum:
                return entries
            time.sleep(.02)
        return self.audit_file.read_text().splitlines()

    def test_denied_methods_never_reach_windows(self):
        for method, params in (
            ("tools/call", {"name": "PowerShell"}),
            ("tools/call", {"name": "Click"}),
            ("tools/call", {"name": "Screenshot", "arguments": {"x": 4}}),
            ("resources/read", {"uri":"file:///secret"}),
            ("prompts/list", {}),
        ):
            with self.subTest(method=method,params=params):
                status, _ = self.rpc(method, params)
                self.assertEqual(status, 403)
        self.assertEqual(self.upstream.received, [])
        lines = self.wait_audit(5)
        events = "\n".join(lines)
        self.assertNotIn(self.token, events)
        self.assertNotIn("PowerShell", events)
        self.assertNotIn("file:///secret", events)
        self.assertEqual(len(lines), 5)

    def test_filters_json_tool_catalog_and_capabilities(self):
        status, reply = self.rpc("tools/list")
        self.assertEqual(status, 200)
        result = json.loads(reply)["result"]
        self.assertEqual([tool["name"] for tool in result["tools"]],
                         ["Screenshot", "ControlStatus"])
        self.assertNotIn("nextCursor", result)
        self.assertNotIn("private-upstream-detail", reply.decode())
        self.assertNotIn("unsafe tool", reply.decode())
        self.assertTrue(all(not tool["inputSchema"]["additionalProperties"]
                            for tool in result["tools"]))
        status, reply = self.rpc("initialize")
        self.assertEqual(status,200)
        self.assertEqual(json.loads(reply)["result"]["capabilities"],
                         {"tools":{}})
        self.assertNotIn("private-upstream-instructions",reply.decode())

    def test_modern_chatgpt_discovery_and_tools_are_read_only(self):
        meta={"io.modelcontextprotocol/protocolVersion":"2026-07-28",
              "io.modelcontextprotocol/clientCapabilities":{},
              "io.modelcontextprotocol/clientInfo":{"name":"synthetic-chatgpt",
                                                       "version":"1"}}
        def modern(method,params=None,header_method=None,header_name=None):
            req={"jsonrpc":"2.0","id":101,"method":method,
                 "params":{"_meta":meta,**(params or {})}}
            headers={"Authorization":"Bearer "+self.token,
                     "Content-Type":"application/json",
                     "Accept":"application/json, text/event-stream",
                     "Mcp-Protocol-Version":"2026-07-28",
                     "Mcp-Method":header_method or method}
            if header_name is not None:
                headers["Mcp-Name"]=header_name
            con=http.client.HTTPConnection("127.0.0.1",self.gateway.server_port,timeout=3)
            con.request("POST","/devices/pc/mcp",body=json.dumps(req).encode(),headers=headers)
            reply=con.getresponse()
            result=(reply.status,reply.read())
            con.close()
            return result
        def decoded(data):
            if data.startswith(b"event:") or data.startswith(b"data:"):
                data=next(line[5:].strip() for line in data.splitlines()
                          if line.startswith(b"data:"))
            return json.loads(data)
        status,data=modern("server/discover")
        self.assertEqual(status,200,data)
        info=decoded(data)["result"]
        self.assertEqual(info["supportedVersions"],["2026-07-28"])
        self.assertEqual(info["capabilities"],{"tools":{}})
        self.assertNotIn("untrusted Windows",str(info))
        status,data=modern("tools/list")
        self.assertEqual(status,200,data)
        result=decoded(data)["result"]
        self.assertEqual(result["resultType"],"complete")
        self.assertEqual([x["name"] for x in result["tools"]],
                         ["Screenshot","ControlStatus"])
        self.assertNotIn("PowerShell",str(result))
        status,data=modern("tools/call",{"name":"ControlStatus",
                          "arguments":{}},header_name="ControlStatus")
        self.assertEqual(status,200,data)
        self.assertIn("result",decoded(data))
        self.assertEqual(modern("tools/call",{"name":"PowerShell",
                        "arguments":{}},header_name="PowerShell")[0],403)
        self.assertEqual(modern("tools/call",{"name":"Screenshot",
                        "arguments":{}},header_name="Click")[0],400)
        self.assertEqual(modern("tools/list",header_method="tools/call")[0],400)
        self.assertEqual(modern("resources/list")[0],403)
        self.assertEqual([x["method"] for x in self.upstream.received],
                         ["server/discover","tools/list","tools/call"])

    def test_filters_sse_tool_catalog(self):
        status, body = self.rpc("tools/list", sse=True)
        self.assertEqual(status, 200)
        self.assertIn(b"Screenshot", body)
        self.assertIn(b"ControlStatus", body)
        self.assertNotIn(b"PowerShell", body)
        self.assertNotIn(b"nextCursor", body)
        status, body = self.rpc("initialize", sse=True)
        self.assertEqual(status, 200)
        self.assertNotIn(b"resources",body)
        self.assertNotIn(b"prompts",body)

    def test_screenshot_archived_only_after_opt_in(self):
        status, response = self.rpc("tools/call",{"name":"Screenshot","arguments":{}})
        self.assertEqual(status,200)
        self.assertEqual(self.screens.list(),[])
        self.screens.configure(24,50)
        status, response = self.rpc("tools/call",{"name":"Screenshot","arguments":{}})
        self.assertEqual(status,200)
        images=self.screens.list()
        self.assertEqual(len(images),1)
        self.assertEqual(self.screens.image(images[0]["id"]),sample_png())
        self.assertEqual(self.rpc("tools/call",{"name":"PowerShell"})[0],403)
        self.assertEqual(len(self.screens.list()),1)
        self.screens.configure(0)
        self.assertEqual(self.screens.list(),[])

    def test_screenshot_sse_archived(self):
        self.screens.configure(24,50)
        status, data = self.rpc("tools/call",{"name":"Screenshot","arguments":{}},sse=True)
        self.assertEqual(status,200)
        self.assertIn(b"data:",data)
        self.assertEqual(len(self.screens.list()),1)
        self.assertEqual(self.screens.image(self.screens.list()[0]["id"]),sample_png())

    def test_read_only_call_and_audit(self):
        status, body = self.rpc("tools/call", {"name": "Screenshot", "arguments": {}})
        self.assertEqual(status, 200)
        self.assertIn(b"iVBORw0KGgo",body)
        self.assertEqual(len(self.upstream.received), 1)
        entries = [json.loads(line) for line in self.wait_audit(1)]
        self.assertEqual(entries[0]["event"], "allowed")
        self.assertEqual(entries[0]["method"], "call_screenshot")
        self.assertEqual(set(entries[0]), {"ts","event","method","status"})
        self.assertNotIn(self.token, self.audit_file.read_text())

    def test_rate_limit_and_auth_denial(self):
        self.gateway.shutdown()
        self.gateway.server_close()
        self.gateway = start(make_handler(
            self.registry, audit=self.audit,
            rate_limiter=RateLimiter(limit=2,window=60)))
        for _ in range(2):
            self.assertEqual(self.rpc("ping")[0], 200)
        self.assertEqual(self.rpc("ping")[0], 429)
        self.assertEqual(len(self.upstream.received), 2)
        self.assertEqual(self.rpc("ping", token="invalid")[0], 403)
        entries = [json.loads(line) for line in self.wait_audit(4)]
        self.assertTrue(any(entry["event"]=="rate_limited" for entry in entries))
        self.assertTrue(any(entry["event"]=="unauthorized" for entry in entries))

    def test_concurrent_request_limit(self):
        self.gateway.shutdown()
        self.gateway.server_close()
        self.gateway = start(make_handler(
            self.registry, audit=self.audit, max_active=1))
        self.upstream.request_arrived = threading.Event()
        self.upstream.block_until = threading.Event()
        results = []
        worker = threading.Thread(
            target=lambda: results.append(self.rpc("ping")[0]), daemon=True)
        worker.start()
        self.assertTrue(self.upstream.request_arrived.wait(timeout=2))
        try:
            self.assertEqual(self.rpc("ping")[0], 503)
        finally:
            self.upstream.block_until.set()
        worker.join(timeout=3)
        self.assertEqual(results, [200])
        self.assertTrue(any(json.loads(line)["event"]=="over_capacity"
                            for line in self.wait_audit(2)))

    def test_serving_requires_private_audit_path(self):
        with self.assertRaisesRegex(ValueError, "audit path"):
            serve(self.registry.path)

    def test_audit_file_stays_private(self):
        self.rpc("tools/list")
        self.assertEqual(self.audit_file.stat().st_mode & 0o777, 0o600)
        data="\n".join(self.wait_audit(1))
        for secret in (self.token, "separate-upstream-", "iVBOR", "/devices/pc/mcp"):
            self.assertNotIn(secret,data)


if __name__ == "__main__":
    unittest.main()
