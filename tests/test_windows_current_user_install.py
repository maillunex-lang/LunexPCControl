from pathlib import Path
import unittest
SCRIPT=Path(__file__).resolve().parents[1]/'agent/windows/Install-CurrentUser.ps1'

class CurrentUserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.source=SCRIPT.read_text('utf-8')
    def test_readonly_default(self):
        self.assertIn('[switch]$Install', self.source)
        self.assertIn('if (-not $Install)', self.source)
    def test_account_isolation(self):
        self.assertIn('$env:LOCALAPPDATA', self.source)
        self.assertIn('WindowsIdentity]::GetCurrent()', self.source)
        self.assertIn('if (-not $interactive)', self.source)
    def test_no_autostart_or_firewall(self):
        for v in ('schtasks', 'New-NetFirewallRule', 'netsh', 'Set-ItemProperty', 'runas'):
            self.assertNotIn(v, self.source)
    def test_compat_path_resolution(self):
        self.assertIn("BootstrapPath = ''", self.source)
        self.assertIn('$MyInvocation.MyCommand.Path', self.source)

    def test_python_scope(self):
        self.assertIn('--scope user', self.source)
        self.assertIn('Python.Python.3.14', self.source)
