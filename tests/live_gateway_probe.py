"""Manually run a real MCP protocol smoke test through the loopback gateway.

Never dumps MCP responses, PNG bytes, client tokens or upstream secrets.
This is NOT run by unittest discovery.
"""
import argparse
import base64
import http.client
import json
from pathlib import Path

PNG=b'\x89PNG\r\n\x1a\n'
MAX=16*1024*1024

def request(method, token, session=None, payload=None, port=18880):
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=25)
    headers={'Authorization':'Bearer '+token,'Accept':'application/json, text/event-stream',
             'MCP-Protocol-Version':'2025-06-18'}
    if session:headers['MCP-Session-Id']=session
    if payload is not None:
        headers['Content-Type']='application/json'
    try:
        c.request('POST','/devices/lunexrdp/mcp',
                  body=json.dumps(payload).encode() if payload is not None else b'',
                  headers=headers)
        r=c.getresponse()
        status=r.status
        response_session=r.getheader('Mcp-Session-Id')
        media=r.getheader('Content-Type','')
        # SSE: read until a JSON data event is complete; do not buffer forever.
        if 'text/event-stream' in media:
            content=bytearray()
            while len(content)<MAX:
                chunk=r.read1(65536)
                if not chunk:break
                content+=chunk
                if b'\n\n' in content or b'\r\n\r\n' in content:break
            raw=bytes(content)
            events=raw.decode('utf-8','replace').replace('\r\n','\n').split('\n\n')
            frames=[]
            for event in events:
                data='\n'.join(line[5:].lstrip(' ') for line in event.split('\n') if line.startswith('data:'))
                if data:
                    try:frames.append(json.loads(data))
                    except ValueError:pass
            result=frames[-1] if frames else {}
        else:
            raw=r.read(MAX+1)
            if len(raw)>MAX:raise RuntimeError('MCP response too large')
            result=json.loads(raw) if raw else {}
        return status,response_session,result
    finally:
        c.close()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--token-file',type=Path,required=True)
    ap.add_argument('--port',type=int,default=18880)
    ap.add_argument('--screenshot',action='store_true')
    args=ap.parse_args()
    token=args.token_file.read_text().strip()
    if len(token)<24:raise RuntimeError('Invalid client token file')
    status,_,_=request('POST','deliberately-invalid',payload={
        'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}},port=args.port)
    if status != 403:raise RuntimeError(f'Unauthorized gateway access was not rejected ({status})')
    print('Gateway correctly rejected invalid client token')
    status,sess,initialized=request('POST',token,payload={
       'jsonrpc':'2.0','id':1,'method':'initialize','params':{
          'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'lunexpc-test','version':'0.1'}
       }},port=args.port)
    if status!=200 or initialized.get('id')!=1 or 'result' not in initialized:
       raise RuntimeError(f'MCP initialize not completed: HTTP {status}')
    print('MCP initialize OK; session assigned:',bool(sess))
    status,_,listing=request('POST',token,session=sess,payload={
       'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}},port=args.port)
    if status!=200 or listing.get('id')!=2:
       raise RuntimeError(f'MCP tools/list not completed: HTTP {status}')
    names={x['name'] for x in listing.get('result',{}).get('tools',[])}
    if names != {'Screenshot','ControlStatus'}:
       raise RuntimeError('Unexpected MCP tool set')
    print('MCP allowed tools verified: Screenshot + ControlStatus')
    if args.screenshot:
       status,_,out=request('POST',token,session=sess,payload={
          'jsonrpc':'2.0','id':3,'method':'tools/call',
          'params':{'name':'Screenshot','arguments':{}}},port=args.port)
       if status!=200 or out.get('id')!=3:
          raise RuntimeError(f'MCP Screenshot tool call failed: HTTP {status}')
       result=out.get('result',{})
       if result.get('isError'):raise RuntimeError('MCP Screenshot returned tool error')
       images=[x for x in result.get('content',[]) if x.get('type')=='image']
       if not images:raise RuntimeError('No image content returned by MCP')
       count=0
       for item in images:
          raw=base64.b64decode(item['data'],validate=True)
          if not raw.startswith(PNG):raise RuntimeError('Invalid PNG screenshot')
          count+=len(raw)
       print(f'END-TO-END-MCP-SCREENSHOT-PASS images={len(images)} bytes={count}')
    else:
       print('END-TO-END-MCP-TOOLS-PASS (no screenshot requested)')
if __name__=='__main__':
    main()
