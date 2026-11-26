from pathlib import Path
import unittest
S=(Path(__file__).resolve().parents[1]/'deploy/verify-gateway.sh').read_text()
class VerifyGatewayScriptTests(unittest.TestCase):
 def test_security_checks(self):
  for value in ("127[.]0[.]0[.]1:18880", "'%{http_code}'", '401', '403', 'systemctl is-active', 'nginx -t', 'audit.jsonl','registry.sqlite'):
   self.assertIn(value,S)
 def test_read_only(self):
  for value in ('systemctl start','systemctl reload','systemctl enable','rm -','chmod ','chown ','curl --data'):
   self.assertNotIn(value,S)
