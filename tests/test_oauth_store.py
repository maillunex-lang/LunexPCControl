import base64
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from server.oauth_store import (
    ACCESS_TTL, CODE_TTL, RESOURCE, SCOPE,
    OAuthError, OAuthStore, redirect_allowed,
)

CALLBACK = "https://chatgpt.com/connector_platform_oauth_redirect"
V = "a" * 64


def challenge(verifier=V):
    return base64.urlsafe_b64encode(hashlib.sha256(
        verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


class OAuthStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 1000000
        self.dbfile = Path(self.tmp.name) / "oauth.sqlite"
        self.store = OAuthStore(self.dbfile, clock=lambda: self.now)
        self.client = self.store.register({
            "client_name": "ChatGPT",
            "redirect_uris": [CALLBACK],
            "token_endpoint_auth_method": "none",
        })["client_id"]

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, **overrides):
        params = {
            "response_type": "code",
            "client_id": self.client,
            "redirect_uri": CALLBACK,
            "state": "own_state_1234",
            "code_challenge": challenge(),
            "code_challenge_method": "S256",
            "resource": RESOURCE,
            "scope": SCOPE,
        }
        params.update(overrides)
        return self.store.authorize(params)

    def approve(self, flow):
        return self.store.approve(flow["request_id"], flow["csrf"], flow["cookie"],
                                  "correct-panel-password", "correct-panel-password")

    def test_client_registrations_require_exact_chatgpt_callback(self):
        for path in [
            "https://chatgpt.com.evil.com/connector_platform_oauth_redirect",
            "https://evil.example/callback",
            "http://chatgpt.com/connector_platform_oauth_redirect",
            "https://chatgpt.com/connector_platform_oauth_redirect?evil=1",
            "https://chatgpt.com@evil.example/callback",
            "https://chatgpt.com/foo",
            "https://chatgpt.com/connector/oauth/../../malice",
            "https://chatgpt.com/connector/oauth/short",
        ]:
            self.assertFalse(redirect_allowed(path), path)
            with self.assertRaises(OAuthError):
                self.store.register({"redirect_uris": [path]})
        self.assertTrue(redirect_allowed(CALLBACK))
        self.assertTrue(redirect_allowed(
            "https://chatgpt.com/connector/oauth/abcDEF123456"))
        self.assertEqual(self.dbfile.stat().st_mode & 0o777, 0o600)

    def test_pkce_authorization_code_access_refresh_and_revoke(self):
        flow = self.start()
        auth = self.approve(flow)
        self.assertEqual(auth["redirect_uri"], CALLBACK)
        payload = {"client_id": self.client, "grant_type": "authorization_code",
                   "redirect_uri": CALLBACK, "code_verifier": V,
                   "code": auth["code"], "resource": RESOURCE}
        tokens = self.store.token(payload)
        self.assertTrue(self.store.validate(tokens["access_token"]))
        self.assertEqual(tokens["scope"], SCOPE)
        self.assertEqual(tokens["token_type"], "Bearer")
        self.assertFalse(self.store.validate(tokens["refresh_token"]))
        with self.assertRaises(OAuthError):
            self.store.token(payload)
        newer = self.store.token({
            "grant_type": "refresh_token", "client_id": self.client,
            "refresh_token": tokens["refresh_token"], "resource": RESOURCE,
        })
        self.assertTrue(self.store.validate(newer["access_token"]))
        with self.assertRaises(OAuthError):
            self.store.token({
                "grant_type": "refresh_token", "client_id": self.client,
                "refresh_token": tokens["refresh_token"], "resource": RESOURCE,
            })
        self.assertEqual(self.store.revoke({
            "client_id": self.client, "token": newer["access_token"],
        }), {})
        self.assertFalse(self.store.validate(newer["access_token"]))
        self.now += ACCESS_TTL + 1
        self.assertFalse(self.store.validate(tokens["access_token"]))

    def test_wrong_pkce_consumes_code_and_never_issues_token(self):
        flow = self.start()
        auth = self.approve(flow)
        request = {"client_id": self.client, "grant_type": "authorization_code",
                   "redirect_uri": CALLBACK, "code_verifier": "b"*64,
                   "code": auth["code"], "resource": RESOURCE}
        with self.assertRaises(OAuthError):
            self.store.token(request)
        request["code_verifier"] = V
        with self.assertRaises(OAuthError):
            self.store.token(request)

    def test_wrong_password_tracks_attempts_then_locks(self):
        flow = self.start()
        for _ in range(5):
            with self.assertRaises(OAuthError):
                self.store.approve(flow["request_id"],flow["csrf"],flow["cookie"],
                                   "bad", "correct-panel-password")
        with self.assertRaises(OAuthError):
            self.approve(flow)
        with sqlite3.connect(self.dbfile) as db:
            count = db.execute("SELECT attempts FROM pending").fetchone()[0]
        self.assertEqual(count,5)

    def test_csrf_and_cookie_binding_enforced(self):
        flow=self.start()
        with self.assertRaises(OAuthError):
            self.store.approve(flow["request_id"],flow["csrf"],
                               "different_cookie_valid1234567890",
                               "correct-panel-password","correct-panel-password")
        with self.assertRaises(OAuthError):
            self.store.approve(flow["request_id"],"mismatched_token123456789012345678",
                               flow["cookie"],
                               "correct-panel-password","correct-panel-password")

    def test_all_expiration_and_wrong_resource_rejected(self):
        flow=self.start()
        self.now += 301
        with self.assertRaises(OAuthError):
            self.approve(flow)
        with self.assertRaises(OAuthError):
            self.start(resource="https://different.example/")
        with self.assertRaises(OAuthError):
            self.start(code_challenge_method="plain")
        flow=self.start()
        auth=self.approve(flow)
        self.now += CODE_TTL + 1
        with self.assertRaises(OAuthError):
            self.store.token({"client_id":self.client,"grant_type":"authorization_code",
                              "redirect_uri":CALLBACK,"code_verifier":V,"code":auth["code"]})

    def test_replay_refresh_does_not_resurrect_revoked_access(self):
        flow=self.start()
        issued=self.approve(flow)
        tokens=self.store.token({"client_id":self.client,"grant_type":"authorization_code",
                                 "redirect_uri":CALLBACK,"code_verifier":V,"code":issued["code"]})
        self.store.revoke({"client_id":self.client,"token":tokens["refresh_token"]})
        with self.assertRaises(OAuthError):
            self.store.token({"client_id":self.client,"grant_type":"refresh_token",
                              "refresh_token":tokens["refresh_token"]})
        self.assertTrue(self.store.validate(tokens["access_token"]))


if __name__=="__main__":
    unittest.main()
