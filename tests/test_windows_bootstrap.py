import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "agent/windows/Bootstrap.ps1"

class BootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = SCRIPT.read_text(encoding="utf-8")

    def test_readonly_default(self):
        self.assertIn("if (-not $Install -and -not $Start)", self.content)
        self.assertIn("Get-State", self.content)

    def test_pinned_isolated_install(self):
        self.assertIn("git clone --no-checkout", self.content)
        self.assertIn("checkout --detach $UpstreamCommit", self.content)
        self.assertIn("-m venv $venvDir", self.content)
        self.assertNotIn("winget install", self.content)

    def test_local_binding_and_auth(self):
        self.assertIn("--host 127.0.0.1", self.content)
        self.assertIn("WINDOWS_MCP_AUTH_KEY", self.content)
        self.assertIn("ANONYMIZED_TELEMETRY", self.content)

    def test_no_scheduled_task(self):
        self.assertNotIn("schtasks", self.content.lower())
        self.assertNotIn("New-NetFirewallRule", self.content)
