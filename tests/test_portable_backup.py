import sqlite3
from pathlib import Path
import tempfile
import unittest
from cryptography.exceptions import InvalidTag
from installer.backup import backup, generate_key, verify_backup

class PortableBackupTests(unittest.TestCase):
    def test_encrypt_verify_and_detect_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            key=root/"key"
            generate_key(key)
            self.assertEqual(key.stat().st_mode&0o777,0o600)
            db=root/"db.sqlite"
            with sqlite3.connect(db) as conn:
                conn.executescript("""
                    CREATE TABLE routes(device TEXT PRIMARY KEY,port INTEGER,upstream_key TEXT);
                    CREATE TABLE clients(device TEXT,token_digest TEXT,allowed INTEGER);
                    INSERT INTO routes VALUES('pc',23789,'very-secret-agent-key');
                    INSERT INTO clients VALUES('pc','sensitive-client-hash',1);
                """)
            db.chmod(0o600)
            panel=root/"panel.key";panel.write_text("another-secret-not-public");panel.chmod(0o600)
            dest=root/"backup.enc"
            self.assertGreater(backup(db,panel,key,dest),100)
            content=dest.read_bytes()
            self.assertNotIn(b"very-secret-agent-key",content)
            self.assertNotIn(b"another-secret-not-public",content)
            self.assertEqual(dest.stat().st_mode&0o777,0o600)
            self.assertEqual(verify_backup(dest,key),{
                "routes":1,"clients":1,"encrypted":True,"panel_key_included":True})
            with self.assertRaises(FileExistsError):
                backup(db,panel,key,dest)
            dest.write_bytes(content.replace(b'"format"',b'"f0rmat"',1))
            with self.assertRaises(ValueError):
                verify_backup(dest,key)
    def test_reject_nonprivate_database(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);key=root/"key";generate_key(key)
            db=root/"db";db.write_bytes(b"not SQLite");db.chmod(0o644)
            with self.assertRaises(PermissionError):
                backup(db,None,key,root/"out")
