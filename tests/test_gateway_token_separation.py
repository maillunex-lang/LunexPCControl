import http.client
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from server.gateway import GatewayRegistry, make_handler

class Upstream(BaseHTTPRequestHandler):
    def do_POST(self):
        self.server.auth_seen = self.headers.get('Authorization')
        body = b'{"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"Screenshot"}]}}'
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*args): pass

class TestGatewaySeparation(unittest.TestCase):
    def test_upstream_receives_only_its_credential(self):
        with tempfile.TemporaryDirectory() as folder:
            upstream=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
            thread=threading.Thread(target=upstream.serve_forever, daemon=True)
            thread.start()
            registry=GatewayRegistry(os.path.join(folder,'auth.db'))
            with __import__('sqlite3').connect(registry.path) as db:
                db.execute('INSERT INTO routes VALUES (?,?,?)',('pc',upstream.server_port,'upstream-token-'+'x'*30))
            client_key=registry.create_client('pc')
            gateway=ThreadingHTTPServer(('127.0.0.1',0), make_handler(registry))
            t2=threading.Thread(target=gateway.serve_forever,daemon=True);t2.start()
            try:
                def query(token):
                    c=http.client.HTTPConnection('127.0.0.1',gateway.server_port,timeout=3)
                    c.request('POST','/devices/pc/mcp',b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"Screenshot","arguments":{}}}',{'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                    response=c.getresponse();status=response.status; data=response.read();c.close();return status,data
                self.assertEqual(query('wrong')[0],403)
                status,data=query(client_key)
                self.assertEqual(status,200)
                self.assertIn(b'Screenshot',data)
                self.assertEqual(upstream.auth_seen,'Bearer upstream-token-'+'x'*30)
                self.assertNotIn(client_key,upstream.auth_seen)
                registry.revoke_client(client_key)
                self.assertEqual(query(client_key)[0],403)
            finally:
                gateway.shutdown();gateway.server_close()
                upstream.shutdown();upstream.server_close()
