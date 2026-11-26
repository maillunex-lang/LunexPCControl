"""Real localhost HTTP OAuth discovery, approval and token exchange.

No external network or owner's live password involved; upstream MCP is mocked
and the privileged gateway routing policy remains unchanged.
"""
import base64
import hashlib
from html import unescape
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlencode, urlsplit

from server.gateway import GatewayRegistry
from server.oauth_http import AUTH_CHALLENGE, RESOURCE_METADATA, METADATA, make_handler
from server.oauth_store import OAuthStore, RESOURCE

CALLBACK="https://chatgpt.com/connector_platform_oauth_redirect"


def approval_url(page):
    # A deliberate, user-clicked callback, not a 303 or a replay.
    match=re.search(rb'<a id="continue" href="([^"]+)"',page)
    if not match:
        raise AssertionError("missing explicit ChatGPT handoff")
    return unescape(match.group(1).decode("utf-8"))

VERIFIER="p"*64
CHALLENGE=base64.urlsafe_b64encode(
    hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()


class FakeResponse:
    status=200
    def getheader(self, name, default=None):
        return "application/json" if name.lower()=="content-type" else default
    def read(self,n=-1):
        return b'{"jsonrpc":"2.0","id":2,"result":{"tools":[]}}'


class FakeConnection:
    received=[]
    def __init__(self,host,port,timeout=None):
        assert host=="127.0.0.1" and port==18880
    def request(self,method,target,body=None,headers=None):
        self.__class__.received.append((method,target,body,headers))
    def getresponse(self):
        return FakeResponse()
    def close(self):
        pass


class OAuthHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.store=OAuthStore(root/"oauth.sqlite")
        self.owner_password="test-only-strong-panel-secret-abc123"
        self.owner_path=root/"panel-auth.key"
        self.owner_path.write_text(self.owner_password)
        self.owner_path.chmod(0o600)
        self.gateway=GatewayRegistry(str(root/"gateway.sqlite"))
        self.gateway.configure_route("lunex",23789,"test-internal-upstream-key-length-32!")
        self.internal=self.gateway.create_client("lunex")
        FakeConnection.received=[]
        self.server=ThreadingHTTPServer(("127.0.0.1",0),
            make_handler(self.store,self.owner_path,self.internal,self.gateway,
                         connection_factory=FakeConnection))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)
        self.temp.cleanup()

    def request(self,method,path,body=None,headers=None):
        hdr={"Host":"rikagro.ru"}
        if headers:hdr.update(headers)
        c=HTTPConnection("127.0.0.1",self.server.server_port,timeout=6)
        c.request(method,path,body,headers=hdr)
        res=c.getresponse()
        status=res.status
        data=res.read()
        response_headers=dict(res.getheaders())
        c.close()
        return status,response_headers,data

    def post(self,path,body,kind="application/x-www-form-urlencoded",headers=None):
        payload=(json.dumps(body).encode() if kind=="application/json"
                 else urlencode(body).encode())
        return self.request("POST",path,payload,{"Content-Type":kind,**(headers or {})})

    def register(self):
        status,_,payload=self.post("/oauth/register",{
            "client_name":"ChatGPT",
            "redirect_uris":[CALLBACK],
            "token_endpoint_auth_method":"none"
        },kind="application/json")
        self.assertEqual(status,201,payload)
        return json.loads(payload)["client_id"]

    def login_and_token(self):
        client=self.register()
        q=urlencode({"response_type":"code","client_id":client,"redirect_uri":CALLBACK,
                     "state":"chatgpt-csrf-state","resource":RESOURCE,"scope":"desktop:read",
                     "code_challenge_method":"S256","code_challenge":CHALLENGE})
        status,h,body=self.request("GET","/oauth/authorize?"+q)
        self.assertEqual(status,200,body)
        self.assertIn(b"LunexPCControl",body)
        self.assertIn(b"button.disabled = true;",body)
        self.assertIn("script-src 'nonce-",h["Content-Security-Policy"])
        self.assertIn(b"type=\"password\"",body)
        request_id=re.search(rb'name="request_id" value="([^"]+)"',body).group(1).decode()
        csrf=re.search(rb'name="csrf" value="([^"]+)"',body).group(1).decode()
        cookie=h["Set-Cookie"].split(";",1)[0]
        self.assertIn("Secure; HttpOnly; SameSite=Lax",h["Set-Cookie"])
        status,h,body=self.post("/oauth/approve",{
            "request_id":request_id,"csrf":csrf,
            "password":self.owner_password
        },headers={"Cookie":cookie,"Origin":"https://rikagro.ru"})
        self.assertEqual(status,200)
        self.assertNotIn("Location",h)
        self.assertNotIn("Set-Cookie",h)
        self.assertEqual(h["Content-Type"],"text/html; charset=utf-8")
        self.assertIn("no-store",h["Cache-Control"])
        self.assertIn("frame-ancestors 'none'",h["Content-Security-Policy"])
        url=urlsplit(approval_url(body))
        self.assertEqual(url.scheme,"https")
        self.assertEqual(url.netloc,"chatgpt.com")
        args=parse_qs(url.query)
        self.assertEqual(args["state"],["chatgpt-csrf-state"])
        self.assertEqual(args["iss"],["https://rikagro.ru"])
        status,h,body=self.post("/oauth/token",{
            "grant_type":"authorization_code","client_id":client,
            "code":args["code"][0],"redirect_uri":CALLBACK,
            "code_verifier":VERIFIER,"resource":RESOURCE
        })
        self.assertEqual(status,200,body)
        return client,json.loads(body)

    def test_chatgpt_specific_callback_receives_issuer_and_state(self):
        client=self.store.register({
            "client_name":"ChatGPT",
            "redirect_uris":["https://chatgpt.com/connector/oauth/abcDEF123456"],
            "token_endpoint_auth_method":"none",
        })["client_id"]
        q=urlencode({"response_type":"code","client_id":client,
                     "redirect_uri":"https://chatgpt.com/connector/oauth/abcDEF123456",
                     "state":"opaque-original-state","resource":RESOURCE,"scope":"desktop:read",
                     "code_challenge_method":"S256","code_challenge":CHALLENGE})
        status,headers,page=self.request("GET","/oauth/authorize?"+q)
        self.assertEqual(status,200)
        form={
            "request_id":re.search(rb'name="request_id" value="([^"]+)"',page).group(1).decode(),
            "csrf":re.search(rb'name="csrf" value="([^"]+)"',page).group(1).decode(),
            "password":self.owner_password
        }
        status,response,body=self.post("/oauth/approve",form,headers={
            "Cookie":headers["Set-Cookie"].split(";",1)[0],
            "Origin":"https://rikagro.ru"})
        self.assertEqual(status,200)
        url=urlsplit(approval_url(body))
        self.assertEqual(url.path,"/connector/oauth/abcDEF123456")
        params=parse_qs(url.query)
        self.assertEqual(params["state"],["opaque-original-state"])
        self.assertEqual(params["iss"],["https://rikagro.ru"])

    def test_protected_resource_and_as_discovery(self):
        for path in ("/.well-known/oauth-protected-resource",
                     "/.well-known/oauth-protected-resource/lunexpc-mcp"):
            status,h,body=self.request("GET",path)
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body),RESOURCE_METADATA)
        status,h,body=self.request("GET","/.well-known/oauth-authorization-server")
        self.assertEqual(status,200)
        metadata=json.loads(body)
        self.assertEqual(metadata, METADATA)
        self.assertIs(metadata["authorization_response_iss_parameter_supported"],True)
        self.assertEqual(metadata["code_challenge_methods_supported"],["S256"])
        self.assertEqual(metadata["token_endpoint_auth_methods_supported"],["none"])

    def test_full_http_oauth_and_strict_gateway_bridge(self):
        client,tokens=self.login_and_token()
        status,_,body=self.post("/lunexpc-mcp",{
            "jsonrpc":"2.0","id":2,"method":"tools/list"
        },kind="application/json",headers={
            "Authorization":"Bearer "+tokens["access_token"],
            "Accept":"application/json, text/event-stream",
        })
        self.assertEqual(status,200,body)
        self.assertEqual(len(FakeConnection.received),1)
        method,target,source,headers=FakeConnection.received[0]
        self.assertEqual(method,"POST")
        self.assertEqual(target,"/devices/lunex/mcp")
        self.assertEqual(headers["Authorization"],"Bearer "+self.internal)
        self.assertNotIn(tokens["access_token"],str(FakeConnection.received))
        status,_,data=self.post("/oauth/revoke",{
            "client_id":client,"token":tokens["access_token"]
        })
        self.assertEqual(status,200)
        status,h,_=self.post("/lunexpc-mcp",{
            "jsonrpc":"2.0","id":2,"method":"tools/list"
        },kind="application/json",headers={
            "Authorization":"Bearer "+tokens["access_token"]
        })
        self.assertEqual(status,401)
        self.assertEqual(h["WWW-Authenticate"],AUTH_CHALLENGE)

    def test_oauth_bridge_preserves_modern_mcp_method_headers(self):
        client,tokens=self.login_and_token()
        FakeConnection.received=[]
        modern_meta={"io.modelcontextprotocol/protocolVersion":"2026-07-28",
                     "io.modelcontextprotocol/clientCapabilities":{}}
        status,headers,body=self.post("/lunexpc-mcp",{
            "jsonrpc":"2.0","id":3,"method":"tools/list",
            "params":{"_meta":modern_meta}
        },kind="application/json",headers={
            "Authorization":"Bearer "+tokens["access_token"],
            "Mcp-Protocol-Version":"2026-07-28",
            "Mcp-Method":"tools/list",
            "Accept":"application/json, text/event-stream",
        })
        self.assertEqual(status,200,body)
        forwarded=FakeConnection.received[-1][3]
        self.assertEqual(forwarded["Mcp-Method"],"tools/list")
        self.assertEqual(forwarded["Mcp-Protocol-Version"],"2026-07-28")
        self.assertNotIn(tokens["access_token"],str(forwarded))

    def test_legacy_alpha_key_still_permitted(self):
        status,h,body=self.post("/lunexpc-mcp",{
            "jsonrpc":"2.0","id":2,"method":"tools/list"
        },kind="application/json",headers={
            "Authorization":"Bearer "+self.internal
        })
        self.assertEqual(status,200)
        self.assertEqual(len(FakeConnection.received),1)

    def test_no_auth_invalid_auth_and_untrusted_host(self):
        status,h,_=self.post("/lunexpc-mcp",{
            "jsonrpc":"2.0","id":2,"method":"tools/list"
        },kind="application/json")
        self.assertEqual(status,401)
        self.assertIn("resource_metadata=",h["WWW-Authenticate"])
        status,h,_=self.post("/lunexpc-mcp",{
            "jsonrpc":"2.0","id":2,"method":"tools/list"
        },kind="application/json",headers={"Authorization":"Bearer invalid"})
        self.assertEqual(status,401)
        self.assertEqual(len(FakeConnection.received),0)
        status,_,_=self.request("GET","/.well-known/oauth-authorization-server",
                                headers={"Host":"evil.example"})
        self.assertEqual(status,400)

    def test_owner_wrong_password_and_csrf_denied(self):
        client=self.register()
        q=urlencode({"response_type":"code","client_id":client,"redirect_uri":CALLBACK,
                     "state":"nonce","resource":RESOURCE,"scope":"desktop:read",
                     "code_challenge_method":"S256","code_challenge":CHALLENGE})
        status,h,body=self.request("GET","/oauth/authorize?"+q)
        self.assertEqual(status,200)
        request_id=re.search(rb'name="request_id" value="([^"]+)"',body).group(1).decode()
        csrf=re.search(rb'name="csrf" value="([^"]+)"',body).group(1).decode()
        fields={"request_id":request_id,"csrf":csrf,"password":self.owner_password}
        status,_,_=self.post("/oauth/approve",fields,
                             headers={"Origin":"https://evil.example"})
        self.assertEqual(status,403)
        status,_,_=self.post("/oauth/approve",fields)
        self.assertEqual(status,403)
        status,_,_=self.post("/oauth/approve",{
            **fields,"password":"incorrect"},headers={
                "Cookie":h["Set-Cookie"].split(";",1)[0],
                "Origin":"https://rikagro.ru",
            })
        self.assertEqual(status,403)

    def _new_approval_page(self, client):
        q=urlencode({"response_type":"code","client_id":client,"redirect_uri":CALLBACK,
                     "state":"new-independent-flow","resource":RESOURCE,"scope":"desktop:read",
                     "code_challenge_method":"S256","code_challenge":CHALLENGE})
        status, headers, page=self.request("GET","/oauth/authorize?"+q)
        self.assertEqual(status,200)
        request_id=re.search(rb'name="request_id" value="([^"]+)"',page).group(1).decode()
        csrf=re.search(rb'name="csrf" value="([^"]+)"',page).group(1).decode()
        return {"request_id":request_id,"csrf":csrf,
                "password":self.owner_password}, headers["Set-Cookie"].split(";",1)[0]

    def test_parallel_chrome_oauth_tabs_have_independent_cookies(self):
        client=self.register()
        first,first_cookie=self._new_approval_page(client)
        second,second_cookie=self._new_approval_page(client)
        self.assertNotEqual(first_cookie.split("=",1)[0],second_cookie.split("=",1)[0])
        # Chrome sends cookies for both tabs: select by request, not last cookie.
        all_cookies=first_cookie+"; "+second_cookie
        for form in (first,second):
            status,head,body=self.post("/oauth/approve",form,headers={
                "Cookie":all_cookies,
                "Origin":"https://rikagro.ru",
                "Sec-Fetch-Site":"same-origin",
            })
            self.assertEqual(status,200)
            self.assertIn("chatgpt.com",approval_url(body))

    def test_android_cookie_missing_same_origin_fallback(self):
        client=self.register()
        form,_=self._new_approval_page(client)
        status,headers,body=self.post("/oauth/approve",form,headers={
            "Origin":"https://rikagro.ru",
            "Sec-Fetch-Site":"same-origin",
        })
        self.assertEqual(status,200)
        self.assertIn("chatgpt.com",approval_url(body))

    def test_android_opaque_origin_requires_intact_cookie(self):
        client=self.register()
        form,cookie=self._new_approval_page(client)
        status,head,body=self.post("/oauth/approve",form,headers={
            "Cookie":cookie,"Origin":"null","Sec-Fetch-Site":"cross-site"})
        self.assertEqual(status,200)
        self.assertIn("chatgpt.com",approval_url(body))

    def test_android_opaque_origin_rejects_missing_or_invalid_cookie(self):
        client=self.register()
        for supplied in (None, "wrong-but-syntactically-valid-abcdef1234567890"):
            form,cookie=self._new_approval_page(client)
            headers={"Origin":"null","Sec-Fetch-Site":"cross-site"}
            if supplied is not None:
                headers["Cookie"]=cookie.split("=",1)[0]+"="+supplied
            status,_,_=self.post("/oauth/approve",form,headers=headers)
            self.assertEqual(status,403)

    def test_opaque_origin_does_not_allow_invalid_csrf(self):
        client=self.register()
        form,cookie=self._new_approval_page(client)
        status,_,_=self.post("/oauth/approve",
                             {**form,"csrf":"x"*43},headers={
            "Cookie":cookie,"Origin":"null","Sec-Fetch-Site":"cross-site"})
        self.assertEqual(status,403)

    def test_duplicate_approval_never_reissues_code(self):
        client=self.register()
        form,cookie=self._new_approval_page(client)
        headers={"Cookie":cookie,"Origin":"null","Sec-Fetch-Site":"cross-site"}
        status,response,first_page=self.post("/oauth/approve",form,headers=headers)
        self.assertEqual(status,200)
        self.assertIn("code=",approval_url(first_page))
        self.assertNotIn("Location",response)
        self.assertNotIn("Set-Cookie",response)
        status,response,body=self.post("/oauth/approve",form,headers=headers)
        self.assertEqual(status,200)
        self.assertIn("Вход уже подтверждён".encode(),body)
        self.assertNotIn("Location",response)
        self.assertNotIn(b"code=",body)
        status,_,_=self.post("/oauth/approve",{**form,"csrf":"x"*43},headers=headers)
        self.assertEqual(status,403)

    def test_cookie_missing_without_proven_origin_denied_html(self):
        client=self.register()
        form,_=self._new_approval_page(client)
        for headers in ({}, {"Origin":"https://rikagro.ru",
                             "Sec-Fetch-Site":"cross-site"},
                        {"Origin":"https://other.example",
                         "Sec-Fetch-Site":"same-origin"}):
            status,head,body=self.post("/oauth/approve",form,headers=headers)
            self.assertEqual(status,403)
            self.assertTrue(head["Content-Type"].startswith("text/html"))
            self.assertIn("Вернуться в ChatGPT".encode(),body)
            self.assertNotIn(self.owner_password.encode(),body)
            self.assertIn("frame-ancestors 'none'",head["Content-Security-Policy"])

    def test_same_site_origin_verified_with_missing_cookie(self):
        client=self.register()
        form,_=self._new_approval_page(client)
        status,head,body=self.post("/oauth/approve",form,headers={
            "Origin":"https://rikagro.ru", "Sec-Fetch-Site":"same-site",
        })
        self.assertEqual(status,200)
        self.assertIn("chatgpt.com",approval_url(body))

    def test_bad_cookie_never_uses_browser_fallback(self):
        client=self.register()
        form,cookie=self._new_approval_page(client)
        name=cookie.split("=",1)[0]
        status,head,body=self.post("/oauth/approve",form,headers={
            "Cookie":name+"=wrong-but-syntactically-valid-abcdef1234567890",
            "Origin":"https://rikagro.ru",
            "Sec-Fetch-Site":"same-origin",
        })
        self.assertEqual(status,403)
        self.assertTrue(head["Content-Type"].startswith("text/html"))
        self.assertIn("Сессия авторизации".encode(),body)

    def test_incorrect_password_renders_safe_error_page(self):
        client=self.register()
        form,cookie=self._new_approval_page(client)
        status,head,body=self.post("/oauth/approve",{**form,"password":"wrong"},
                                    headers={"Cookie":cookie,
                                             "Origin":"https://rikagro.ru",
                                             "Sec-Fetch-Site":"same-origin"})
        self.assertEqual(status,403)
        self.assertEqual(head["Content-Type"],"text/html; charset=utf-8")
        self.assertIn("Пароль не прошёл проверку".encode(),body)
        self.assertNotIn("wrong".encode(),body)
        self.assertIn("no-store",head["Cache-Control"])

    def test_unregistered_callback_rejected_before_login(self):
        client=self.register()
        q=urlencode({"response_type":"code","client_id":client,
                     "redirect_uri":"https://attacker.example/callback",
                     "state":"nonce","resource":RESOURCE,"scope":"desktop:read",
                     "code_challenge_method":"S256","code_challenge":CHALLENGE})
        status,_,_=self.request("GET","/oauth/authorize?"+q)
        self.assertEqual(status,400)


if __name__=="__main__":
    unittest.main()
