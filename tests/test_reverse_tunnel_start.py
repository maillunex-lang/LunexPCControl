from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1]/"agent/windows/Start-ReverseTunnel.ps1"
class ReverseTunnelStartTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.s=P.read_text("utf-8")
 def test_key_only_and_strict_host(self):
  for arg in ("BatchMode=yes","PasswordAuthentication=no","StrictHostKeyChecking=yes","UpdateHostKeys=no","UserKnownHostsFile=","IdentitiesOnly=yes"):
   self.assertIn(arg,self.s)
  self.assertNotIn("StrictHostKeyChecking=no",self.s)
 def test_fixed_loopback_forward(self):
  self.assertIn("127.0.0.1:",self.s)
  self.assertIn("$RemotePort + ':127.0.0.1:'",self.s)
  self.assertIn("-N -T -R",self.s)
  self.assertIn("$RemotePort -ne 23789",self.s)
 def test_no_autostart(self):
  for name in ("schtasks","New-NetFirewallRule","Start-Service","Set-Service","-o GatewayPorts=yes"):
   self.assertNotIn(name,self.s)
