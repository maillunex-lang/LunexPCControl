import base64
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

from panel.auth import PanelAuth
from panel.server import PanelHandler
from server.screen_history import ScreenHistory
from tests.test_screen_history import response, sample_png


class MonitorHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        key=root/"panel.key"
        key.write_text("a-long-private-example-password-for-browser")
        key.chmod(0o600)
        self.store=ScreenHistory(root/"screens")
        self.server=ThreadingHTTPServer(("127.0.0.1",0),PanelHandler)
        self.server.panel_auth=PanelAuth(key)
        self.server.screen_history=self.store
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.port=self.server.server_port
        secret=base64.b64encode(b"admin:a-long-private-example-password-for-browser").decode()
        self.auth={"Authorization":"Basic "+secret}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def call(self,method,path,*,payload=None,headers=None):
        h={"Connection":"close",**(headers or {})}
        body=None
        if payload is not None:
            body=json.dumps(payload).encode()
            h["Content-Type"]="application/json"
        conn=HTTPConnection("127.0.0.1",self.port,timeout=5)
        conn.request(method,path,body=body,headers=h)
        r=conn.getresponse()
        out=r.read()
        status=r.status
        response_headers=dict(r.getheaders())
        conn.close()
        return status,out,response_headers

    def action_headers(self, action):
        return {**self.auth,
                "Origin":f"http://127.0.0.1:{self.port}",
                "X-LunexPC-Action":action}

    def test_new_monitor_menu_requires_password(self):
        status,_,_=self.call("GET","/monitor")
        self.assertEqual(status,401)
        status,page,headers=self.call("GET","/monitor",headers=self.auth)
        self.assertEqual(status,200)
        self.assertIn("Мониторинг экрана".encode(),page)
        self.assertIn(b"setInterval(refresh,3000)",page)
        self.assertEqual(headers["Cache-Control"],"no-store")
        status,data,_=self.call("GET","/api/screens",headers=self.auth)
        self.assertEqual(status,200)
        self.assertFalse(json.loads(data)["settings"]["enabled"])
        self.assertEqual(json.loads(data)["items"],[])

    def test_settings_csrf_and_genuine_private_image(self):
        change={"retention_hours":24,"max_count":1}
        path="/api/screens/settings"
        self.assertEqual(self.call("POST",path,payload=change,headers=self.auth)[0],403)
        headers={**self.auth,"Origin":f"http://127.0.0.1:{self.port}"}
        self.assertEqual(self.call("POST",path,payload=change,headers=headers)[0],403)
        self.assertEqual(self.call("POST",path,payload=change,headers={
            **self.action_headers("screens-settings"),"Origin":"https://evil.example"})[0],403)
        status,data,_=self.call("POST",path,payload=change,
                                 headers=self.action_headers("screens-settings"))
        self.assertEqual(status,200)
        self.assertEqual(json.loads(data)["max_count"],1)
        self.assertEqual(self.store.capture("pc",response()),1)
        status,data,_=self.call("GET","/api/screens",headers=self.auth)
        self.assertEqual(status,200)
        item=json.loads(data)["items"][0]
        url="/api/screens/"+item["id"]+".png"
        self.assertEqual(self.call("GET",url)[0],401)
        status,image,headers=self.call("GET",url,headers=self.auth)
        self.assertEqual(status,200)
        self.assertEqual(image,sample_png())
        self.assertEqual(headers["Cache-Control"],"no-store")
        self.assertEqual(headers["Content-Type"],"image/png")
        self.assertEqual(self.call("GET","/api/screens/../../etc/passwd",headers=self.auth)[0],404)
        clear=self.action_headers("screens-clear")
        self.assertEqual(self.call("POST","/api/screens/clear",payload={},
                                   headers=clear)[0],200)
        self.assertEqual(self.call("GET",url,headers=self.auth)[0],404)

    def test_invalid_settings_and_no_authorized_screenshot(self):
        invalid=self.action_headers("screens-settings")
        status,_,_=self.call("POST","/api/screens/settings",
                             payload={"retention_hours":999,"max_count":50},
                             headers=invalid)
        self.assertEqual(status,400)
        self.assertFalse(self.store.settings()["enabled"])
        self.assertEqual(self.store.list(),[])
        self.assertEqual(self.call("GET","/api/screens/not-hex.png",
                                   headers=self.auth)[0],404)

if __name__=="__main__":
    unittest.main()
