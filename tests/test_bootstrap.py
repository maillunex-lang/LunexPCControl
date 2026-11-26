from pathlib import Path
import unittest
SRC = (Path(__file__).resolve().parents[1] / 'installer/bootstrap.sh').read_text()
class BootstrapTests(unittest.TestCase):
    def test_pin(self):
        for value in ('FULL_40_CHARACTER_COMMIT_SHA', 'checkout --quiet --detach "$REF"',
                      'rev-parse HEAD', '"$FOUND" != "$REF"', '--apply'):
            self.assertIn(value, SRC)
    def test_no_unrelated_modifications(self):
        for value in ("ufw ", "nginx -s", "systemctl restart", "systemctl enable",
                      "apt-get remove", "git push"):
            self.assertNotIn(value, SRC)
