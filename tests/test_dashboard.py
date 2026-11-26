from pathlib import Path
import json
import base64
import os
import sqlite3
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from panel.server import PanelHandler, dashboard_data, html_page
from panel.auth import PanelAuth

class DashboardTests(unittest.TestCase):
    def test_no_secret_data(self):
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/"registry.db"
            with sqlite3.connect(db) as conn:
                conn.executescript("""
                create table clients(device text,token_digest text,allowed integer);
                create table routes(device text,port integer,upstream_key text);
                insert into clients values('some-private-device','client-digest',1);
                insert into routes values('some-private-device',23789,'secret-key');
                """)
            log=Path(temp)/"events.jsonl"
            log.write_text(json.dumps({"ts":"2026-11-26T08:00:00+00:00",
                                       "event":"allowed","method":"call_screenshot",
                                       "status":200,"secret":"must-not-leak"})+"\n")
            result=dashboard_data(db,log)
            raw=json.dumps(result)
            self.assertEqual(result["devices"],1)
            self.assertEqual(result["active_clients"],1)
            for secret in ("some-private-device","client-digest","secret-key","must-not-leak"):
                self.assertNotIn(secret,raw)
    def test_panel_is_local_and_readonly(self):
        service=(Path(__file__).resolve().parents[1]/"deploy/lunexpc-panel.service").read_text()
        self.assertIn("--bind 127.0.0.1 --port 18881",service)
        self.assertIn("--auth-file /var/lib/lunexpc-gateway/panel-auth.key",service)
        page=html_page().decode()
        self.assertIn("Центр управления",page)
        self.assertNotIn("eval(",page)
    def test_http_endpoints(self):
        server=ThreadingHTTPServer(("127.0.0.1",0),PanelHandler)
        with tempfile.TemporaryDirectory() as d:
            key=Path(d)/'auth.key'
            key.write_text('a-long-private-demo-token-not-for-production')
            key.chmod(0o600)
            server.panel_auth=PanelAuth(key)
            self._exercise_http(server)

    def _exercise_http(self,server):
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            conn=HTTPConnection("127.0.0.1",server.server_port,timeout=5)
            conn.request("GET","/")
            result=conn.getresponse()
            self.assertEqual(result.status,401)
            self.assertIn("Basic", result.getheader("WWW-Authenticate",""))
            result.read()
            token=base64.b64encode(b'admin:a-long-private-demo-token-not-for-production').decode()
            conn.request("GET","/",headers={"Authorization":"Basic "+token})
            result=conn.getresponse()
            self.assertEqual(result.status,200)
            self.assertEqual(result.getheader("Cache-Control"),"no-store")
            self.assertIn(b"Lunex",result.read())
            conn.request("POST","/api/status")
            result=conn.getresponse()
            self.assertEqual(result.status,405)
            result.read()
            conn.request("GET","/random",headers={"Authorization":"Basic "+token})
            result=conn.getresponse()
            self.assertEqual(result.status,404)
            result.read()
            conn.request("GET","/api/status",headers={"Host":"attacker.example"})
            result=conn.getresponse()
            self.assertEqual(result.status,403)
            result.read()
            conn.request("GET","/api/status",headers={"Origin":"https://attacker.example"})
            result=conn.getresponse()
            self.assertEqual(result.status,403)
            result.read()
            conn.close()
        finally:
            server.shutdown();server.server_close()
