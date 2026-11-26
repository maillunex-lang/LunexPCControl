from pathlib import Path
import unittest
SRC=(Path(__file__).resolve().parents[1]/"agent/windows/Run-RemoteMcpSmoke.ps1").read_text()
class RemoteSmokeRunnerTests(unittest.TestCase):
 def test_no_public_exposure(self):
  self.assertIn("'127.0.0.1:23789:127.0.0.1:18789'",SRC)
  self.assertIn("'127.0.0.1'",SRC)
  self.assertIn("'StrictHostKeyChecking=yes'",SRC)
 def test_temp_lifecycle(self):
  self.assertIn("finally {",SRC)
  self.assertIn("Remove-Item -LiteralPath $incoming",SRC)
  self.assertIn("Stop-Process",SRC)
  self.assertIn("DurationSeconds",SRC)
 def test_no_persistence(self):
  self.assertNotIn("schtasks",SRC)
  self.assertNotIn("New-NetFirewallRule",SRC)
