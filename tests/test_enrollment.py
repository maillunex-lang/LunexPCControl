import tempfile
import unittest
import sqlite3
from pathlib import Path
from server.enrollment import Registry

class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'registry.db'
        self.registry = Registry(self.path)

    def test_lifecycle(self):
        token = self.registry.enroll('pc1')
        self.assertTrue(self.registry.verify('pc1', token))
        self.assertFalse(self.registry.verify('pc1', 'wrong'))
        self.assertFalse(self.registry.verify('pc2', token))
        self.registry.revoke('pc1')
        self.assertFalse(self.registry.verify('pc1', token))

    def test_duplicate(self):
        self.registry.enroll('pc1')
        with self.assertRaises(sqlite3.IntegrityError):
            self.registry.enroll('pc1')

    def test_invalid(self):
        with self.assertRaises(ValueError):
            self.registry.enroll('../pc')

    def test_no_plaintext(self):
        token = self.registry.enroll('pc1')
        self.assertNotIn(token.encode(), self.path.read_bytes())
