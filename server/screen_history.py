"""Encrypted, bounded and optional archival of MCP screenshot responses.

A screenshot is recorded only when a completed, authenticated Screenshot
tools/call succeeded. It is NEVER returned through an unauthenticated route.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import threading
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PNG_BYTES = 5 * 1024 * 1024
MAX_RESPONSE_SCAN = 15 * 1024 * 1024
RECORD_CAP = 50
MAX_STORED_BYTES = 64 * 1024 * 1024
ALLOWED_RETENTION_HOURS = {0, 1, 24, 168}
AAD = b"lunexpc-screenshot-v1"


def _regular_private(path, size=None):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("symlink forbidden")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
        raise PermissionError("private regular file required")
    if size is not None and info.st_size != size:
        raise ValueError("wrong key length")
    return path


def _new_private(path, content):
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise FileExistsError("refusing to overwrite private file")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, content)
        os.fsync(fd)
    finally:
        os.close(fd)


def extract_pngs(body):
    """Find only PNG image contents, reject oversized and malformed payloads."""
    if not isinstance(body, bytes) or len(body) > MAX_RESPONSE_SCAN:
        return []
    try:
        doc = json.loads(body)
    except (ValueError, UnicodeDecodeError, TypeError):
        return []
    if not isinstance(doc, dict):
        return []
    result = doc.get("result")
    if not isinstance(result, dict) or result.get("isError"):
        return []
    content = result.get("content", [])
    if not isinstance(content, list):
        return []
    images = []
    for item in content[:10]:
        if not isinstance(item, dict) or item.get("type") != "image":
            continue
        if item.get("mimeType") != "image/png" or not isinstance(item.get("data"), str):
            continue
        encoded = item["data"]
        if len(encoded) > (MAX_PNG_BYTES * 4 // 3 + 16):
            continue
        try:
            png = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            continue
        if not (PNG_SIGNATURE == png[:8] and
                len(png) <= MAX_PNG_BYTES and
                len(png) >= 24 and
                png[12:16] == b"IHDR" and
                png[-12:-8] == b"\x00\x00\x00\x00" and
                png[-8:-4] == b"IEND"):
            continue
        images.append(png)
    return images


class ScreenHistory:
    """Private SQLite metadata + encrypted PNGs; no raw screenshot file."""
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.folder.is_symlink() or stat.S_IMODE(self.folder.stat().st_mode) != 0o700:
            raise PermissionError("screenshot storage must be private 0700")
        self.lock = threading.RLock()
        self.db_path = self.folder / "history.sqlite"
        self.key_path = self.folder / "history.key"
        if not self.key_path.exists():
            try:
                _new_private(self.key_path, secrets.token_bytes(32))
            except FileExistsError:
                # Panel and gateway may start simultaneously. Reuse the
                # existing private key rather than overwriting it.
                pass
        self.key = _regular_private(self.key_path, 32).read_bytes()
        if not self.db_path.exists():
            flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                fd = os.open(self.db_path, flags, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(fd)
        self._require_private(self.db_path)
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS images(
                id TEXT PRIMARY KEY, device TEXT NOT NULL, utc TEXT NOT NULL,
                created REAL NOT NULL, bytes INTEGER NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS config(
                name TEXT PRIMARY KEY, value INTEGER NOT NULL)""")
            db.execute("INSERT OR IGNORE INTO config(name,value) VALUES('retention_hours',0)")
            db.execute("INSERT OR IGNORE INTO config(name,value) VALUES('max_count',50)")
        self._require_private(self.db_path)

    @staticmethod
    def _require_private(path):
        if path.exists():
            file = _regular_private(path)
            return file
        return None

    def _db(self):
        self._require_private(self.db_path)
        return sqlite3.connect(self.db_path, timeout=5)

    def settings(self):
        with self._db() as db:
            config = dict(db.execute("SELECT name,value FROM config").fetchall())
        return {"retention_hours": config["retention_hours"],
                "max_count": config["max_count"],
                "enabled": config["retention_hours"] != 0}

    def configure(self, hours, max_count=None):
        if type(hours) is not int or hours not in ALLOWED_RETENTION_HOURS:
            raise ValueError("invalid retention setting")
        if max_count is not None and (type(max_count) is not int or max_count not in (1,50)):
            raise ValueError("invalid history count")
        with self.lock, self._db() as db:
            db.execute("UPDATE config SET value=? WHERE name='retention_hours'",(hours,))
            if max_count is not None:
                db.execute("UPDATE config SET value=? WHERE name='max_count'",(max_count,))
        self.prune()
        return self.settings()

    def capture(self, device, response):
        if not isinstance(device, str) or not re.fullmatch("[A-Za-z0-9_-]{1,64}",device):
            return 0
        with self.lock:
            setting = self.settings()
            if not setting["enabled"]:
                return 0
            count = 0
            for png in extract_pngs(response):
                identifier = secrets.token_hex(16)
                filename = self.folder / (identifier + ".enc")
                # Nonce is stored inline but the key stays in a private file.
                nonce = secrets.token_bytes(12)
                encrypted = nonce + AESGCM(self.key).encrypt(nonce, png, AAD)
                _new_private(filename,encrypted)
                with self._db() as db:
                    db.execute("INSERT INTO images(id,device,utc,created,bytes) VALUES(?,?,?,?,?)",
                               (identifier,device,datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                time.time(),len(png)))
                count += 1
            self.prune()
            return count

    def prune(self):
        with self.lock, self._db() as db:
            conf = self.settings()
            rows = db.execute("SELECT id,created,bytes FROM images ORDER BY created DESC,id DESC").fetchall()
            expire_before = time.time() - conf["retention_hours"] * 3600
            total = 0
            stale = []
            for idx, (image_id, created, size) in enumerate(rows):
                total += size
                if (not conf["enabled"] or created < expire_before
                    or idx >= conf["max_count"] or total > MAX_STORED_BYTES):
                    stale.append(image_id)
            for identifier in stale:
                file = self.folder / (identifier+".enc")
                if file.is_file() and not file.is_symlink():
                    file.unlink()
                db.execute("DELETE FROM images WHERE id=?",(identifier,))

    def clear(self):
        with self.lock, self._db() as db:
            rows=db.execute("SELECT id FROM images").fetchall()
            for (identifier,) in rows:
                file=self.folder/(identifier+".enc")
                if file.is_file() and not file.is_symlink():
                    file.unlink()
                db.execute("DELETE FROM images WHERE id=?",(identifier,))
        return True

    def list(self):
        self.prune()
        with self._db() as db:
            rows=db.execute("SELECT id,device,utc,bytes FROM images ORDER BY created DESC,id DESC LIMIT 50").fetchall()
        return [{"id":i,"device":d,"time":t,"bytes":s} for i,d,t,s in rows]

    def image(self, identifier):
        self.prune()
        if not isinstance(identifier,str) or not re.fullmatch(r"[0-9a-f]{32}",identifier):
            return None
        with self.lock, self._db() as db:
            if not db.execute("SELECT 1 FROM images WHERE id=?",(identifier,)).fetchone():
                return None
            filename = self.folder / (identifier+".enc")
            if not filename.is_file() or filename.is_symlink():
                return None
            encrypted = _regular_private(filename).read_bytes()
            if len(encrypted)<28 or len(encrypted)>MAX_PNG_BYTES+64:
                return None
            return AESGCM(self.key).decrypt(encrypted[:12],encrypted[12:],AAD)
