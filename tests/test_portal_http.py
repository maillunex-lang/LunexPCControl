import base64
import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from panel.auth import PanelAuth
from panel.server import PanelHandler
from panel.live_view import LiveFrameService
from tests.test_screen_history import sample_png


class PortalHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        key=root/"auth.key";key.write_text("long-secure-demo-password-not-for-production");key.chmod(0o600)
        self.database=root/"registry.sqlite"
        with sqlite3.connect(self.database) as connection:
            connection.execute("CREATE TABLE routes(device TEXT PRIMARY KEY,port INTEGER,upstream_key TEXT)")
            connection.execute("INSERT INTO routes VALUES(?,?,?)",("lunex",23789,"demo-key-do-not-use-production-123456789"))
        self.capture_calls=[]
        def capture(port,secret):
            self.capture_calls.append(port)
            return sample_png()
        self.server=ThreadingHTTPServer(("127.0.0.1",0),PanelHandler)
        self.server.panel_auth=PanelAuth(key)
        self.server.registry_path=self.database
        self.server.live_view=LiveFrameService(self.database,capture=capture,clock=lambda:100.)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.port=self.server.server_port
        value=base64.b64encode(b"admin:long-secure-demo-password-not-for-production").decode()
        self.auth={"Authorization":"Basic "+value}

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(3)
        self.tmp.cleanup()

    def get(self,path,headers=None):
        conn=HTTPConnection("127.0.0.1",self.port,timeout=5)
        conn.request("GET",path,headers=headers or {})
        result=conn.getresponse()
        data=result.read()
        status=result.status
        content_type=result.getheader("Content-Type","")
        conn.close()
        return status,content_type,data

    def test_portal_routes_auth_and_no_implicit_capture(self):
        for route in ["/devices","/live","/api/devices"]:
            self.assertEqual(self.get(route)[0],401)
            self.assertEqual(self.get(route,self.auth)[0],200)
        self.assertEqual(self.capture_calls,[])
        html=self.get("/live",self.auth)[2]
        self.assertIn(b"X-LunexPC-LiveView",html)
        self.assertIn(b"pagehide",html)
        html2=self.get("/devices",self.auth)[2]
        self.assertIn("Мои компьютеры".encode(),html2)
        metadata=json.loads(self.get("/api/devices",self.auth)[2])
        self.assertEqual(metadata["total"],1)
        self.assertFalse(metadata["devices"][0]["ip_required"])
        self.assertNotIn("upstream_key",str(metadata))
        self.assertNotIn("demo-key",str(metadata))

    def test_live_requires_owner_and_explicit_browser_control(self):
        url="/api/live/frame/lunex/balanced.jpg"
        self.assertEqual(self.get(url)[0],401)
        self.assertEqual(self.get(url,self.auth)[0],403)
        headers={**self.auth,"X-LunexPC-LiveView":"active"}
        status,media,jpeg=self.get(url,headers)
        self.assertEqual(status,200)
        self.assertEqual(media,"image/jpeg")
        self.assertTrue(jpeg.startswith(b"\xff\xd8"))
        self.assertEqual(self.capture_calls,[23789])
        self.assertEqual(self.get(url,headers)[0],200)
        self.assertEqual(self.capture_calls,[23789]) # cached
        self.assertEqual(self.get("/api/live/frame/../../etc/passwd",headers)[0],404)
        self.assertEqual(self.get("/api/live/frame/lunex/super.jpg",headers)[0],404)
        self.assertEqual(self.get(url,{"Authorization":self.auth["Authorization"],
                                       "Host":"evil.example","X-LunexPC-LiveView":"active"})[0],403)

if __name__=="__main__":
    unittest.main()
