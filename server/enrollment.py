"""Local device credential registry; never stores plaintext tokens."""
import hashlib
import hmac
import secrets
import sqlite3
import re

class Registry:
    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY, digest TEXT NOT NULL)')

    def enroll(self, device):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', device):
            raise ValueError('invalid device ID')
        token = secrets.token_urlsafe(32)
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO devices VALUES (?, ?)', (device, self.digest(token)))
        return token

    @staticmethod
    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def verify(self, device, token):
        with sqlite3.connect(self.path) as db:
            row = db.execute('SELECT digest FROM devices WHERE id=?', (device,)).fetchone()
        return bool(row and hmac.compare_digest(row[0], self.digest(token)))

    def revoke(self, device):
        with sqlite3.connect(self.path) as db:
            db.execute('DELETE FROM devices WHERE id=?', (device,))
