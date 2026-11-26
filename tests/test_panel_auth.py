import os
import base64
from pathlib import Path
import tempfile
import unittest
from panel.auth import PanelAuth


class PanelAuthTests(unittest.TestCase):
    def test_unconfigured_auth_fails_closed(self):
        self.assertFalse(PanelAuth().verify(None))
        self.assertFalse(PanelAuth().verify("Basic YWRtaW46dGVzdA=="))

    def test_protected_secret_and_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'auth.key'
            p.write_text('not-a-real-secret-token-of-sufficient-length')
            p.chmod(0o600)
            verifier=PanelAuth(p)
            valid=base64.b64encode(b'admin:not-a-real-secret-token-of-sufficient-length').decode()
            wrong_user=base64.b64encode(b'guest:not-a-real-secret-token-of-sufficient-length').decode()
            self.assertTrue(verifier.verify('Basic '+valid))
            self.assertFalse(verifier.verify('Basic '+wrong_user))
            self.assertFalse(verifier.verify('Bearer not-a-real-secret-token-of-sufficient-length'))
            self.assertFalse(verifier.verify('basic '+valid))
            self.assertFalse(verifier.verify('not-a-real-secret-token-of-sufficient-length'))
            self.assertFalse(verifier.verify('Basic ' + 'a'*400))
            p.chmod(0o644)
            with self.assertRaises(PermissionError):PanelAuth(p)
            p.chmod(0o600)
            link=Path(d)/'link.key'
            link.symlink_to(p)
            with self.assertRaises(PermissionError):PanelAuth(link)

    def test_broken_configuration_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            missing=Path(d)/'missing.key'
            with self.assertRaises(FileNotFoundError):PanelAuth(missing)
            p=Path(d)/'short.key';p.write_text('tiny');p.chmod(0o600)
            with self.assertRaises(ValueError):PanelAuth(p)
