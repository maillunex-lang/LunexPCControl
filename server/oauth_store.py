"""Constrained owner-only OAuth 2.1 authorization-code + PKCE state store.

All bearer tokens and authorization codes are persisted as SHA-256 digests.
All registered public-client redirect URIs are strictly scoped to ChatGPT.
No access is granted without an owner-password approval and exact PKCE.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import time
from urllib.parse import urlsplit

ISSUER = "https://rikagro.ru"
RESOURCE = ISSUER + "/lunexpc-mcp"
SCOPE = "desktop:read"
MAX_CLIENTS = 50
CODE_TTL = 120
REQUEST_TTL = 300
ACCESS_TTL = 3600
REFRESH_TTL = 30 * 86400

CLIENT_NAME = re.compile(r"[\w ._-]{1,64}\Z", re.UNICODE)
PKCE_RE = re.compile(r"[A-Za-z0-9_-]{43}\Z")
VERIFIER_RE = re.compile(r"[A-Za-z0-9._~\-]{43,128}\Z")
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{24,256}\Z")
CALLBACK_RE = re.compile(r"/connector/oauth/[A-Za-z0-9_-]{6,128}\Z")


class OAuthError(ValueError):
    def __init__(self, code="invalid_request", status=400):
        super().__init__(code)
        self.code = code
        self.status = status


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def redirect_allowed(raw) -> bool:
    if not isinstance(raw, str) or len(raw) > 250 or not raw.isascii():
        return False
    try:
        u = urlsplit(raw)
    except ValueError:
        return False
    if (u.scheme != "https" or u.netloc != "chatgpt.com"
            or u.username is not None or u.password is not None
            or u.query or u.fragment):
        return False
    return (u.path == "/connector_platform_oauth_redirect"
            or CALLBACK_RE.fullmatch(u.path) is not None)


def unique_str(obj, key, *, max_len=1024):
    value = obj.get(key)
    if not isinstance(value, str) or not value or len(value) > max_len:
        raise OAuthError()
    return value


def _secure_private_db(path: Path):
    if path.is_symlink():
        raise PermissionError("OAuth database may not be a symlink")
    if path.exists():
        meta = path.stat()
        if not stat.S_ISREG(meta.st_mode) or stat.S_IMODE(meta.st_mode) & 0o077:
            raise PermissionError("OAuth database must be private")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise PermissionError("OAuth state directory is not safe")


class OAuthStore:
    def __init__(self, path, clock=None):
        self.path = str(path)
        self.clock = clock or time.time
        if self.path != ":memory:":
            _secure_private_db(Path(self.path))
        old_umask = os.umask(0o077)
        try:
            with self._db() as db:
                db.execute("""CREATE TABLE IF NOT EXISTS clients (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    redirects TEXT NOT NULL, created INTEGER NOT NULL
                )""")
                db.execute("""CREATE TABLE IF NOT EXISTS pending (
                    request_hash TEXT PRIMARY KEY, csrf_hash TEXT NOT NULL,
                    cookie_hash TEXT NOT NULL, client_id TEXT NOT NULL,
                    redirect_uri TEXT NOT NULL, challenge TEXT NOT NULL,
                    state TEXT NOT NULL, expires INTEGER NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0
                )""")
                db.execute("""CREATE TABLE IF NOT EXISTS codes (
                    hash TEXT PRIMARY KEY, client_id TEXT NOT NULL,
                    redirect_uri TEXT NOT NULL, challenge TEXT NOT NULL,
                    expires INTEGER NOT NULL
                )""")
                for table in ("access", "refresh"):
                    db.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
                        hash TEXT PRIMARY KEY, client_id TEXT NOT NULL,
                        expires INTEGER NOT NULL
                    )""")
        finally:
            os.umask(old_umask)
        if self.path != ":memory:":
            _secure_private_db(Path(self.path))

    def _db(self):
        return sqlite3.connect(self.path, timeout=5)

    def register(self, request):
        if not isinstance(request, dict):
            raise OAuthError()
        redirects = request.get("redirect_uris")
        if (not isinstance(redirects, list) or not 1 <= len(redirects) <= 5
                or any(not redirect_allowed(u) for u in redirects)
                or len(set(redirects)) != len(redirects)):
            raise OAuthError("invalid_redirect_uri")
        auth_method = request.get("token_endpoint_auth_method", "none")
        if auth_method != "none":
            raise OAuthError("invalid_client_metadata")
        if "grant_types" in request:
            grants = request["grant_types"]
            if (not isinstance(grants, list) or not grants
                    or any(item not in ("authorization_code", "refresh_token")
                           for item in grants)):
                raise OAuthError("invalid_client_metadata")
        if "response_types" in request and request["response_types"] != ["code"]:
            raise OAuthError("invalid_client_metadata")
        name = request.get("client_name", "ChatGPT")
        if not isinstance(name, str) or not CLIENT_NAME.fullmatch(name):
            raise OAuthError("invalid_client_metadata")
        now = int(self.clock())
        client_id = secrets.token_urlsafe(24)
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM clients").fetchone()[0] >= MAX_CLIENTS:
                raise OAuthError("registration_limit", 429)
            db.execute("INSERT INTO clients (id,name,redirects,created) VALUES (?,?,?,?)",
                       (client_id, name, json.dumps(redirects), now))
        return {"client_id": client_id, "client_name": name,
                "redirect_uris": redirects, "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"]}

    def authorize(self, query):
        if query.get("response_type") != "code":
            raise OAuthError("unsupported_response_type")
        client = unique_str(query, "client_id", max_len=128)
        redirect = unique_str(query, "redirect_uri", max_len=250)
        state = unique_str(query, "state", max_len=512)
        challenge = unique_str(query, "code_challenge", max_len=128)
        if (not PKCE_RE.fullmatch(challenge)
                or query.get("code_challenge_method") != "S256"):
            raise OAuthError("invalid_request")
        if query.get("scope", SCOPE) != SCOPE or query.get("resource") != RESOURCE:
            raise OAuthError("invalid_scope")
        with self._db() as db:
            row = db.execute("SELECT name,redirects FROM clients WHERE id=?",
                             (client,)).fetchone()
        if row is None or redirect not in json.loads(row[1]):
            raise OAuthError("invalid_client")
        request_id = secrets.token_urlsafe(24)
        csrf = secrets.token_urlsafe(24)
        cookie = secrets.token_urlsafe(24)
        now = int(self.clock())
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM pending WHERE expires<=?", (now,))
            if db.execute("SELECT count(*) FROM pending").fetchone()[0] >= 100:
                raise OAuthError("temporarily_unavailable", 429)
            db.execute("""INSERT INTO pending
                (request_hash,csrf_hash,cookie_hash,client_id,redirect_uri,challenge,state,expires)
                VALUES (?,?,?,?,?,?,?,?)""",
                (digest(request_id), digest(csrf), digest(cookie),
                 client, redirect, challenge, state, now + REQUEST_TTL))
        return {"request_id": request_id, "csrf": csrf, "cookie": cookie,
                "client_name": row[0], "redirect_uri": redirect,
                "scope": SCOPE}

    def approve(self, request_id, csrf, cookie, password, owner_secret):
        if (any(not isinstance(x, str) for x in
                (request_id, csrf, cookie, password, owner_secret))
                or not TOKEN_RE.fullmatch(request_id)
                or not TOKEN_RE.fullmatch(csrf)
                or not TOKEN_RE.fullmatch(cookie)):
            raise OAuthError("access_denied", 403)
        now = int(self.clock())
        denial = False
        result = None
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT csrf_hash,cookie_hash,client_id,redirect_uri,
                                       challenge,state,expires,attempts
                                FROM pending WHERE request_hash=?""",
                             (digest(request_id),)).fetchone()
            if row is None or row[6] <= now or row[7] >= 5:
                denial = True
            else:
                db.execute("""UPDATE pending SET attempts=attempts+1
                              WHERE request_hash=?""", (digest(request_id),))
                if (not hmac.compare_digest(digest(csrf), row[0])
                        or not hmac.compare_digest(digest(cookie), row[1])
                        or not hmac.compare_digest(password, owner_secret)):
                    denial = True
                else:
                    db.execute("DELETE FROM pending WHERE request_hash=?",
                               (digest(request_id),))
                    code = secrets.token_urlsafe(32)
                    db.execute("""INSERT INTO codes(hash,client_id,redirect_uri,challenge,expires)
                                  VALUES(?,?,?,?,?)""",
                               (digest(code), row[2], row[3], row[4], now + CODE_TTL))
                    result = {"code": code, "redirect_uri": row[3], "state": row[5]}
        if denial:
            raise OAuthError("access_denied", 403)
        return result

    def _issue_tokens(self, db, client, now):
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.execute("INSERT INTO access(hash,client_id,expires) VALUES(?,?,?)",
                   (digest(access), client, now + ACCESS_TTL))
        db.execute("INSERT INTO refresh(hash,client_id,expires) VALUES(?,?,?)",
                   (digest(refresh), client, now + REFRESH_TTL))
        return {"access_token": access, "token_type": "Bearer",
                "expires_in": ACCESS_TTL, "refresh_token": refresh,
                "scope": SCOPE}

    def token(self, body):
        if not isinstance(body, dict):
            raise OAuthError()
        client = unique_str(body, "client_id", max_len=128)
        if body.get("resource", RESOURCE) != RESOURCE:
            raise OAuthError("invalid_target")
        if "client_secret" in body:
            raise OAuthError("invalid_client")
        now = int(self.clock())
        grant = body.get("grant_type")
        if grant == "authorization_code":
            code = unique_str(body, "code", max_len=256)
            verifier = unique_str(body, "code_verifier", max_len=128)
            uri = unique_str(body, "redirect_uri", max_len=250)
            if not TOKEN_RE.fullmatch(code) or not VERIFIER_RE.fullmatch(verifier):
                raise OAuthError("invalid_grant")
            invalid = False
            result = None
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT client_id,redirect_uri,challenge,expires FROM codes WHERE hash=?",
                    (digest(code),)).fetchone()
                if row is None:
                    invalid = True
                else:
                    # Consume even on a bad verifier; prevents replay and probing.
                    db.execute("DELETE FROM codes WHERE hash=?", (digest(code),))
                    calculated = base64.urlsafe_b64encode(
                        hashlib.sha256(verifier.encode("ascii")).digest()
                    ).rstrip(b"=").decode("ascii")
                    if (row[0] != client or row[1] != uri
                            or row[3] <= now or not hmac.compare_digest(row[2], calculated)):
                        invalid = True
                    else:
                        result = self._issue_tokens(db, client, now)
            if invalid:
                raise OAuthError("invalid_grant")
            return result
        if grant == "refresh_token":
            token = unique_str(body, "refresh_token", max_len=256)
            if not TOKEN_RE.fullmatch(token):
                raise OAuthError("invalid_grant")
            invalid = False
            result = None
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT client_id,expires FROM refresh WHERE hash=?",
                                 (digest(token),)).fetchone()
                if row is None:
                    invalid = True
                else:
                    db.execute("DELETE FROM refresh WHERE hash=?", (digest(token),))
                    if row[0] != client or row[1] <= now:
                        invalid = True
                    else:
                        result = self._issue_tokens(db, client, now)
            if invalid:
                raise OAuthError("invalid_grant")
            return result
        raise OAuthError("unsupported_grant_type")

    def validate(self, token):
        if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
            return False
        with self._db() as db:
            row = db.execute("SELECT expires FROM access WHERE hash=?",
                             (digest(token),)).fetchone()
        return bool(row and row[0] > int(self.clock()))

    def revoke(self, body):
        if not isinstance(body, dict):
            raise OAuthError()
        client = unique_str(body, "client_id", max_len=128)
        token = unique_str(body, "token", max_len=256)
        if TOKEN_RE.fullmatch(token):
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                for table in ("access", "refresh"):
                    db.execute(f"DELETE FROM {table} WHERE hash=? AND client_id=?",
                               (digest(token), client))
        return {}
