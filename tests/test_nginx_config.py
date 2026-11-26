from pathlib import Path
import unittest
BASE=Path(__file__).resolve().parents[1]/'server'
class NginxConfigurationTests(unittest.TestCase):
 def test_default_blocks_everything(self):
  content=(BASE/'nginx-lunexpc.conf').read_text()
  self.assertIn('location ^~ /lunexpc/',content)
  self.assertEqual(content.count('return 404;'),2)
  self.assertNotIn('proxy_pass',content)
 def test_enable_example_binds_loopback_and_preserves_auth(self):
  content=(BASE/'nginx-lunexpc-enabled.example.conf').read_text()
  for phrase in ('127.0.0.1:18880','proxy_set_header Authorization $http_authorization','proxy_buffering off','client_max_body_size 4m','proxy_redirect off','limit_except GET POST DELETE'):
   self.assertIn(phrase,content)
  self.assertNotIn('0.0.0.0:18880',content)
  self.assertNotIn('proxy_pass http://195.',content)
