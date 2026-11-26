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
 def test_does_not_confuse_ssh_port_with_reverse_forward(self):
  self.assertNotIn('Test-NetConnection',SRC)
  self.assertIn('VPS test runner separately verifies',SRC)
 def test_child_process_cleanup_and_preexisting_tunnel_guard(self):
  self.assertIn('taskkill.exe /PID',SRC)
  self.assertIn('/T /F',SRC)
  self.assertIn('Get-NetTCPConnection -LocalPort 18789',SRC)
  self.assertIn('Existing device tunnel in this session',SRC)
  self.assertIn('REMOTE-MCP-CLEANUP-COMPLETE',SRC)
 def test_no_persistence(self):
  self.assertNotIn("schtasks",SRC)
  self.assertNotIn("New-NetFirewallRule",SRC)
