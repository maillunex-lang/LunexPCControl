from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
UNIT=(ROOT/'deploy/lunexpc-gateway.service').read_text()
ROTATE=(ROOT/'deploy/lunexpc-gateway.logrotate').read_text()
class GatewayDeployTests(unittest.TestCase):
 def test_unprivileged_private_service(self):
  for value in ('User=lunexpc-gateway','Group=lunexpc-gateway',
   'ProtectSystem=strict','NoNewPrivileges=yes','CapabilityBoundingSet=',
   'UMask=0077','MemoryMax=256M','RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6'):
   self.assertIn(value,UNIT)
  self.assertNotIn('User=root',UNIT)
 def test_loopback_no_external_listener(self):
  self.assertIn('--port 18880',UNIT)
  self.assertNotIn('--bind 0.0.0.0',UNIT)
  self.assertIn('--audit /var/log/lunexpc-gateway/audit.jsonl',UNIT)
 def test_rotation_permissions(self):
  for value in ('daily','rotate 14','compress','create 0600 lunexpc-gateway lunexpc-gateway','su lunexpc-gateway lunexpc-gateway'):
   self.assertIn(value,ROTATE)
