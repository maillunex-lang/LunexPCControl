import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'installer/install.py'
spec = importlib.util.spec_from_file_location("lunexpc_installer", PATH)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class PortableInstallerTests(unittest.TestCase):
    def test_source_inventory(self):
        installer.validate_source()
        self.assertIn("server/gateway.py", installer.FILES)
        self.assertIn("deploy/lunexpc-gateway.service", installer.FILES)
        self.assertIn("deploy/lunexpc-panel.service", installer.FILES)
        self.assertIn("panel/server.py", installer.FILES)
        self.assertIn("panel/auth.py", installer.FILES)
        self.assertIn("installer/backup.py", installer.FILES)
        self.assertIn("installer/upgrade.py", installer.FILES)
        self.assertIn("installer/install.py", installer.FILES)
        self.assertIn("server/connector_registry.py", installer.FILES)
        self.assertIn("deploy/nginx-portalmcp.conf", installer.FILES)
        self.assertIn("deploy/nginx-portalmcp-rate-limit.conf", installer.FILES)
        self.assertIn("deploy/lunexpc-connector.service", installer.FILES)
        self.assertIn("server/sealed_token.py", installer.FILES)

    def test_nested_installer_directory_is_created_before_file_install(self):
        dirs = installer.install_directories()
        self.assertIn(installer.APP_DIR / "installer", dirs)
        self.assertIn(installer.APP_DIR / "panel", dirs)
        self.assertIn(installer.APP_DIR / "server", dirs)
        self.assertIn(installer.APP_DIR / "deploy", dirs)
        self.assertEqual(dirs[0], installer.APP_DIR)

    def test_default_is_readonly(self):
        code = PATH.read_text()
        self.assertIn('parser.add_argument("--apply", action="store_true"', code)
        self.assertIn("if args.apply:", code)
        self.assertIn("existing installation: use a dedicated upgrade", code)

    def test_protected_targets(self):
        for target in installer.FILES.values():
            self.assertTrue(str(target).startswith(("/opt/lunexpc-gateway/","/etc/")))
        for banned in ('nginx -s reload', 'ufw allow', 'ssh-keygen -A', 'systemctl enable'):
            self.assertNotIn(banned, PATH.read_text())

    def test_no_existing_overwrite(self):
        with patch.object(installer, "is_existing_install", return_value=True):
            with patch.object(installer.os, "geteuid", return_value=0):
                with self.assertRaisesRegex(RuntimeError,"existing installation"):
                    installer.apply_install()
