"""Real JSON-RPC lifecycle through the authenticated gateway and local MCP simulator."""
import http.client
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from server.gateway import GatewayRegistry, make_handler

class MCPProtocol(BaseHTTPRequestHandler):
    def do_POST(self):
        self.server.auth = self.headers.get('Authorization')
        self.server.mcp_version = self.headers.get('Mcp-Protocol-Version')
        raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        obj = json.loads(raw)
        method = obj.get('method')
        if method == 'initialize':
            result = {'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'test-windows-agent','version':'0.0'}}
        elif method == 'tools/list':
            result = {'tools':[{'name':'Screenshot','description':'read-only test screenshot'}]}
        elif method == 'tools/call':
            result = {'content':[{'type':'image','mimeType':'image/png','data':'iVBORw0KGgo='}], 'isError':False}
        else:
            result = {}
        body = json.dumps({'jsonrpc':'2.0','id':obj.get('id'),'result':result}).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Mcp-Session-Id','test-session')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*args):pass

class TestGatewayLiveProtocol(unittest.TestCase):
    def test_real_mcp_jsonrpc_sequence_and_revocation(self):
        with tempfile.TemporaryDirectory() as folder:
            upstream=ThreadingHTTPServer(('127.0.0.1',0),MCPProtocol)
            gateway=None
            threading.Thread(target=upstream.serve_forever,daemon=True).start()
            try:
                registry=GatewayRegistry(os.path.join(folder,'auth.db'))
                with sqlite3.connect(registry.path) as db:
                    db.execute('INSERT INTO routes VALUES (?,?,?)',('pc',upstream.server_port,'agent-only-'+'y'*35))
                token=registry.create_client('pc')
                gateway=ThreadingHTTPServer(('127.0.0.1',0),make_handler(registry))
                threading.Thread(target=gateway.serve_forever,daemon=True).start()
                def rpc(method, request_id=1, params=None):
                    conn=http.client.HTTPConnection('127.0.0.1',gateway.server_port,timeout=5)
                    data=json.dumps({'jsonrpc':'2.0','method':method,'id':request_id,'params':params or {}}).encode()
                    conn.request('POST','/devices/pc/mcp',body=data,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json, text/event-stream','Mcp-Protocol-Version':'2025-06-18'})
                    resp=conn.getresponse();status=resp.status;payload=resp.read();headers=dict(resp.getheaders());conn.close()
                    return status,json.loads(payload) if status==200 else {},headers
                status,obj,headers=rpc('initialize')
                self.assertEqual(status,200)
                self.assertEqual(obj['result']['serverInfo']['name'],'LunexPCControl')
                self.assertEqual(headers.get('Mcp-Session-Id'),'test-session')
                self.assertEqual(upstream.auth,'Bearer agent-only-'+'y'*35)
                status,obj,_=rpc('tools/list',2)
                self.assertEqual(obj['result']['tools'][0]['name'],'Screenshot')
                status,obj,_=rpc('tools/call',3,{'name':'Screenshot','arguments':{}})
                self.assertEqual(obj['result']['content'][0]['type'],'image')
                self.assertEqual(obj['result']['content'][0]['mimeType'],'image/png')
                registry.revoke_device('pc')
                self.assertEqual(rpc('tools/list',4)[0],403)
            finally:
                if gateway is not None: gateway.shutdown();gateway.server_close()
                upstream.shutdown();upstream.server_close()
