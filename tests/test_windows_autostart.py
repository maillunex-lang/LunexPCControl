from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
CODE=(ROOT/"agent/windows/AutoStart-Interactive.ps1").read_text()

class AutostartTests(unittest.TestCase):
    def test_opt_in_and_user_session_only(self):
        for part in ("'Check','Install','Disable'","'Check'","UserInteractive",
                     "SessionId","Get-ScheduledTask","New-ScheduledTaskAction",
                     "New-ScheduledTaskTrigger","-AtLogOn -User $identity",
                     "-LogonType Interactive -RunLevel Limited",
                     "-MultipleInstances IgnoreNew","Register-ScheduledTask",
                     "-MaxRetries 0","Disable-ScheduledTask"):
            self.assertIn(part,CODE)
    def test_no_password_storage_or_elevation(self):
        for forbidden in ("-RunLevel Highest","-LogonType Password",
                          "-UserId SYSTEM","netsh advfirewall",
                          "Set-MpPreference","-Force",
                          "schtasks.exe /create","New-Service"):
            self.assertNotIn(forbidden,CODE)

if __name__=="__main__":
    unittest.main()
