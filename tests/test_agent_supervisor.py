from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
TEXT=(ROOT/'agent/windows/Agent-Supervisor.ps1').read_text()

class AgentSupervisorTests(unittest.TestCase):
    def test_interactive_only_and_pinned_identity(self):
        for segment in ("[ValidateSet('Check','Run')]", "UserInteractive",
                        "SessionId", "ssh\\known_hosts", "ssh\\id_ed25519",
                        "'Screenshot,ControlStatus'", "'strict'",
                        "Start-ReverseTunnel.ps1", "Stop-Process",
                        "MaxRetries", "StopOnDisconnect",
                        "'serve','--transport','streamable-http'",
                        "ConnectAsync('127.0.0.1',18789)", "probe -lt 45",
                        "PrivateMcpCredentialAvailable", "WINDOWS_MCP_AUTH_KEY",
                        "Test-McpAuthentication", "StatusCode -eq 401",
                        "taskkill.exe /PID", "Join-Path $PSHOME 'powershell.exe'",
                        "MaxRetries = 0", "while ($MaxRetries -eq 0",
                        "Get-RetryDelay", "DynamicClientIpSupported = $true"):
            self.assertIn(segment,TEXT)
    def test_no_unwanted_autostart_or_extra_commands(self):
        for forbidden in ('schtasks.exe','New-ScheduledTask',
                          'Register-ScheduledTask','Set-ItemProperty',
                          'PowerShell -EncodedCommand','Invoke-Expression',
                          'Set-MpPreference','netsh advfirewall'):
            self.assertNotIn(forbidden,TEXT)
    def test_no_privileged_default(self):
        self.assertIn("if ($Mode -eq 'Check')",TEXT)
        self.assertIn("AutoStartConfiguredByThisScript = $false",TEXT)

if __name__=='__main__':unittest.main()
