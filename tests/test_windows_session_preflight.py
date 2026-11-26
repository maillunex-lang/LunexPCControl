from pathlib import Path
import unittest

PREFLIGHT = Path(__file__).resolve().parents[1] / "agent/windows/SessionPreflight.ps1"

class SessionPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = PREFLIGHT.read_text(encoding="utf-8")

    def test_session_and_owner_detection(self):
        self.assertIn('WindowsIdentity]::GetCurrent()', self.content)
        self.assertIn('GetCurrentProcess().SessionId', self.content)
        self.assertIn('$_.SessionId -eq $sessionId', self.content)

    def test_current_user_install_only(self):
        self.assertIn("$env:LOCALAPPDATA", self.content)
        self.assertIn('AgentInstalledForThisUser', self.content)

    def test_listener_safety(self):
        self.assertIn('Get-NetTCPConnection', self.content)
        self.assertIn("NonLoopbackListener", self.content)
        self.assertIn("'127.0.0.1','::1'", self.content)
