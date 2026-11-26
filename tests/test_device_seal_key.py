import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
P=Path(__file__).resolve().parents[1]/'agent/windows/Device-SealKey.py'
spec=importlib.util.spec_from_file_location('device_seal_key',P)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class DeviceSealKeyTests(unittest.TestCase):
 def test_create_reuse_and_mismatch(self):
  with tempfile.TemporaryDirectory() as t:
   folder=Path(t)/'secret';export=Path(t)/'public'
   mod.create(folder,export)
   first=export.read_bytes()
   mod.create(folder,export)
   self.assertEqual(export.read_bytes(),first)
   export.write_bytes(b'incorrect')
   with self.assertRaises(RuntimeError):mod.create(folder,export)
 def test_partial_key_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   folder=Path(t)/'secret';folder.mkdir()
   (folder/'seal-private.pem').write_text('incomplete')
   with self.assertRaises(RuntimeError):mod.create(folder,Path(t)/'public')
