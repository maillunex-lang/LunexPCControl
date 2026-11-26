"""Fail-closed optional bearer authentication for private LunexPCControl panel.

The bearer token is loaded once from a 0600 regular file in private storage.
No token is logged, exposed to JavaScript, or sent through a URL.
"""
from __future__ import annotations
import hmac
import base64
import binascii
import os
import stat
from pathlib import Path


class PanelAuth:
    def __init__(self, key_file=None):
        self.configured = bool(key_file)
        self.secret = None
        if not self.configured:
            return
        path = Path(key_file)
        if path.is_symlink():
            raise PermissionError("panel credential may not be symlinked")
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) & 0o077:
            raise PermissionError("panel credential must be a private regular file")
        if metadata.st_size > 256:
            raise ValueError("panel credential file too large")
        secret = path.read_text(encoding="ascii").strip()
        if not (32 <= len(secret) <= 128) or not secret.isascii():
            raise ValueError("invalid panel credential")
        self.secret = secret

    def verify(self, authorization):
        if self.secret is None:
            return not self.configured
        if not isinstance(authorization, str) or len(authorization) > 256:
            return False
        scheme, sep, supplied = authorization.partition(" ")
        if not sep or scheme != "Basic" or not supplied or len(supplied) > 180:
            return False
        try:
            raw = base64.b64decode(supplied, validate=True).decode("utf-8")
        except (ValueError, UnicodeError, binascii.Error):
            return False
        user, delim, password = raw.partition(":")
        if not delim or not hmac.compare_digest(user, "admin"):
            return False
        return hmac.compare_digest(password, self.secret)
