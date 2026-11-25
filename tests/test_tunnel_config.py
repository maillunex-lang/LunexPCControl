import base64
import struct
import unittest
from server.tunnel_config import authorized_key

KEY = 'ssh-ed25519 ' + base64.b64encode(struct.pack('>I', 11)+b'ssh-ed25519'+struct.pack('>I', 32)+bytes(range(32))).decode()

class TunnelTests(unittest.TestCase):
    def test_restrictions(self):
        result = authorized_key(KEY, 20001)
        self.assertIn('permitlisten="127.0.0.1:20001"', result)
        self.assertIn('restrict,port-forwarding', result)
        self.assertIn('command="/bin/false"', result)
    def test_ports(self):
        for port in (22, 30000, '20001', True):
            with self.assertRaises(ValueError):
                authorized_key(KEY, port)
    def test_bad_key(self):
        for key in ('ssh-rsa abc', 'ssh-ed25519 AAAA', 'ssh-ed25519 !!!'):
            with self.assertRaises(ValueError):
                authorized_key(key, 20001)
