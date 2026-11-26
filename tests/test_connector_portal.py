import base64
import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import time
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from panel.auth import PanelAuth
from panel.server import PanelHandler
from server.connector_registry import ConnectorRegistry,signature_payload
from server.gateway_policy import RateLimiter


class ConnectorPortalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        cred=root/"panel.key";cred.write_text("test-only-very-long-panel-secret-value");cred.chmod(0o600)
        self.srv=ThreadingHTTPServer(("127.0.0.1",0),PanelHandler)
        self.srv.panel_auth=PanelAuth(cred)
        self.srv.connector_registry=ConnectorRegistry(root/"connector.sqlite")
        self.srv.connector_limiter=RateLimiter(limit=60,window=60)
        self.thread=threading.Thread(target=self.srv.serve_forever,daemon=True)
        self.thread.start()
        self.basic="Basic "+base64.b64encode(b"admin:test-only-very-long-panel-secret-value").decode()
        self.priv=Ed25519PrivateKey.generate()

    def tearDown(self):
        self.srv.shutdown();self.srv.server_close();self.thread.join(3)
        self.temp.cleanup()

    def request(self,path,body=None,headers=None,method="GET"):
        h={"Host":"rikagro.ru"}
        if headers:h.update(headers)
        if body is not None:
            h["Content-Type"]="application/json"
            body=json.dumps(body).encode("utf-8")
        c=HTTPConnection("127.0.0.1",self.srv.server_port,timeout=6)
        c.request(method,path,body,headers=h)
        r=c.getresponse();status=r.status;b=r.read();c.close()
        return status,b

    def owner(self,action,body):
        return self.request("/api/connectors/"+action,body,{
            "Authorization":self.basic,"Origin":"https://rikagro.ru",
            "X-LunexPC-Action": "connector-invite" if action=="invitations" else "connector-revoke"
        },"POST")

    def client(self,action,body,headers=None):
        h={"X-LunexPC-Connector":"v1"}
        if headers:h.update(headers)
        return self.request("/api/connectors/"+action,body,h,"POST")

    def test_public_claim_signed_heartbeat_owner_revoke(self):
        self.assertEqual(self.owner("invitations",{"os":"linux","name":"Ubuntu"})[0],200)
        status,raw=self.owner("invitations",{"os":"windows","name":"Desktop"})
        self.assertEqual(status,200)
        invite=json.loads(raw)
        code=invite["pairing_code"]
        key=self.priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
        pub=base64.urlsafe_b64encode(key).decode()
        body={"pairing_code":code,"os":"windows","public_key":pub}
        self.assertEqual(self.client("claim",body,{"Origin":"https://evil.example"})[0],403)
        status,data=self.client("claim",body)
        self.assertEqual(status,200)
        registration=json.loads(data)
        device=registration["device_id"]
        self.assertNotIn(code, str(registration))
        self.assertEqual(self.client("claim",body)[0],403)
        status,data=self.request("/api/connectors",headers={"Authorization":self.basic})
        self.assertEqual(status,200)
        self.assertIn(device,data.decode())
        self.assertNotIn(code,data.decode())
        self.assertNotIn(pub,data.decode())
        now=int(time.time())
        nonce="nonce_abcdefghijk12345678"
        sign=base64.urlsafe_b64encode(self.priv.sign(signature_payload(device,now,nonce))).decode()
        beat={"device_id":device,"timestamp":now,"nonce":nonce,"signature":sign}
        self.assertEqual(self.client("heartbeat",beat)[0],200)
        self.assertEqual(self.client("heartbeat",beat)[0],403)
        self.assertEqual(self.owner("revoke",{"device_id":device})[0],200)
        self.assertEqual(self.client("heartbeat",{**beat,"nonce":"nonce_new_abcdefgh123456"})[0],403)

    def test_owner_csrf_auth_and_transport_restrictions(self):
        body={"os":"linux","name":"VPS"}
        self.assertEqual(self.request("/api/connectors/invitations",body,{"Origin":"https://rikagro.ru","X-LunexPC-Action":"connector-invite"},"POST")[0],401)
        self.assertEqual(self.request("/api/connectors/invitations",body,{"Authorization":self.basic,"Origin":"https://evil.example","X-LunexPC-Action":"connector-invite"},"POST")[0],403)
        self.assertEqual(self.request("/api/connectors/invitations",body,{"Authorization":self.basic,"Origin":"https://rikagro.ru"},"POST")[0],403)
        self.assertEqual(self.request("/api/connectors/invitations",body,{"Authorization":self.basic,"Origin":"https://rikagro.ru","X-LunexPC-Action":"connector-invite"},"PUT")[0],405)
        self.assertEqual(self.client("claim",{"pairing_code":"invalid","os":"linux","public_key":"wrong"})[0],403)
        self.assertEqual(self.request("/api/connectors")[0],401)

if __name__=="__main__":
    unittest.main()
