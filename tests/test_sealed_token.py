import unittest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.exceptions import InvalidTag
from server.sealed_token import seal,open_sealed

class SealedTokenTests(unittest.TestCase):
 def test_roundtrip(self):
  private=X25519PrivateKey.generate()
  public=private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
  for value in (b'hello secret '*3,b'x'*128):
   doc=seal(public,value)
   self.assertNotIn(value,doc)
   self.assertEqual(open_sealed(private,doc),value)
 def test_wrong_device_cannot_decrypt(self):
  a=X25519PrivateKey.generate()
  public=a.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
  blob=seal(public,b'one time auth token '*3)
  with self.assertRaises(InvalidTag):open_sealed(X25519PrivateKey.generate(),blob)
 def test_invalid_envelopes(self):
  a=X25519PrivateKey.generate()
  public=a.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
  with self.assertRaises(ValueError):seal(b'wrong',b'secret secret secret secret')
  with self.assertRaises(ValueError):seal(public,b'short')
  with self.assertRaises(ValueError):open_sealed(a,b'X'*3000)
  with self.assertRaises(ValueError):open_sealed(a,b'{"v":2}')
