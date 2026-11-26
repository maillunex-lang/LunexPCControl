import base64
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

PATH=Path(__file__).resolve().parents[1]/"agent/windows/provision_device_tunnel.py"
spec=importlib.util.spec_from_file_location("tunnel_identity",PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class TunnelIdentityTests(unittest.TestCase):
 def test_key_fingerprint_and_match(self):
  raw=b"ssh host key test"
  encoded=base64.b64encode(raw).decode()
  fp="SHA256:"+base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
  self.assertEqual(mod.fingerprint(encoded),fp)
  self.assertEqual(mod.choose_host_key("192.0.2.1 ssh-rsa "+encoded,"192.0.2.1",fp),"192.0.2.1 ssh-rsa "+encoded+"\n")
  with self.assertRaises(ValueError):
   mod.choose_host_key("192.0.2.1 ssh-rsa "+encoded,"192.0.2.1","SHA256:wrong")
 def test_reject_changed_key(self):
  try:
   import cryptography
  except ImportError:
   self.skipTest("cryptography unavailable")
  with tempfile.TemporaryDirectory() as d:
   base=Path(d)
   folder=base/"ssh"
   export=base/"public"
   key=base64.b64encode(b"host-key").decode()
   fp=mod.fingerprint(key)
   with patch.object(mod.subprocess,"run",return_value=SimpleNamespace(stdout="192.0.2.1 ssh-rsa "+key+"\n")):
    self.assertEqual(mod.provision(folder,export,"192.0.2.1",fp),fp)
    self.assertEqual(mod.provision(folder,export,"192.0.2.1",fp),fp)
    self.assertTrue((folder/"id_ed25519").exists())
    self.assertTrue(export.exists())
    (folder/"known_hosts").write_text("different")
    with self.assertRaises(RuntimeError):
     mod.provision(folder,export,"192.0.2.1",fp)
 def test_ps_acl_and_session(self):
  s=(PATH.parent/"Setup-TunnelIdentity.ps1").read_text()
  self.assertIn("icacls.exe",s)
  self.assertIn("/inheritance:r",s)
  self.assertIn("$session -le 0",s)
  self.assertIn("$env:LOCALAPPDATA",s)
  self.assertIn("$MyInvocation.MyCommand.Path",s)
  self.assertIn("--host-key-file",s)
