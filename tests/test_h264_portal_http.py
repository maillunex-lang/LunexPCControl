import base64
import sqlite3
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from panel.auth import PanelAuth
from panel.server import PanelHandler
from panel.mjpeg_stream import StreamGate
from panel.h264_proxy import purpose_bound_key

FRAGMENTS=b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x08moov\x00\x00\x00\x08moof\x00\x00\x00\x08mdat"

class Response:
    def __init__(self):self.data=FRAGMENTS
    def read1(self,n):
        data=self.data[:n];self.data=self.data[n:];return data
    def close(self):pass

class Connection:
    def close(self):pass

class H264PortalHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        file=root/"key"
        file.write_text("a-long-test-only-auth-password-not-real")
        file.chmod(0o600)
        self.http=ThreadingHTTPServer(("127.0.0.1",0),PanelHandler)
        self.http.panel_auth=PanelAuth(file)
        self.http.h264_gate=StreamGate(1)
        self.http.registry_path=root/"registry.db"
        with sqlite3.connect(self.http.registry_path) as db:
            db.execute("CREATE TABLE routes(device TEXT PRIMARY KEY,port INTEGER,upstream_key TEXT)")
            db.execute("INSERT INTO routes VALUES (?,?,?)",("lunex",23789,"demo-upstream-credential-padding-123456789"))
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()
        self.auth="Basic "+base64.b64encode(b"admin:a-long-test-only-auth-password-not-real").decode()

    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join(3)
        self.tmp.cleanup()

    def get(self,headers=None,path="/api/live/h264/lunex/balanced.mp4"):
        conn=HTTPConnection("127.0.0.1",self.http.server_port,timeout=5)
        conn.request("GET",path,headers=headers or {})
        response=conn.getresponse()
        value=response.status,response.getheader("Content-Type",""),response.read()
        conn.close()
        return value

    def test_read_only_stream_requires_browser_header_and_valid_origin(self):
        from panel import server
        with patch.object(server,"open_h264_stream",return_value=(Connection(),Response())) as upstream:
            url="/api/live/h264/lunex/balanced.mp4"
            self.assertEqual(self.get()[0],401)
            self.assertEqual(self.get({"Authorization":self.auth})[0],403)
            self.assertEqual(self.get({"Authorization":self.auth,"X-LunexPC-Video":"active",
                                       "Sec-Fetch-Site":"cross-site"})[0],403)
            self.assertEqual(self.get({"Authorization":self.auth,"X-LunexPC-Video":"active",
                                       "Origin":"https://evil.example"})[0],403)
            status,kind,body=self.get({"Authorization":self.auth,"X-LunexPC-Video":"active",
                                        "Sec-Fetch-Site":"same-origin"})
            self.assertEqual(status,200)
            self.assertTrue(kind.startswith("video/mp4"))
            self.assertEqual(body,FRAGMENTS)
            self.assertEqual(upstream.call_count,1)
            self.assertEqual(self.get({"Authorization":self.auth,"X-LunexPC-Video":"active"},
                                      path=url+"?tracking=1")[0],404)

    def test_over_capacity_stream_is_denied(self):
        self.http.h264_gate.acquire()
        try:
            self.assertEqual(self.get({"Authorization":self.auth,"X-LunexPC-Video":"active"})[0],503)
        finally:
            self.http.h264_gate.release()

if __name__=="__main__":
    unittest.main()
