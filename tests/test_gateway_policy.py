import json
import os
from pathlib import Path
import tempfile
import unittest
from server.gateway_policy import (inspect_request, PolicyError, filtered_response,
                                   filtered_sse_event, RateLimiter, AuditLog)


class GatewayPolicyTests(unittest.TestCase):
    def request(self, method, params=None):
        return json.dumps({"jsonrpc":"2.0","id":1,"method":method,
                           "params": params if params is not None else {}}).encode()

    def test_only_read_only_tools(self):
        self.assertEqual(inspect_request(self.request("tools/call",{
            "name":"Screenshot","arguments":{}})), "call_screenshot")
        self.assertEqual(inspect_request(self.request("tools/call",{
            "name":"ControlStatus","arguments":{}})), "call_status")
        for name in ("PowerShell","Click","Type","Drag","FileSystem","ScreenshotAdmin"):
            with self.subTest(name=name), self.assertRaises(PolicyError) as e:
                inspect_request(self.request("tools/call",{"name":name}))
            self.assertEqual(e.exception.status,403)

    def test_ambiguous_and_unsafe_requests(self):
        for body in (
            b'{"jsonrpc":"2.0","id":1,"method":"tools/list","method":"tools/call"}',
            b'[{"jsonrpc":"2.0","id":1,"method":"tools/list"}]',
            b'{"jsonrpc":"2.0","id":1,"method":"resources/list"}',
            self.request("tools/call",{"name":"Screenshot","arguments":{"x":1}}),
            self.request("tools/call",{"name":"Screenshot","arguments":[]}),
            self.request("tools/call",{"name":[]}),
            b'{"jsonrpc":"2.0","id":1,"method":["tools/list"]}', 
            b'invalid json',
            b'{"jsonrpc":"2.0","method":"tools/list"}'
        ):
            with self.subTest(body=body[:50]), self.assertRaises(PolicyError):
                inspect_request(body)

    def test_initialize_and_notification(self):
        self.assertEqual(inspect_request(self.request("initialize")),"initialize")
        self.assertEqual(inspect_request(b'{"jsonrpc":"2.0","method":"notifications/initialized"}'),"notification")
        self.assertEqual(inspect_request(self.request("ping")),"ping")

    def test_modern_discovery_filters_untrusted_capabilities(self):
        request=self.request("server/discover",{
            "_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28",
                     "io.modelcontextprotocol/clientCapabilities":{}}})
        self.assertEqual(inspect_request(request),"discover")
        payload={"jsonrpc":"2.0","id":7,"result":{
            "resultType":"complete","supportedVersions":["2026-07-28"],
            "capabilities":{"tools":{"listChanged":True},"resources":{},
                            "prompts":{},"sampling":{}},
            "instructions":"do not expose upstream instructions",
            "cacheScope":"public"}}
        reply=json.loads(filtered_response(json.dumps(payload).encode(),"discover"))
        assert_result=reply["result"]
        self.assertEqual(assert_result["supportedVersions"],["2026-07-28"])
        self.assertEqual(assert_result["capabilities"],{"tools":{}})
        self.assertEqual(assert_result["cacheScope"],"private")
        self.assertNotIn("instructions",assert_result)
        self.assertNotIn("resources",str(assert_result))
        self.assertEqual(assert_result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"],
                         "LunexPCControl")
        event=b"event: message\ndata: "+json.dumps(payload).encode()+b"\n\n"
        self.assertNotIn(b"instructions",filtered_sse_event(event,"discover"))
        with self.assertRaises(PolicyError) as error:
            inspect_request(self.request("server/sensitive"))
        self.assertEqual(error.exception.status,403)
        with self.assertRaises(PolicyError):
            filtered_response(b'{"result":{"capabilities":{"resources":{}}}}',"discover")

    def test_filter_tools_json_and_sse(self):
        doc={"jsonrpc":"2.0","id":1,"result":{"tools":[
            {"name":"Screenshot"},{"name":"PowerShell"},{"name":"ControlStatus"}
        ],"nextCursor":"unsafe"}}
        filtered=json.loads(filtered_response(json.dumps(doc).encode(),"list"))
        self.assertEqual([x["name"] for x in filtered["result"]["tools"]],
                         ["Screenshot","ControlStatus"])
        self.assertNotIn("nextCursor",filtered["result"])
        self.assertEqual(set(filtered["result"]["tools"][0]), {"name","description","inputSchema"})
        event=(b"event: message\r\ndata: "+json.dumps(doc).encode()+b"\r\n\r\n")
        output=filtered_sse_event(event,"list")
        self.assertNotIn(b"PowerShell",output)
        self.assertIn(b"Screenshot",output)
        self.assertEqual(filtered_sse_event(b": keepalive\n\n","list"),b": keepalive\n\n")
        with self.assertRaises(PolicyError):
            filtered_response(b'{"result":{"tools": "bad"}}',"list")

    def test_limiter(self):
        timer=[0.0]
        limiter=RateLimiter(limit=2,window=10,max_identities=2,clock=lambda:timer[0])
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))
        self.assertTrue(limiter.allow("b"))
        self.assertFalse(limiter.allow("c"))
        timer[0]=11.0
        self.assertTrue(limiter.allow("c"))

    def test_audit_redaction_and_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"audit.jsonl"
            audit=AuditLog(path)
            audit.record("blocked","denied",403)
            audit.record("allowed","call_screenshot",200)
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            data=path.read_text()
            self.assertIn("call_screenshot",data)
            self.assertNotIn("Authorization",data)
            self.assertEqual(len(data.splitlines()),2)
            with self.assertRaises(ValueError):
                audit.record("some-user-supplied-data","denied",403)
            path.chmod(0o644)
            with self.assertRaises(PermissionError):
                audit.record("blocked","denied",403)
            alias=Path(d)/"alias"
            alias.symlink_to(path)
            with self.assertRaises((OSError,PermissionError)):
                AuditLog(alias)
