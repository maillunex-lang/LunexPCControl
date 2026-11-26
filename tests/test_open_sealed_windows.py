import importlib.util
from pathlib import Path
import tempfile
import unittest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,NoEncryption,PublicFormat
from server.sealed_token import seal
P=Path(__file__).resolve().parents[1]/'agent/windows/Open-SealedToken.py'
spec=importlib.util.spec_from_file_location('open_sealed_win',P)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class OpenSealedTests(unittest.TestCase):
 def test_local_open(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)
   key=X25519PrivateKey.generate()
   private=folder/'private.pem'; private.write_bytes(key.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()))
   public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
   payload=b'test-password-but-not-printed'
   sealed=folder/'packet.json'; sealed.write_bytes(seal(public,payload))
   self.assertEqual(mod.open_local(private,sealed),__import__('hashlib').sha256(payload).hexdigest())
 def test_output_is_private_and_never_overwritten(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)
   key=X25519PrivateKey.generate()
   private=folder/'private.pem';private.write_bytes(key.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()))
   public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
   payload=b'secret-long-token-not-for-logs'
   sealed=folder/'sealed.json';sealed.write_bytes(seal(public,payload))
   output=folder/'protected'/'secret.key'
   self.assertEqual(mod.open_local(private,sealed,output),__import__('hashlib').sha256(payload).hexdigest())
   self.assertEqual(output.read_bytes(),payload+b'\n')
   with self.assertRaises(FileExistsError):
    mod.open_local(private,sealed,output)
 def test_no_stdout_secret(self):
  content=P.read_text()
  self.assertIn('hashlib.sha256(plain).hexdigest()',content)
  self.assertNotIn('print(plain)',content)
