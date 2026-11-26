from pathlib import Path
import unittest
SRC=(Path(__file__).resolve().parents[1]/'agent/windows/LocalScreenshotCheck.ps1').read_text('utf-8')
class LocalCheckTests(unittest.TestCase):
 def test_loopback_and_tool_restrictions(self):
  self.assertIn("'127.0.0.1'",SRC)
  self.assertIn("'Screenshot'",SRC)
  self.assertIn("'strict'",SRC)
 def test_one_time_secret_not_logged(self):
  self.assertIn('WINDOWS_MCP_AUTH_KEY',SRC)
  self.assertNotIn('Write-Output $secret',SRC)
 def test_session_guard_and_cleanup(self):
  self.assertIn('$sessionId -le 0',SRC)
  self.assertIn('finally {',SRC)
  self.assertIn('Stop-Process',SRC)
