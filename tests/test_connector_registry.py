import base64
import os
from pathlib import Path
import stat
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from server.connector_registry import ConnectorRegistry, PairingError, signature_payload


def pub64(key):
    raw=key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)
    return base64.urlsafe_b64encode(raw).decode("ascii")


class ConnectorRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"connector.sqlite"
        self.now=1000000
        self.reg=ConnectorRegistry(self.path,clock=lambda:self.now)
        self.key=Ed25519PrivateKey.generate()
    def tearDown(self):
        self.tmp.cleanup()

    def test_invite_is_secret_and_expires_and_is_one_time(self):
        invitation=self.reg.invite("windows","Desktop")
        code=invitation["pairing_code"]
        raw=self.path.read_bytes()
        self.assertNotIn(code.encode(),raw)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode),0o600)
        with self.assertRaises(PairingError):
            self.reg.claim(code,"linux",pub64(self.key))
        result=self.reg.claim(code,"windows",pub64(self.key))
        self.assertEqual(result["name"],"Desktop")
        self.assertEqual(len(result["device_id"]),32)
        self.assertEqual(len(self.reg.list_devices()),1)
        with self.assertRaises(PairingError):
            self.reg.claim(code,"windows",pub64(Ed25519PrivateKey.generate()))
        another=self.reg.invite("linux","Ubuntu")
        self.now+=601
        with self.assertRaises(PairingError):
            self.reg.claim(another["pairing_code"],"linux",pub64(Ed25519PrivateKey.generate()))

    def test_heartbeat_signature_replay_skew_and_revoke(self):
        code=self.reg.invite("windows","Desktop")["pairing_code"]
        device=self.reg.claim(code,"windows",pub64(self.key))["device_id"]
        nonce="nonce_abcdefgh1234567890"
        message=signature_payload(device,self.now,nonce)
        signed=base64.urlsafe_b64encode(self.key.sign(message)).decode("ascii")
        self.assertEqual(self.reg.heartbeat(device,self.now,nonce,signed),{"online":True})
        self.assertTrue(self.reg.list_devices()[0]["online"])
        with self.assertRaises(PairingError):
            self.reg.heartbeat(device,self.now,nonce,signed)
        with self.assertRaises(PairingError):
            self.reg.heartbeat(device,self.now,"nonce_different1234567890",signed)
        self.now+=91
        self.assertFalse(self.reg.list_devices()[0]["online"])
        with self.assertRaises(PairingError):
            self.reg.heartbeat(device,self.now-91,"another_nonce1234567890",signed)
        self.assertEqual(self.reg.revoke(device),{"revoked":True})
        self.assertEqual(self.reg.list_devices(),[])
        with self.assertRaises(PairingError):
            self.reg.heartbeat(device,self.now,"nonce_abcdefgh1234567890",
                               base64.urlsafe_b64encode(self.key.sign(
                                 signature_payload(device,self.now,"nonce_abcdefgh1234567890")
                               )).decode("ascii"))
    def test_invalid_inputs(self):
        for osname in ("windows 11","mac","",None):
            with self.assertRaises(PairingError):
                self.reg.invite(osname,"Machine")
        for name in ("", "../tmp","<img>","long"*25):
            with self.assertRaises(PairingError):
                self.reg.invite("windows",name)
        ru=self.reg.invite("windows","Мой компьютер")
        self.assertEqual(ru["name"],"Мой компьютер")
        with self.assertRaises(PairingError):
            self.reg.claim("short","windows",pub64(self.key))
        with self.assertRaises(PairingError):
            self.reg.revoke("../")
    def test_public_key_reuse_rejected(self):
        first=self.reg.invite("windows","A")
        self.reg.claim(first["pairing_code"],"windows",pub64(self.key))
        second=self.reg.invite("windows","B")
        with self.assertRaises(PairingError):
            self.reg.claim(second["pairing_code"],"windows",pub64(self.key))
    def test_no_symlink_and_private_storage(self):
        pointer=Path(self.tmp.name)/"link.db"
        pointer.symlink_to(self.path)
        with self.assertRaises(PermissionError):
            ConnectorRegistry(pointer)
        os.chmod(self.path,0o644)
        with self.assertRaises(PermissionError):
            ConnectorRegistry(self.path)


if __name__=="__main__":
    unittest.main()
