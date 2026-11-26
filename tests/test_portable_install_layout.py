"""Isolated fresh-install file layout smoke test. No system services modified."""
from __future__ import annotations
import ast
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from installer.install import APP_DIR, FILES, install_directories

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_PYTHON_MODULES = {
    path for path in FILES
    if path.startswith(("server/", "panel/", "installer/"))
    and path.endswith(".py")
}


class PortableLayoutTests(unittest.TestCase):
    def test_every_installed_file_has_an_installable_parent(self):
        dirs = set(install_directories())
        self.assertIn(APP_DIR, dirs)
        for relative, destination in FILES.items():
            self.assertTrue((ROOT / relative).is_file(), relative)
            if destination.is_relative_to(APP_DIR):
                self.assertIn(destination.parent, set(install_directories()), relative)
        self.assertIn(APP_DIR / "installer", set(install_directories()))

    def test_all_local_python_imports_are_in_file_inventory(self):
        modules = {rel[:-3].replace("/", ".") for rel in ACTIVE_PYTHON_MODULES}
        for name in ACTIVE_PYTHON_MODULES:
            content = (ROOT / name).read_text()
            for node in ast.walk(ast.parse(content, filename=name)):
                if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    if node.module.startswith(("server.", "panel.", "installer.")):
                        self.assertIn(node.module, modules, f"{name}: {node.module}")
                elif isinstance(node, ast.Import):
                    for item in node.names:
                        if item.name.startswith(("server.", "panel.", "installer.")):
                            self.assertIn(item.name, modules, f"{name}: {item.name}")

    def test_fresh_layout_imports_and_handles_authorization_offline(self):
        # Materialize exactly the files our portable installer deploys,
        # without touching /opt, /etc, systemd, nginx, or live services.
        with tempfile.TemporaryDirectory(prefix="lunexpc-portable-layout-") as tmp:
            shadow = Path(tmp) / "opt/lunexpc-gateway"
            for folder in install_directories():
                relative = folder.relative_to(APP_DIR)
                (shadow / relative).mkdir(parents=True, exist_ok=True)
            for source, target in FILES.items():
                if not target.is_relative_to(APP_DIR):
                    continue
                dest = shadow / target.relative_to(APP_DIR)
                shutil.copy2(ROOT / source, dest)
            bootstrap = r'''
import base64, json, pathlib, sqlite3, tempfile
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
from panel.server import PanelHandler
from panel.auth import PanelAuth
from server.connector_registry import ConnectorRegistry
from server.gateway import GatewayRegistry
from panel.portal_html import devices_page
with tempfile.TemporaryDirectory() as scratch:
    p=pathlib.Path(scratch)
    gateway=GatewayRegistry(str(p/"gateway.sqlite"))
    conn=ConnectorRegistry(str(p/"connector.sqlite"))
    key=p/"panel-auth.key"
    key.write_text("portable-test-only-private-panel-password-123")
    key.chmod(0o600)
    srv=ThreadingHTTPServer(("127.0.0.1",0),PanelHandler)
    srv.panel_auth=PanelAuth(key)
    srv.connector_registry=conn
    srv.registry_path=str(p/"gateway.sqlite")
    server=Thread(target=srv.serve_forever,daemon=True)
    server.start()
    client=HTTPConnection("127.0.0.1",srv.server_port,timeout=5)
    client.request("GET","/devices",headers={"Host":"rikagro.ru"})
    response=client.getresponse()
    assert response.status==401, response.status
    response.read()
    client.close()
    assert b"api/connectors/invitations" in devices_page()
    srv.shutdown()
    srv.server_close()
    server.join(5)
print("ISOLATED_FRESH_LAYOUT_PASS")
'''
            proc = subprocess.run(
                [sys.executable, "-B", "-c", bootstrap],
                cwd=shadow,
                env={**os.environ, "PYTHONPATH": str(shadow),
                     "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True, text=True, timeout=18)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("ISOLATED_FRESH_LAYOUT_PASS", proc.stdout)


if __name__ == "__main__":
    unittest.main()
