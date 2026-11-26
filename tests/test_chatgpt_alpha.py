"""Alpha 0.1 plugin credential and public route fail-closed checks."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from installer.chatgpt_key import provision, status, rotate, revoke
from server.gateway import GatewayRegistry
from server.gateway_policy import inspect_request, PolicyError

ROOT = Path(__file__).resolve().parents[1]


class ChatGPTAlphaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.registry_path = self.path / "registry.sqlite"
        self.key = self.path / "alpha.key"
        self.registry = GatewayRegistry(str(self.registry_path))
        self.registry.configure_route("lunex", 23789, "not-a-real-credential-very-long")

    def tearDown(self):
        self.tmp.cleanup()

    def test_provision_rotate_revoke_without_exposing_token(self):
        with patch("installer.chatgpt_key.os.geteuid", return_value=0):
            self.assertFalse(status(self.registry_path, self.key)["configured"])
            result = provision(self.registry_path, self.key)
            self.assertTrue(result["created"])
            self.assertNotIn("token", result)
            self.assertEqual(self.key.stat().st_mode & 0o777, 0o600)
            before = self.key.read_text().strip()
            self.assertIsNotNone(self.registry.authenticate("lunex", before))
            with self.assertRaises(FileExistsError):
                provision(self.registry_path, self.key)
            rotate(self.registry_path, self.key)
            after = self.key.read_text().strip()
            self.assertNotEqual(before, after)
            self.assertIsNone(self.registry.authenticate("lunex", before))
            self.assertIsNotNone(self.registry.authenticate("lunex", after))
            self.assertTrue(status(self.registry_path, self.key)["active"])
            revoke(self.registry_path, self.key)
            self.assertFalse(status(self.registry_path, self.key)["active"])
            self.assertIsNone(self.registry.authenticate("lunex", after))

    def test_symlinked_key_refused(self):
        other = self.path / "other"
        other.write_text("this-is-a-placeholder-long-enough-to-test-key")
        self.key.symlink_to(other)
        with patch("installer.chatgpt_key.os.geteuid", return_value=0):
            with self.assertRaises(FileExistsError):
                provision(self.registry_path, self.key)
            with self.assertRaises(PermissionError):
                rotate(self.registry_path, self.key)

    def test_exact_public_route_disallows_other_methods(self):
        text = (ROOT / "deploy/nginx-lunexpc-chatgpt-alpha.conf").read_text()
        self.assertIn("location = /lunexpc-mcp {", text)
        self.assertIn("limit_except POST { deny all; }", text)
        self.assertIn("proxy_pass http://127.0.0.1:18882/lunexpc-mcp;", text)
        self.assertIn("proxy_set_header Authorization $http_authorization;", text)
        self.assertIn("location ^~ /lunexpc-mcp/ { return 404; }", text)
        self.assertNotIn("proxy_pass http://0.0.0.0", text)

    def test_only_readonly_tools_are_allowed(self):
        for name in ("Screenshot", "ControlStatus"):
            raw = ('{"jsonrpc":"2.0","id":1,"method":"tools/call",'
                   '"params":{"name":"'+name+'","arguments":{}}}').encode()
            self.assertIn(inspect_request(raw), ("call_screenshot", "call_status"))
        for forbidden in ("Type", "Click", "Move", "RunCommand", "FileWrite"):
            raw = ('{"jsonrpc":"2.0","id":1,"method":"tools/call",'
                   '"params":{"name":"'+forbidden+'","arguments":{}}}').encode()
            with self.assertRaises(PolicyError):
                inspect_request(raw)


if __name__ == "__main__":
    unittest.main()
