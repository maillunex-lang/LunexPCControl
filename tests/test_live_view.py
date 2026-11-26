import io
import json
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from panel.live_view import (
    LiveFrameService, LiveError, PROFILE, device_routes, probe_devices,
    encode_preview, _parse_sse,
)
from tests.test_screen_history import sample_png


def registry(db):
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE routes(device TEXT PRIMARY KEY, port INTEGER, upstream_key TEXT)")
        connection.execute("INSERT INTO routes VALUES(?,?,?)", ("lunex", 23789, "example-key-do-not-use-in-production-123456789"))


class LiveViewTests(unittest.TestCase):
    def test_profiles_compress_and_enforce_image_limits(self):
        png = sample_png()
        for name in PROFILE:
            data = encode_preview(png, name)
            self.assertTrue(data.startswith(b"\xff\xd8\xff"))
            with Image.open(io.BytesIO(data)) as jpeg:
                self.assertEqual(jpeg.format, "JPEG")
                self.assertEqual(jpeg.size, (1, 1))
        with self.assertRaises(ValueError):
            encode_preview(png, "ultra")
        with self.assertRaises(LiveError):
            encode_preview(b"not an image")

    def test_status_checks_outbound_tunnel_without_ip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "reg.db"
            registry(path)
            self.assertEqual(device_routes(path), [("lunex", 23789)])
            result = probe_devices(path, connector=lambda p: p == 23789)
            self.assertEqual(result[0]["status"], "connected")
            self.assertTrue(result[0]["tunnel_online"])
            self.assertFalse(result[0]["ip_required"])
            self.assertEqual(probe_devices(path, connector=lambda p: False)[0]["status"], "offline")

    def test_on_demand_cache_and_global_throttle(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"reg.db"
            registry(path)
            current = [100.0]
            captured = []
            def capture(port, secret):
                captured.append((port, len(secret)))
                return sample_png()
            service = LiveFrameService(path, capture=capture, clock=lambda: current[0])
            self.assertEqual(captured, [])  # no background capture
            jpeg, tag, fresh = service.frame("lunex")
            self.assertTrue(fresh)
            self.assertTrue(jpeg.startswith(b"\xff\xd8"))
            self.assertEqual(len(tag), 32)
            self.assertEqual(len(captured), 1)
            cached, tag2, fresh2 = service.frame("lunex")
            self.assertFalse(fresh2)
            self.assertEqual(jpeg, cached)
            self.assertEqual(tag, tag2)
            with self.assertRaisesRegex(LiveError, "rate"):
                service.frame("lunex", "data")
            current[0] = 101.1
            self.assertTrue(service.frame("lunex", "data")[2])
            self.assertEqual(len(captured), 2)
            with self.assertRaises(LiveError):
                service.frame("../lunex")
            with self.assertRaises(LiveError):
                service.frame("lunex", "giant")
            with self.assertRaises(LiveError):
                service.frame("unregistered")
            self.assertEqual(len(captured), 2)

    def test_fail_closed_on_offline_agent(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"reg.db";registry(path)
            clock=lambda: 10.
            def fail(port, secret):
                raise LiveError("test upstream offline")
            viewer=LiveFrameService(path,capture=fail,clock=clock)
            with self.assertRaises(LiveError):
                viewer.frame("lunex")
            with self.assertRaises(LiveError):
                viewer.frame("lunex")

    def test_sse_parser_malformed_incomplete_and_valid(self):
        valid = {"jsonrpc": "2.0", "id":2, "result":{"content":[]}}
        event = b'event: message\r\ndata: ' + json.dumps(valid).encode() + b'\r\n\r\n'
        self.assertEqual(_parse_sse(event), valid)
        with self.assertRaises(LiveError):
            _parse_sse(b'data: not-json\n\n')
        with self.assertRaises(LiveError):
            _parse_sse(b'X'*(8*1024*1024+1))


if __name__=="__main__":
    unittest.main()
