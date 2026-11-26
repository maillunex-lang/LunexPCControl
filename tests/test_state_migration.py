"""Migration archives stay encrypted, are tightly allowlisted, and stage only."""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from installer.backup import generate_key, read_key
from installer.migration import AAD, FORMAT, create, verify, stage, inventory


def private(root, path, contents):
    dest = root / path
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest.write_bytes(contents)
    dest.chmod(0o600)
    return dest


def sqlite_private(root, path, statements):
    dest = root / path
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sqlite3.connect(dest) as db:
        db.executescript(statements)
    dest.chmod(0o600)
    return dest


class StateMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lunexpc-state-v2-")
        base = Path(self.tmp.name)
        self.source = base / "input"
        self.source.mkdir()
        self.key = base / "encryption.key"
        generate_key(self.key)
        self.archive = base / "export.enc"
        self.restored = base / "restored"

    def tearDown(self):
        self.tmp.cleanup()

    def data(self):
        sqlite_private(self.source, "var/lib/lunexpc-gateway/registry.sqlite", """
            CREATE TABLE routes(device TEXT, port INTEGER, upstream_key TEXT);
            CREATE TABLE clients(device TEXT, token_digest TEXT, allowed INTEGER);
            INSERT INTO routes VALUES('test-pc', 23789, 'never-upload-upstream-secret');
            INSERT INTO clients VALUES('test-pc','client-secret',1);
        """)
        private(self.source, "var/lib/lunexpc-gateway/panel-auth.key", b"very-private-panel-password")
        sqlite_private(self.source, "var/lib/lunexpc-gateway/connectors/registry.sqlite", """
            CREATE TABLE devices(id TEXT,name TEXT);
            INSERT INTO devices VALUES('abc','Lunex VPS');
        """)
        sqlite_private(self.source, "var/lib/lunexpc-gateway/screens/history.sqlite", """
            CREATE TABLE pictures(id TEXT PRIMARY KEY);
        """)
        private(self.source, "var/lib/lunexpc-gateway/screens/history.key", b"K"*32)
        private(self.source, "var/lib/lunexpc-gateway/screens/"+"a"*32+".enc",
                b"encrypted-screen-payload-not-a-plain-picture")
        private(self.source, "var/lib/lunexpc-gateway/lunex-test-client.key", b"private-mcp-client-key")
        private(self.source, "etc/lunexpc-gateway/backup.key", b"B"*32)
        private(self.source, "var/lib/lunexpc-agent/LunexPCControl/connector.json",
                b'{"private_key":"extremely-private-device-signing-key"}')
        private(self.source, "var/lib/lunexpc-tunnel/.ssh/authorized_keys",
                b'restrict,permitlisten="127.0.0.1:23789" ssh-ed25519 public-key')
        return self

    def test_encrypted_complete_snapshot_verify_and_stage(self):
        self.data()
        result=create(self.source,self.key,self.archive)
        self.assertGreaterEqual(result["files"],10)
        encrypted=self.archive.read_bytes()
        for marker in (b"very-private-panel-password",b"never-upload-upstream-secret",
                       b"private-mcp-client-key",b"extremely-private-device-signing-key"):
            self.assertNotIn(marker, encrypted)
        self.assertEqual(self.archive.stat().st_mode&0o777,0o600)
        info=verify(self.archive,self.key)
        self.assertTrue(info["has_connector"])
        self.assertTrue(info["has_screens"])
        staged=stage(self.archive,self.key,self.restored)
        self.assertEqual(staged["files"],result["files"])
        self.assertTrue(staged["staged_only"])
        self.assertEqual(self.restored.stat().st_mode&0o777,0o700)
        self.assertEqual((self.restored/"var/lib/lunexpc-gateway/panel-auth.key").read_bytes(),
                         b"very-private-panel-password")
        self.assertEqual((self.restored/"var/lib/lunexpc-agent/LunexPCControl/connector.json").stat().st_mode&0o777,
                         0o600)
        with sqlite3.connect(self.restored/"var/lib/lunexpc-gateway/registry.sqlite") as db:
            self.assertEqual(db.execute("SELECT upstream_key FROM routes").fetchone()[0],
                             "never-upload-upstream-secret")
        with self.assertRaises(FileExistsError):
            stage(self.archive,self.key,self.restored)
        with self.assertRaises(FileExistsError):
            create(self.source,self.key,self.archive)

    def test_modified_archive_is_rejected(self):
        self.data()
        create(self.source,self.key,self.archive)
        data=json.loads(self.archive.read_bytes())
        data["ciphertext"]=base64.b64encode(b"tampered").decode("ascii")
        self.archive.write_text(json.dumps(data))
        with self.assertRaises((ValueError,Exception)):
            verify(self.archive,self.key)
        self.assertFalse(self.restored.exists())

    def test_missing_required_or_symlink_source_is_rejected(self):
        self.data()
        (self.source/"var/lib/lunexpc-gateway/panel-auth.key").unlink()
        with self.assertRaises(FileNotFoundError):
            create(self.source,self.key,self.archive)
        panel=self.source/"var/lib/lunexpc-gateway/panel-auth.key"
        panel.symlink_to(self.key)
        with self.assertRaises(ValueError):
            create(self.source,self.key,self.archive)
        self.assertFalse(self.archive.exists())

    def test_unknown_path_in_encrypted_payload_never_escapes(self):
        self.data()
        doc={"format": FORMAT,"created":1,"files":[]}
        for path in ("var/lib/lunexpc-gateway/registry.sqlite",
                     "var/lib/lunexpc-gateway/panel-auth.key",
                     "../../root/.ssh/authorized_keys"):
            blob=b"fake"
            doc["files"].append({"path":path,"sha256":hashlib.sha256(blob).hexdigest(),
                                 "data":base64.b64encode(blob).decode()})
        nonce=os.urandom(12)
        cipher=AESGCM(read_key(self.key)).encrypt(nonce,json.dumps(doc).encode(),AAD)
        self.archive.write_text(json.dumps({"format":FORMAT,
            "nonce":base64.b64encode(nonce).decode(),
            "ciphertext":base64.b64encode(cipher).decode()}))
        self.archive.chmod(0o600)
        with self.assertRaises(ValueError):
            stage(self.archive,self.key,self.restored)
        self.assertFalse(self.restored.exists())

    def test_inventory_is_only_explicit_allowlist(self):
        self.data()
        private(self.source,"var/lib/lunexpc-gateway/private-not-in-allowlist.txt",b"do not touch")
        items=inventory(self.source)
        self.assertNotIn("var/lib/lunexpc-gateway/private-not-in-allowlist.txt",items)
        self.assertIn("var/lib/lunexpc-gateway/panel-auth.key",items)


if __name__=="__main__":
    unittest.main()
