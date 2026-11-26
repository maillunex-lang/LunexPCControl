#!/usr/bin/env python3
"""Encrypted, explicit state migration with read-only verification and staging.

Does NOT overwrite /var/lib, systemd, nginx, SSH, or installed programs.
A staged restore must be reviewed and activated manually on the new VPS.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from installer.backup import private_file, read_key, snapshot_sqlite

FORMAT = "lunexpc-state-migration-v2"
AAD = FORMAT.encode("ascii")
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_SCREEN_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 80 * 1024 * 1024
MAX_ARCHIVE_BYTES = 115 * 1024 * 1024
MAX_JSON_BYTES = 96 * 1024 * 1024

REQUIRED = frozenset({
    "var/lib/lunexpc-gateway/registry.sqlite",
    "var/lib/lunexpc-gateway/panel-auth.key",
})
OPTIONAL = frozenset({
    "var/lib/lunexpc-gateway/connectors/registry.sqlite",
    "var/lib/lunexpc-gateway/screens/history.sqlite",
    "var/lib/lunexpc-gateway/screens/history.key",
    "var/lib/lunexpc-agent/LunexPCControl/connector.json",
    "var/lib/lunexpc-gateway/oauth/issuer.sqlite",
    "var/lib/lunexpc-gateway/oauth/proxy.key",
    "var/lib/lunexpc-tunnel/.ssh/authorized_keys",
    "etc/lunexpc-gateway/backup.key",
})
SCREEN = re.compile(r"var/lib/lunexpc-gateway/screens/[0-9a-f]{32}\.enc\Z")
OTHER_KEY = re.compile(r"var/lib/lunexpc-gateway/[A-Za-z0-9_.-]{1,64}\.key\Z")
MAX_SINGLE = 8 * 1024 * 1024


def allowed(name: str) -> bool:
    if not isinstance(name, str) or not name.isascii():
        return False
    return name in REQUIRED or name in OPTIONAL or SCREEN.fullmatch(name) is not None or (
        OTHER_KEY.fullmatch(name) is not None and
        name != "var/lib/lunexpc-gateway/panel-auth.key")


def _private_source(root: Path, name: str, max_size: int):
    if not allowed(name):
        raise ValueError("unknown state file")
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("invalid path")
    candidate = root
    for segment in relative.parts:
        candidate = candidate / segment
        if candidate.is_symlink():
            raise ValueError("symlinks forbidden in migration inputs")
    return private_file(candidate, max_size)


def inventory(root: Path):
    paths = set(REQUIRED)
    for name in OPTIONAL:
        if (root / name).exists() or (root / name).is_symlink():
            paths.add(name)
    screens = root / "var/lib/lunexpc-gateway/screens"
    if screens.is_dir() and not screens.is_symlink():
        for item in screens.iterdir():
            name = "var/lib/lunexpc-gateway/screens/" + item.name
            if item.name.endswith(".enc"):
                if not SCREEN.fullmatch(name):
                    raise ValueError("unexpected screen history filename")
                paths.add(name)
    keys = root / "var/lib/lunexpc-gateway"
    if keys.is_dir() and not keys.is_symlink():
        for item in keys.iterdir():
            name = "var/lib/lunexpc-gateway/" + item.name
            if item.name.endswith(".key") and OTHER_KEY.fullmatch(name):
                paths.add(name)
    return sorted(paths)


def _read_files(root: Path):
    parts = []
    total = 0
    screenshot_total = 0
    for name in inventory(root):
        limit = MAX_IMAGE_BYTES if SCREEN.fullmatch(name) else MAX_SINGLE
        file = _private_source(root, name, limit)
        if name.endswith(".sqlite"):
            blob = snapshot_sqlite(file)
        else:
            blob = file.read_bytes()
        total += len(blob)
        if SCREEN.fullmatch(name):
            screenshot_total += len(blob)
        if total > MAX_TOTAL_BYTES or screenshot_total > MAX_SCREEN_BYTES:
            raise ValueError("state exceeds encrypted migration limits")
        parts.append((name, blob))
    if not REQUIRED.issubset({name for name, _ in parts}):
        raise ValueError("required state missing")
    return parts


def _bundle_data(contents):
    if type(contents) is not list or not contents or len(contents) > 2000:
        raise ValueError("invalid file inventory")
    result = []
    names = set()
    total = 0
    screenshots = 0
    for part in contents:
        if type(part) is not dict or set(part) != {"path", "sha256", "data"}:
            raise ValueError("invalid state entry")
        name = part["path"]
        if not allowed(name) or name in names:
            raise ValueError("unknown or duplicate state path")
        names.add(name)
        if not isinstance(part["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", part["sha256"]):
            raise ValueError("invalid digest")
        try:
            blob = base64.b64decode(part["data"], validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid encoded state") from exc
        if hashlib.sha256(blob).hexdigest() != part["sha256"]:
            raise ValueError("state integrity mismatch")
        if len(blob) > (MAX_IMAGE_BYTES if SCREEN.fullmatch(name) else MAX_SINGLE):
            raise ValueError("file too large")
        total += len(blob)
        if SCREEN.fullmatch(name):
            screenshots += len(blob)
        if total > MAX_TOTAL_BYTES or screenshots > MAX_SCREEN_BYTES:
            raise ValueError("decoded state exceeds size cap")
        if name.endswith(".sqlite"):
            if not blob.startswith(b"SQLite format 3\x00"):
                raise ValueError("invalid SQLite state")
            db = sqlite3.connect(":memory:")
            try:
                db.deserialize(blob)
                if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                    raise ValueError("invalid SQLite state")
            finally:
                db.close()
        result.append((name, blob))
    if not REQUIRED.issubset(names):
        raise ValueError("required migration file missing")
    return result


def _decrypt(archive, key_file):
    encrypted = private_file(archive, MAX_ARCHIVE_BYTES).read_bytes()
    envelope = json.loads(encrypted)
    if type(envelope) is not dict or set(envelope) != {"format", "nonce", "ciphertext"} or envelope["format"] != FORMAT:
        raise ValueError("unsupported migration archive")
    nonce = base64.b64decode(envelope["nonce"], validate=True)
    payload = base64.b64decode(envelope["ciphertext"], validate=True)
    if len(nonce) != 12 or len(payload) > MAX_ARCHIVE_BYTES:
        raise ValueError("invalid encryption envelope")
    decrypted = AESGCM(read_key(key_file)).decrypt(nonce, payload, AAD)
    if len(decrypted) > MAX_JSON_BYTES:
        raise ValueError("migration exceeds size limit")
    document = json.loads(decrypted)
    if type(document) is not dict or set(document) != {"format", "files", "created"} or document["format"] != FORMAT:
        raise ValueError("invalid migration manifest")
    return _bundle_data(document["files"])


def create(source_root, key_file, destination):
    source_root = Path(source_root)
    if source_root.is_symlink() or not source_root.is_dir():
        raise ValueError("source root must be a real directory")
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("refusing to overwrite encrypted backup")
    files = _read_files(source_root)
    document = json.dumps({"format": FORMAT, "created": int(time.time()),
                           "files": [{"path": name,
                                      "sha256": hashlib.sha256(blob).hexdigest(),
                                      "data": base64.b64encode(blob).decode("ascii")}
                                     for name, blob in files]},
                          separators=(",", ":")).encode()
    if len(document) > MAX_JSON_BYTES:
        raise ValueError("migration manifest exceeds limit")
    nonce = secrets.token_bytes(12)
    cipher = AESGCM(read_key(key_file)).encrypt(nonce, document, AAD)
    result = json.dumps({"format": FORMAT, "nonce": base64.b64encode(nonce).decode(),
                         "ciphertext": base64.b64encode(cipher).decode()},
                        separators=(",", ":")).encode()
    if len(result) > MAX_ARCHIVE_BYTES:
        raise ValueError("encrypted archive exceeds limit")
    if destination.parent.is_symlink() or not destination.parent.is_dir():
        raise ValueError("backup parent directory must exist")
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(result)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        # Archive is unusable if writing failed; never hide the error.
        raise
    return {"files": len(files), "encrypted": True, "bytes": len(result)}


def verify(archive, key_file):
    parts = _decrypt(archive, key_file)
    return {"files": len(parts), "encrypted": True,
            "has_connector": any(name.startswith("var/lib/lunexpc-agent/") for name, _ in parts),
            "has_screens": any(name.startswith("var/lib/lunexpc-gateway/screens/") for name, _ in parts)}


def stage(archive, key_file, output):
    """Decrypt into a NEW private offline directory, never production paths."""
    files = _decrypt(archive, key_file)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("restore destination must be new")
    output.mkdir(mode=0o700)
    try:
        for relative, blob in files:
            target = output / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as file:
                file.write(blob)
                file.flush()
                os.fsync(file.fileno())
    except BaseException:
        # Never delete a partially staged directory; it may hold private
        # material. Operator must inspect and safely remove it.
        raise
    return {"files": len(files), "staged_only": True, "directory": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    make = sub.add_parser("create")
    make.add_argument("--source-root", type=Path, default=Path("/"))
    make.add_argument("--key-file", type=Path, required=True)
    make.add_argument("--output", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--backup", type=Path, required=True)
    check.add_argument("--key-file", type=Path, required=True)
    restore = sub.add_parser("stage")
    restore.add_argument("--backup", type=Path, required=True)
    restore.add_argument("--key-file", type=Path, required=True)
    restore.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "create":
        result = create(args.source_root, args.key_file, args.output)
    elif args.action == "verify":
        result = verify(args.backup, args.key_file)
    else:
        result = stage(args.backup, args.key_file, args.output)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
