from pathlib import Path
import tempfile
import unittest

from installer.oauth_setup import provision, status, revoke
from server.gateway import GatewayRegistry


class OAuthSetupTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.path = Path(self.root.name)
        self.secret_dir = self.path / "private"
        self.secret_dir.mkdir(mode=0o700)
        self.key = self.secret_dir / "bridge.key"
        self.registry_file = self.path / "registry.sqlite"
        reg=GatewayRegistry(str(self.registry_file))
        reg.configure_route("lunex",23789,"fictitious-valid-upstream-secret-123456")

    def tearDown(self):
        self.root.cleanup()

    def test_provision_status_revoke_and_no_overwrite(self):
        self.assertEqual(status(self.registry_file,self.key),
                         {"configured":False,"active":False})
        result=provision(self.registry_file,self.key)
        self.assertTrue(result["created"])
        self.assertTrue(result["token_disclosed"] is False)
        self.assertEqual(self.key.stat().st_mode & 0o777,0o600)
        self.assertTrue(status(self.registry_file,self.key)["active"])
        with self.assertRaises(FileExistsError):
            provision(self.registry_file,self.key)
        revoke(self.registry_file,self.key)
        self.assertFalse(status(self.registry_file,self.key)["active"])

    def test_directory_must_be_private(self):
        self.secret_dir.chmod(0o755)
        with self.assertRaises(PermissionError):
            provision(self.registry_file,self.key)

    def test_key_symlink_rejected(self):
        another=self.path/"other.txt"
        another.write_text("private-example-test-not-a-secret-value")
        self.key.symlink_to(another)
        with self.assertRaises(FileExistsError):
            provision(self.registry_file,self.key)


if __name__=="__main__":
    unittest.main()
