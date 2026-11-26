#!/usr/bin/env python3
"""Provision a separate OAuth bridge client under the existing gateway policy.

Run as the dedicated lunexpc-gateway system user. Generates a private
0600 file under a 0700 directory, without printing the actual token.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat

from installer.chatgpt_key import _read_token
from server.gateway import GatewayRegistry

REGISTRY = Path("/var/lib/lunexpc-gateway/registry.sqlite")
KEY = Path("/var/lib/lunexpc-gateway/oauth/proxy.key")
DEVICE = "lunex"


def check_directory(path):
    directory = Path(path).parent
    if directory.is_symlink() or not directory.is_dir():
        raise PermissionError("missing private OAuth directory")
    metadata = directory.stat()
    if stat.S_IMODE(metadata.st_mode) != 0o700:
        raise PermissionError("OAuth directory must have mode 0700")
    if metadata.st_uid != os.geteuid():
        raise PermissionError("OAuth directory must be owned by current user")


def provision(registry_path=REGISTRY, key_path=KEY):
    key_path = Path(key_path)
    check_directory(key_path)
    if key_path.exists() or key_path.is_symlink():
        raise FileExistsError("OAuth proxy key already exists")
    registry = GatewayRegistry(str(registry_path))
    token = registry.create_client(DEVICE)
    fd = None
    try:
        fd = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as file:
            fd = None
            file.write(token + "\n")
            file.flush()
            os.fsync(file.fileno())
    except BaseException:
        registry.revoke_client(token)
        if fd is not None:
            os.close(fd)
        raise
    return {"created": True, "token_disclosed": False}


def status(registry_path=REGISTRY, key_path=KEY):
    if not Path(key_path).exists():
        return {"configured": False, "active": False}
    token = _read_token(Path(key_path))
    registry = GatewayRegistry(str(registry_path))
    return {"configured": True, "active": registry.authenticate(DEVICE, token) is not None}


def revoke(registry_path=REGISTRY, key_path=KEY):
    token = _read_token(Path(key_path))
    registry = GatewayRegistry(str(registry_path))
    registry.revoke_client(token)
    return {"revoked": True, "token_disclosed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("provision", "status", "revoke"))
    args = parser.parse_args()
    if args.action == "provision":
        result = provision()
    elif args.action == "status":
        result = status()
    else:
        result = revoke()
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
