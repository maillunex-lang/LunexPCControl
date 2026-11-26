from pathlib import Path
import unittest
SRC=(Path(__file__).resolve().parents[1]/'agent/windows/Prepare-RemoteMcpSmoke.ps1').read_text()
class PrepareRemoteMcpSmokeTests(unittest.TestCase):
 def test_requires_interactive_and_protected_folder(self):
  for field in ('GetCurrentProcess().SessionId','$session -le 0','icacls.exe','/inheritance:r'):
   self.assertIn(field,SRC)
 def test_no_secrets_on_command_line(self):
  self.assertIn('--output $output --quiet',SRC)
  self.assertIn('Existing MCP credential; refusing overwrite',SRC)
  self.assertNotIn('Write-Output $key',SRC)
