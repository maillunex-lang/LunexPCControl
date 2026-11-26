"""Owner-approved one-time pairing and Ed25519-signed connector heartbeats.

Separate from the privileged MCP/SSH route registry. Pairing grants only
presence/telemetry registration, never mouse, shell, SSH or MCP access.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ID_RE = re.compile(r"[0-9a-f]{32}\Z")
CODE_RE = re.compile(r"[A-Za-z0-9_-]{40,90}\Z")
NAME_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9 _.-]{1,48}\Z")
NONCE_RE = re.compile(r"[A-Za-z0-9_-]{16,90}\Z")
OS_NAMES = frozenset({"windows", "linux"})
TTL_SECONDS = 600
MAX_CLOCK_SKEW = 90
MAX_DEVICES = 50
MAX_INVITATIONS = 10


class PairingError(ValueError):
    pass


def _decode_key(value):
    if not isinstance(value, str) or not 30 <= len(value) <= 100:
        raise PairingError("invalid public key")
    try:
        result = base64.b64decode(value, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise PairingError("invalid public key") from exc
    if len(result) != 32:
        raise PairingError("invalid public key")
    try:
        Ed25519PublicKey.from_public_bytes(result)
    except ValueError as exc:
        raise PairingError("invalid public key") from exc
    return result


def signature_payload(device_id: str, stamp: int, nonce: str) -> bytes:
    if not isinstance(device_id, str) or not ID_RE.fullmatch(device_id):
        raise PairingError("invalid device ID")
    if type(stamp) is not int or stamp < 0:
        raise PairingError("invalid timestamp")
    if not isinstance(nonce, str) or not NONCE_RE.fullmatch(nonce):
        raise PairingError("invalid nonce")
    return f"LUNEXPC-PRESENCE-v1\n{device_id}\n{stamp}\n{nonce}\n".encode("ascii")


class ConnectorRegistry:
    def __init__(self, path, *, clock=None):
        self.path = str(path)
        self.clock = clock or time.time
        if self.path != ":memory:":
            item = Path(self.path)
            if item.is_symlink() or (item.exists() and not stat.S_ISREG(item.stat().st_mode)):
                raise PermissionError("connector database must be regular, never symlinked")
            if item.exists() and stat.S_IMODE(item.stat().st_mode) & 0o077:
                raise PermissionError("connector database must be private")
            old = os.umask(0o077)
        else:
            old = None
        try:
            with self._connect() as db:
                db.execute("CREATE TABLE IF NOT EXISTS invitations (digest TEXT PRIMARY KEY, os TEXT NOT NULL, label TEXT NOT NULL, expires INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0)")
                db.execute("CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY, os TEXT NOT NULL, label TEXT NOT NULL, public_key BLOB NOT NULL UNIQUE, paired INTEGER NOT NULL, last_seen INTEGER, revoked INTEGER NOT NULL DEFAULT 0)")
                db.execute("CREATE TABLE IF NOT EXISTS presence_nonces (device_id TEXT NOT NULL, nonce TEXT NOT NULL, expires INTEGER NOT NULL, PRIMARY KEY(device_id,nonce))")
        finally:
            if old is not None:
                os.umask(old)
        if self.path != ":memory:" and stat.S_IMODE(os.stat(self.path).st_mode) & 0o077:
            raise PermissionError("connector database permissions invalid")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def invite(self, os_name, label):
        if os_name not in OS_NAMES:
            raise PairingError("unsupported operating system")
        if (not isinstance(label, str) or not NAME_RE.fullmatch(label)
                or len(label.encode("utf-8"))>128):
            raise PairingError("invalid device name")
        code = secrets.token_urlsafe(32)
        now = int(self.clock())
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM invitations WHERE expires <= ? OR used=1", (now,))
            if db.execute("SELECT count(*) FROM invitations").fetchone()[0] >= MAX_INVITATIONS:
                raise PairingError("too many pending invitations")
            if db.execute("SELECT count(*) FROM devices WHERE revoked=0").fetchone()[0] >= MAX_DEVICES:
                raise PairingError("device limit reached")
            db.execute("INSERT INTO invitations (digest,os,label,expires) VALUES (?,?,?,?)",
                       (hashlib.sha256(code.encode()).hexdigest(), os_name, label, now+TTL_SECONDS))
        return {"pairing_code": code, "expires_in_seconds": TTL_SECONDS, "os": os_name, "name": label}

    def claim(self, pairing_code, os_name, public_key):
        if not isinstance(pairing_code, str) or not CODE_RE.fullmatch(pairing_code):
            raise PairingError("invalid pairing code")
        if os_name not in OS_NAMES:
            raise PairingError("unsupported operating system")
        key = _decode_key(public_key)
        digest = hashlib.sha256(pairing_code.encode()).hexdigest()
        now = int(self.clock())
        device_id = secrets.token_hex(16)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            invitation = db.execute("SELECT os,label,expires,used FROM invitations WHERE digest=?",(digest,)).fetchone()
            if not invitation or invitation[0] != os_name or invitation[2] <= now or invitation[3] != 0:
                raise PairingError("invitation invalid or expired")
            if db.execute("SELECT count(*) FROM devices WHERE revoked=0").fetchone()[0] >= MAX_DEVICES:
                raise PairingError("device limit reached")
            try:
                db.execute("INSERT INTO devices (id,os,label,public_key,paired) VALUES (?,?,?,?,?)",
                           (device_id, os_name, invitation[1], key, now))
            except sqlite3.IntegrityError as exc:
                raise PairingError("public key already registered") from exc
            db.execute("UPDATE invitations SET used=1 WHERE digest=?",(digest,))
        return {"device_id": device_id, "name": invitation[1], "os": os_name}

    def heartbeat(self, device_id, stamp, nonce, signature):
        payload = signature_payload(device_id, stamp, nonce)
        now = int(self.clock())
        if abs(now - stamp) > MAX_CLOCK_SKEW:
            raise PairingError("stale heartbeat")
        if not isinstance(signature, str) or not 80 <= len(signature) <= 100:
            raise PairingError("invalid signature")
        try:
            binary = base64.b64decode(signature, altchars=b"-_", validate=True)
        except Exception as exc:
            raise PairingError("invalid signature") from exc
        if len(binary) != 64:
            raise PairingError("invalid signature")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT public_key,revoked FROM devices WHERE id=?",(device_id,)).fetchone()
            if row is None or row[1]:
                raise PairingError("unknown or revoked device")
            try:
                Ed25519PublicKey.from_public_bytes(row[0]).verify(binary, payload)
            except InvalidSignature as exc:
                raise PairingError("invalid signature") from exc
            db.execute("DELETE FROM presence_nonces WHERE expires <= ?",(now,))
            try:
                db.execute("INSERT INTO presence_nonces (device_id,nonce,expires) VALUES (?,?,?)",
                           (device_id,nonce,max(now,stamp)+MAX_CLOCK_SKEW+1))
            except sqlite3.IntegrityError as exc:
                raise PairingError("replayed heartbeat") from exc
            db.execute("UPDATE devices SET last_seen=? WHERE id=?",(now,device_id))
        return {"online": True}

    def list_devices(self):
        now=int(self.clock())
        with self._connect() as db:
            rows=db.execute("SELECT id,os,label,paired,last_seen FROM devices WHERE revoked=0 ORDER BY paired DESC LIMIT ?",(MAX_DEVICES,)).fetchall()
        return [{"id":x[0],"os":x[1],"name":x[2],"paired_at":x[3],"last_seen":x[4],
                 "online":bool(x[4] is not None and now-x[4] < 90)} for x in rows]

    def revoke(self, device_id):
        if not isinstance(device_id,str) or not ID_RE.fullmatch(device_id):
            raise PairingError("invalid device ID")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            found = db.execute("UPDATE devices SET revoked=1 WHERE id=? AND revoked=0",(device_id,)).rowcount
            db.execute("DELETE FROM presence_nonces WHERE device_id=?",(device_id,))
        if found != 1:
            raise PairingError("unknown device")
        return {"revoked": True}
