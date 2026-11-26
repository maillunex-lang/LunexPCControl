#!/usr/bin/env python3
"""Bounded encrypted backup + read-only verification of LunexPCControl state.

Data contains secrets. Encryption key must be exported and protected separately.
No raw SQLite copy is ever written to a temporary filesystem location.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import stat
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = "lunexpc-backup-v1"
AAD = MAGIC.encode()
MAX_DB_BYTES = 8 * 1024 * 1024
MAX_BUNDLE_BYTES = 12 * 1024 * 1024
MAX_FILE_BYTES = 16 * 1024 * 1024


def private_file(path, max_size):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("symlink is forbidden")
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise PermissionError("source must be a regular 0600 private file")
    if metadata.st_size > max_size:
        raise ValueError("source file exceeds size limit")
    return path


def generate_key(path):
    output = Path(path)
    if output.is_symlink() or output.exists():
        raise FileExistsError("backup encryption key already exists")
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, secrets.token_bytes(32))
    finally:
        os.close(fd)
    print("Generated private backup key file. Export it separately from the VPS.")


def read_key(path):
    file = private_file(path, 32)
    result = file.read_bytes()
    if len(result) != 32:
        raise ValueError("backup key must be exactly 32 binary bytes")
    return result


def snapshot_sqlite(db_path):
    path = private_file(db_path, MAX_DB_BYTES)
    uri = "file:" + str(path.resolve()) + "?mode=ro"
    source = sqlite3.connect(uri, uri=True, timeout=5)
    target = sqlite3.connect(":memory:")
    try:
        source.backup(target)
        status = target.execute("PRAGMA quick_check").fetchone()
        if status != ("ok",):
            raise ValueError("database quick_check failed")
        blob = target.serialize()
        if len(blob) > MAX_DB_BYTES:
            raise ValueError("snapshot exceeds allowed SQLite size")
        return blob
    finally:
        target.close()
        source.close()


def backup(db_path, panel_key_path, key_path, output):
    key = read_key(key_path)
    registry = snapshot_sqlite(db_path)
    panel_key = b""
    if panel_key_path is not None:
        panel_key = private_file(panel_key_path, 256).read_bytes()
    doc = {
        "format": MAGIC,
        "registry_sha256": hashlib.sha256(registry).hexdigest(),
        "registry": base64.b64encode(registry).decode("ascii"),
        "panel_auth": base64.b64encode(panel_key).decode("ascii"),
    }
    raw = json.dumps(doc, separators=(",", ":")).encode()
    if len(raw) > MAX_BUNDLE_BYTES:
        raise ValueError("snapshot exceeds encrypted backup limit")
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(key).encrypt(nonce, raw, AAD)
    encoded = json.dumps({
        "format": MAGIC, "nonce": base64.b64encode(nonce).decode(),
        "encrypted": base64.b64encode(ciphertext).decode(),
    }, separators=(",", ":")).encode()
    if len(encoded) > MAX_FILE_BYTES:
        raise ValueError("encrypted backup exceeds size limit")
    path = Path(output)
    if path.is_symlink() or path.exists():
        raise FileExistsError("refusing to overwrite existing backup")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, encoded)
        os.fsync(fd)
    finally:
        os.close(fd)
    return len(encoded)


def verify_backup(backup_path, key_path):
    key = read_key(key_path)
    blob = private_file(backup_path, MAX_FILE_BYTES).read_bytes()
    envelope = json.loads(blob)
    if set(envelope) != {"format", "nonce", "encrypted"} or envelope["format"] != MAGIC:
        raise ValueError("unsupported backup envelope")
    nonce = base64.b64decode(envelope["nonce"], validate=True)
    ciphertext = base64.b64decode(envelope["encrypted"], validate=True)
    if len(nonce) != 12:
        raise ValueError("invalid backup nonce")
    raw = AESGCM(key).decrypt(nonce, ciphertext, AAD)
    if len(raw) > MAX_BUNDLE_BYTES:
        raise ValueError("decoded bundle size exceeded")
    content = json.loads(raw)
    if set(content) != {"format","registry_sha256","registry","panel_auth"} or content["format"] != MAGIC:
        raise ValueError("invalid backup content")
    registry = base64.b64decode(content["registry"], validate=True)
    if len(registry) > MAX_DB_BYTES or not registry.startswith(b"SQLite format 3\x00"):
        raise ValueError("invalid SQLite database")
    if hashlib.sha256(registry).hexdigest() != content["registry_sha256"]:
        raise ValueError("registry integrity mismatch")
    # Never write decrypted registry or panel key to disk.
    db = sqlite3.connect(":memory:")
    try:
        db.deserialize(registry)
        if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ValueError("database integrity check failed")
        routes = db.execute("SELECT count(*) FROM routes").fetchone()[0]
        clients = db.execute("SELECT count(*) FROM clients").fetchone()[0]
    finally:
        db.close()
    panel = base64.b64decode(content["panel_auth"], validate=True)
    if len(panel) > 256:
        raise ValueError("invalid panel credential")
    return {"routes": routes, "clients": clients, "encrypted": True,
            "panel_key_included": bool(panel)}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    gen = sub.add_parser("keygen")
    gen.add_argument("--output", type=Path, required=True)
    make = sub.add_parser("create")
    make.add_argument("--registry", type=Path, required=True)
    make.add_argument("--panel-key", type=Path)
    make.add_argument("--key-file", type=Path, required=True)
    make.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--backup", type=Path, required=True)
    verify.add_argument("--key-file", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "keygen":
        generate_key(args.output)
    elif args.action == "create":
        size = backup(args.registry, args.panel_key, args.key_file, args.output)
        print(f"Encrypted backup created: {size} bytes")
    else:
        details = verify_backup(args.backup, args.key_file)
        print("Encrypted backup integrity PASS; routes:", details["routes"],
              "clients:", details["clients"], "panel key:", details["panel_key_included"])


if __name__ == "__main__":
    main()
