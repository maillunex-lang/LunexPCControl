from pathlib import Path
import unittest
PATH=Path(__file__).resolve().parents[1]/'agent/windows/Prepare-Interactive.ps1'
class InteractivePrepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.s=PATH.read_text(encoding='utf-8')
    def test_read_only(self):
        for forbidden in ('Start-Process','Invoke-WebRequest','Install-Package','winget install','schtasks','Set-Item','New-Item','Remove-Item'):
            self.assertNotIn(forbidden, self.s)
    def test_user_session(self):
        self.assertIn('WindowsIdentity]::GetCurrent()',self.s)
        self.assertIn('GetCurrentProcess().SessionId',self.s)
        self.assertIn("$env:LOCALAPPDATA",self.s)
