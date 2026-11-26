import hashlib,json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from installer import upgrade


class UpgradeTests(unittest.TestCase):
 def test_plan_requires_pinned_clean_checkout(self):
  with patch.object(upgrade,"git_read",side_effect=["a"*40,""]):
   with patch.object(upgrade,"REPO_ROOT",Path(__file__).resolve().parents[1]):
    upgrade.verify_checkout("a"*40)
  with self.assertRaises(ValueError):upgrade.verify_checkout("main")
  with patch.object(upgrade,"git_read",side_effect=["b"*40]):
   with self.assertRaises(ValueError):upgrade.verify_checkout("a"*40)

 def test_stage_and_verify_hashes(self):
  with tempfile.TemporaryDirectory() as d:
   with patch.object(upgrade,"verify_checkout"):
    with patch.object(upgrade.os,"geteuid",return_value=0):
     p=upgrade.stage("c"*40,Path(d)/"updates")
     self.assertEqual(upgrade.check_stage(p),{
        "revision":"c"*40,"files":len(upgrade.FILES)})
     with self.assertRaises(FileExistsError):
      upgrade.stage("c"*40,Path(d)/"updates")
     sample=p/"panel/server.py"
     sample.write_text("tampered")
     with self.assertRaisesRegex(ValueError,"integrity mismatch"):
      upgrade.check_stage(p)

 def test_no_service_mutation(self):
  source=(Path(__file__).resolve().parents[1]/"installer/upgrade.py").read_text()
  for forbidden in ("systemctl restart", "systemctl stop", "os.system(",
                    "ssh_exec", "nginx -s", "ufw "):
   self.assertNotIn(forbidden,source)
