import base64
import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest

from panel.auth import PanelAuth
from panel.live_view import LiveFrameService
from panel.mjpeg_stream import StreamGate, StreamBusy, content_type, stream_frames
from panel.server import PanelHandler
from tests.test_screen_history import sample_png


class MockClock:
    def __init__(self): self.value=0.
    def __call__(self): return self.value
    def sleep(self,delta): self.value+=delta


class MJPEGStreamTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.db=root/"registry.db"
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE routes(device TEXT PRIMARY KEY,port INTEGER,upstream_key TEXT)")
            db.execute("INSERT INTO routes VALUES (?,?,?)",("lunex",23789,"demo-credential-with-sufficient-length-123456789"))
        cred=root/"auth.key";cred.write_text("safe-demo-password-not-for-production");cred.chmod(0o600)
        self.clock=MockClock()
        self.calls=[]
        def capture(port,key):
            self.calls.append(port)
            return sample_png()
        self.viewer=LiveFrameService(self.db,capture=capture,clock=self.clock)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),PanelHandler)
        self.server.panel_auth=PanelAuth(cred)
        self.server.registry_path=self.db
        self.server.live_view=self.viewer
        self.server.stream_gate=StreamGate()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        credential=base64.b64encode(b"admin:safe-demo-password-not-for-production").decode()
        self.auth={"Authorization":"Basic "+credential}
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(3)
        self.temp.cleanup()
    def get(self,path,authorized=True,limit=1600):
        c=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=6)
        c.request("GET",path,headers=self.auth if authorized else {})
        r=c.getresponse();status=r.status;ctype=r.getheader("Content-Type","")
        # Never consume an entire live response in an HTTP test.
        body=r.read(limit) if status==200 and "multipart" in ctype else r.read()
        c.close()
        return status,ctype,body

    def test_stream_is_auth_only_and_has_valid_multipart_jpeg(self):
        route="/api/live/stream/lunex/balanced.mjpg"
        self.assertEqual(self.get(route,False)[0],401)
        self.assertEqual(self.calls,[])
        self.assertEqual(self.get("/api/live/stream/../etc/passwd")[0],404)
        self.assertEqual(self.get("/api/live/stream/lunex/bad.mjpg")[0],404)
        self.assertEqual(self.get("/api/live/stream/nope/balanced.mjpg")[0],404)
        status,media,data=self.get(route)
        self.assertEqual(status,200)
        self.assertEqual(media,content_type())
        self.assertIn(b"Content-Type: image/jpeg",data)
        self.assertIn(b"\xff\xd8\xff",data)
        self.assertTrue(self.calls)
    def test_global_viewer_limit_and_cleanup(self):
        gate=StreamGate(1)
        gate.acquire()
        with self.assertRaises(StreamBusy):
            gate.acquire()
        gate.release()
        gate.acquire()
        gate.release()
    def test_bounds_end_and_no_capture_until_stream_consumed(self):
        clock=MockClock()
        viewer=LiveFrameService(self.db,capture=lambda p,k:sample_png(),clock=clock)
        iterator=stream_frames(viewer,"lunex","balanced",
                               clock=clock,sleep=clock.sleep,max_seconds=2.7)
        self.assertEqual(clock.value,0)
        parts=list(iterator)
        self.assertGreaterEqual(len(parts),2)
        self.assertLessEqual(len(parts),3)
        self.assertLessEqual(clock.value,3.5)
        self.assertTrue(all(b"image/jpeg" in part for part in parts))
        with self.assertRaises(Exception):
            list(stream_frames(viewer,"lunex","balanced",max_seconds=9999))
    def test_no_unauthenticated_live_frame_side_effects(self):
        route="/api/live/stream/lunex/data.mjpg"
        self.assertEqual(self.get(route,False)[0],401)
        self.assertEqual(self.calls,[])


if __name__=="__main__":unittest.main()
