import base64
import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from panel.auth import PanelAuth
from panel.server import PanelHandler
from server.screen_history import ScreenHistory

class PortalPublicHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        credential = root/"passwd"
        credential.write_text("a-secret-longer-than-32-characters-for-testing")
        credential.chmod(0o600)
        self.web = ThreadingHTTPServer(("127.0.0.1",0),PanelHandler)
        self.web.panel_auth = PanelAuth(credential)
        self.web.screen_history = ScreenHistory(root/"screens")
        self.thread = threading.Thread(target=self.web.serve_forever,daemon=True)
        self.thread.start()
        secret = base64.b64encode(b"admin:a-secret-longer-than-32-characters-for-testing").decode()
        self.basic = "Basic "+secret
    def tearDown(self):
        self.web.shutdown();self.web.server_close();self.thread.join(3);self.temp.cleanup()
    def request(self, path, host, auth=True, method="GET", payload=None, headers=None):
        h={"Host":host}
        if auth:h["Authorization"]=self.basic
        if headers:h.update(headers)
        body=None
        if payload is not None:
            body=json.dumps(payload).encode()
            h["Content-Type"]="application/json"
        c=HTTPConnection("127.0.0.1",self.web.server_port,timeout=6)
        c.request(method,path,body,headers=h)
        r=c.getresponse();s=r.status;b=r.read();c.close();return s,b
    def test_public_html_stays_under_named_prefix(self):
        for path in ("/","/devices","/live","/monitor"):
            self.assertEqual(self.request(path,"rikagro.ru",auth=False)[0],401)
            status,body=self.request(path,"rikagro.ru")
            self.assertEqual(status,200)
            self.assertIn(b'/portalmcp/',body)
            self.assertNotIn(b'href="/devices"',body)
        status,body=self.request("/monitor","127.0.0.1:"+str(self.web.server_port))
        self.assertEqual(status,200)
        self.assertIn(b"'/api/screens'",body)
        self.assertNotIn(b"/portalmcp/",body)

    def test_public_settings_require_auth_origin_and_custom_header(self):
        payload={"retention_hours":24,"max_count":1}
        endpoint="/api/screens/settings"
        hdr={"Origin":"https://rikagro.ru","X-LunexPC-Action":"screens-settings"}
        self.assertEqual(self.request(endpoint,"rikagro.ru",False,"POST",payload,hdr)[0],401)
        self.assertEqual(self.request(endpoint,"rikagro.ru",True,"POST",payload,hdr)[0],200)
        hdr["Origin"]="https://wrong.example"
        self.assertEqual(self.request(endpoint,"rikagro.ru",True,"POST",payload,hdr)[0],403)
        self.assertEqual(self.request(endpoint,"attacker.example")[0],403)

    def test_browser_tracking_query_on_html_only(self):
        for path in ("/", "/devices", "/live", "/monitor"):
            url=path+"?utm_source=chatgpt.com"
            self.assertEqual(self.request(url,"rikagro.ru",False)[0],401)
            self.assertEqual(self.request(url,"rikagro.ru")[0],200)
        self.assertEqual(self.request("/api/screens?utm_source=test","rikagro.ru")[0],404)
