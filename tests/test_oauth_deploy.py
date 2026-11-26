"""Production routing and service-hardening invariants for OAuth."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OAuthDeploymentTests(unittest.TestCase):
    def test_oauth_systemd_bound_to_unprivileged_loopback(self):
        unit=(ROOT/"deploy/lunexpc-oauth.service").read_text()
        for check in (
            "User=lunexpc-gateway",
            "Group=lunexpc-gateway",
            "ProtectSystem=strict",
            "ReadWritePaths=/var/lib/lunexpc-gateway/oauth",
            "NoNewPrivileges=yes",
            "CapabilityBoundingSet=",
            "ProtectHome=yes",
            "MemoryMax=128M",
            "server.oauth_http --bind 127.0.0.1 --port 18882",
            "ConditionPathExists=/var/lib/lunexpc-gateway/oauth/proxy.key",
        ):
            self.assertIn(check,unit)
        for forbidden in (
            "User=root",
            "--bind 0.0.0.0",
            "ReadWritePaths=/var/lib/lunexpc-gateway\n",
        ):
            self.assertNotIn(forbidden,unit)

    def test_nginx_oauth_discovery_and_existing_private_route(self):
        protected=(ROOT/"deploy/nginx-lunexpc-chatgpt-alpha.conf").read_text()
        public=(ROOT/"deploy/nginx-lunexpc-oauth.conf").read_text()
        self.assertIn("location = /lunexpc-mcp {",protected)
        self.assertIn("limit_except POST { deny all; }",protected)
        self.assertIn("proxy_pass http://127.0.0.1:18882/lunexpc-mcp;",protected)
        self.assertIn("proxy_set_header Authorization $http_authorization;",protected)
        self.assertIn("location ^~ /lunexpc-mcp/ { return 404; }",protected)
        for locator in (
            "location = /.well-known/oauth-authorization-server",
            "location = /.well-known/oauth-protected-resource",
            "location = /.well-known/oauth-protected-resource/lunexpc-mcp",
            "location ^~ /oauth/",
            "proxy_pass http://127.0.0.1:18882",
            "auth_basic off",
            "client_max_body_size 8k",
        ):
            self.assertIn(locator,public)
        self.assertNotIn("http://0.0.0.0",protected+public)

    def test_reproducible_nginx_dispatch_template(self):
        source=(ROOT/"deploy/nginx-lunexpc.conf").read_text()
        self.assertIn("location ^~ /lunexpc/ {",source)
        self.assertIn("return 404;",source)
        self.assertIn("include /etc/nginx/snippets/lunexpc-portal.conf;",source)
        self.assertIn("include /etc/nginx/snippets/lunexpc-chatgpt-alpha.conf;",source)
        self.assertIn("include /etc/nginx/snippets/lunexpc-oauth.conf;",source)

    def test_plugin_uses_dcr_pkce_with_read_only_scope(self):
        manifest=json.loads((ROOT/"chatgpt-plugin/mcp.json").read_text())
        auth=manifest["mcpServers"]["lunexpc-readonly"]["extensions"]["com.openai"]["auth"]
        self.assertEqual(auth,{"type":"oauth","client":{"mode":"dcr"},
                               "baseScopes":["desktop:read"]})
        root=json.loads((ROOT/"chatgpt-plugin/plugin.json").read_text())
        self.assertEqual(root["version"],"0.1.1")

    def test_all_first_party_oauth_sources_in_install_inventory(self):
        from installer.install import FILES
        for relative in (
            "server/oauth_store.py",
            "server/oauth_http.py",
            "deploy/lunexpc-oauth.service",
            "deploy/nginx-lunexpc-oauth.conf",
            "deploy/nginx-lunexpc-chatgpt-alpha.conf",
        ):
            self.assertIn(relative,FILES)

    def test_encrypted_state_migration_includes_oauth_files(self):
        from installer.migration import OPTIONAL
        self.assertIn("var/lib/lunexpc-gateway/oauth/issuer.sqlite", OPTIONAL)
        self.assertIn("var/lib/lunexpc-gateway/oauth/proxy.key", OPTIONAL)


if __name__=="__main__":
    unittest.main()
