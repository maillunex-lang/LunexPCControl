#!/usr/bin/env python3
"""Owner-only ChatGPT Alpha bearer credential. Never print the secret.

The existing loopback MCP gateway independently authorizes this token,
and its fail-closed policy permits Screenshot and ControlStatus only.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat

from server.gateway import GatewayRegistry

REGISTRY = Path("/var/lib/lunexpc-gateway/registry.sqlite")
KEY = Path("/var/lib/lunexpc-gateway/chatgpt-alpha.key")
DEVICE = "lunex"


def _read_token(path: Path) -> str:
    if path.is_symlink():
        raise PermissionError("symlink credentials are forbidden")
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise PermissionError("credential must be private 0600")
    token = path.read_text(encoding="ascii").strip()
    if len(token) < 40:
        raise ValueError("invalid credential")
    return token


def status(registry_path=REGISTRY, key_path=KEY):
    registry = GatewayRegistry(str(registry_path))
    if not key_path.exists():
        return {"configured": False, "active": False}
    token = _read_token(key_path)
    return {"configured": True, "active": bool(registry.authenticate(DEVICE, token))}


def provision(registry_path=REGISTRY, key_path=KEY):
    if os.geteuid() != 0:
        raise PermissionError("root required to provision ChatGPT key")
    key_path = Path(key_path)
    if key_path.exists() or key_path.is_symlink():
        raise FileExistsError("key exists; use rotate to revoke and replace it")
    parent = key_path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise PermissionError("unsafe key directory")
    registry = GatewayRegistry(str(registry_path))
    token = registry.create_client(DEVICE)
    fd = None
    try:
        fd = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as out:
            fd = None
            out.write(token + "\n")
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        registry.revoke_client(token)
        if fd is not None:
            os.close(fd)
        raise
    return {"created": True, "token_disclosed": False}


def rotate(registry_path=REGISTRY, key_path=KEY):
    if os.geteuid() != 0:
        raise PermissionError("root required")
    registry = GatewayRegistry(str(registry_path))
    old = _read_token(Path(key_path))
    registry.revoke_client(old)
    # Existing file holds a revoked key until a new one is safely persisted.
    replacement = registry.create_client(DEVICE)
    temp = Path(str(key_path) + ".new")
    if temp.exists() or temp.is_symlink():
        registry.revoke_client(replacement)
        raise FileExistsError("unexpected staged key")
    try:
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(replacement + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, key_path)
    except BaseException:
        registry.revoke_client(replacement)
        raise
    return {"rotated": True, "old_key_revoked": True, "token_disclosed": False}


def revoke(registry_path=REGISTRY, key_path=KEY):
    if os.geteuid() != 0:
        raise PermissionError("root required")
    registry = GatewayRegistry(str(registry_path))
    current = _read_token(Path(key_path))
    registry.revoke_client(current)
    return {"revoked": True, "token_disclosed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "provision", "rotate", "revoke"))
    args = parser.parse_args()
    if args.action == "status":
        result = status()
    elif args.action == "provision":
        result = provision()
    elif args.action == "rotate":
        result = rotate()
    else:
        result = revoke()
    import json
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
