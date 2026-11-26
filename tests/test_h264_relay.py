import sqlite3
import tempfile
from pathlib import Path
import unittest

from agent.windows.h264_agent import derived_video_key
from panel.h264_proxy import purpose_bound_key,video_route,open_h264_stream
from panel.live_view import LiveError
from panel.portal_html import live_page

class MockResponse:
    status=200
    def getheader(self,name,default=""):
        return "video/mp4" if name=="Content-Type" else default
class MockConnection:
    def __init__(self,host,port,timeout):
        self.target=(host,port)
        self.headers=None
    def request(self,method,path,headers):
        self.headers=headers
        self.route=(method,path)
    def getresponse(self):
        return MockResponse()
    def close(self):pass

class H264RelayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.registry=Path(self.tmp.name)/"registry.db"
        with sqlite3.connect(self.registry) as db:
            db.execute("CREATE TABLE routes(device TEXT PRIMARY KEY, port INTEGER, upstream_key TEXT)")
            db.execute("INSERT INTO routes VALUES (?,?,?)",("lunex",23789,"k"*48))
    def tearDown(self):
        self.tmp.cleanup()
    def test_video_key_is_purpose_bound(self):
        self.assertEqual(purpose_bound_key("k"*48),derived_video_key("k"*48))
        self.assertNotEqual(purpose_bound_key("k"*48),"k"*48)
    def test_validated_local_forward_and_profile(self):
        port,key=video_route(self.registry,"lunex","balanced")
        self.assertEqual(port,23790)
        self.assertEqual(len(key),64)
        self.assertRaises(LiveError,video_route,self.registry,"../etc","balanced")
        self.assertRaises(LiveError,video_route,self.registry,"lunex","arbitrary")
        self.assertRaises(LiveError,video_route,self.registry,"missing","balanced")
        conn,resp=open_h264_stream(self.registry,"lunex","balanced",MockConnection)
        self.assertEqual(conn.target,("127.0.0.1",23790))
        self.assertEqual(conn.route,("GET","/video/h264/balanced.mp4"))
        self.assertEqual(conn.headers["Host"],"127.0.0.1:18790")
        self.assertEqual(resp.status,200)
    def test_mse_ui_and_fallback_present(self):
        html=live_page()
        for element in (b'value="h264" selected',b'MediaSource',
                        b'addSourceBuffer',b'h264Loop',b'/api/live/h264/',
                        b"updateBuffer", b"mode='stream'", b"X-LunexPC-Video"):
            if element==b'blob:':
                continue
            self.assertIn(element,html)

if __name__=="__main__":
    unittest.main()
