"""Read-only local dashboard for LunexPCControl. No control endpoints.

The backend displays only sanitized counts, fixed-category audit records,
and agent presence (locally registered, not necessarily online). It never
exposes gateway secrets, client tokens, raw log lines, or system shell.
The dashboard must be accessed via an authenticated private transport.
"""
from __future__ import annotations

import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from panel.auth import PanelAuth
from panel.monitor_html import monitor_page
from panel.portal_html import devices_page, live_page
from panel.live_view import LiveFrameService, LiveError, probe_devices
from panel.mjpeg_stream import StreamGate, StreamBusy, stream_frames, content_type
from server.screen_history import ScreenHistory
import re

GATEWAY_REGISTRY = Path(os.environ.get(
    "LUNEXPC_REGISTRY", "/var/lib/lunexpc-gateway/registry.sqlite"))
AUDIT_LOG = Path(os.environ.get(
    "LUNEXPC_AUDIT", "/var/log/lunexpc-gateway/audit.jsonl"))
ALLOWED_EVENTS = frozenset({
    "allowed", "blocked", "invalid", "unauthorized",
    "rate_limited", "upstream_error", "over_capacity",
})
ALLOWED_METHODS = frozenset({
    "initialize", "notification", "ping", "list",
    "call_screenshot", "call_status", "denied", "other",
})


def registry_snapshot(db_path: Path) -> dict:
    if not db_path.exists():
        return {"devices": 0, "active_clients": 0, "registered_devices": [],
                "registry_ready": False}
    uri = f"file:{db_path}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=2) as conn:
        devices = [str(row[0]) for row in conn.execute(
            "SELECT device FROM routes ORDER BY device LIMIT 50")]
        total = conn.execute("SELECT count(*) FROM routes").fetchone()[0]
        clients = conn.execute(
            "SELECT count(*) FROM clients WHERE allowed=1").fetchone()[0]
    # Device IDs can be user-supplied. Return only counts, no identifiers.
    return {"devices": total, "active_clients": clients,
            "registered_devices": [], "registry_ready": True}


def audit_snapshot(path: Path, count: int = 12) -> list[dict]:
    if not path.is_file():
        return []
    # Read at most the last 64 KiB. Avoid unbounded memory on large logs.
    with path.open("rb") as file:
        file.seek(0, 2)
        end = file.tell()
        file.seek(max(0, end - 65536))
        chunk = file.read(65536)
    lines = chunk.splitlines()[-count:]
    events = []
    for line in lines:
        try:
            entry = json.loads(line)
            if entry.get("event") not in ALLOWED_EVENTS:
                continue
            if entry.get("method") not in ALLOWED_METHODS:
                continue
            status = entry.get("status")
            if type(status) is not int or not 100 <= status <= 599:
                continue
            # ISO time is validated only to prevent injecting arbitrary strings.
            timestamp = entry.get("ts")
            if not isinstance(timestamp, str) or len(timestamp) > 48:
                continue
            if not timestamp[:4].isdigit() or "T" not in timestamp:
                continue
            events.append({
                "time": timestamp, "event": entry["event"],
                "method": entry["method"], "status": status,
            })
        except (ValueError, TypeError, AttributeError):
            continue
    return events


def dashboard_data(registry_path=GATEWAY_REGISTRY, audit_path=AUDIT_LOG) -> dict:
    data = registry_snapshot(Path(registry_path))
    data["audit"] = audit_snapshot(Path(audit_path))
    data["mode"] = "read-only"
    data["public_mcp"] = "disabled-by-default"
    return data


def html_page() -> bytes:
    # Responsive and dependency-free: everything stays in the GitHub repo.
    return """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Lunex PC Control | Панель</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:#0b1018;color:#eef4ff}
.wrap{max-width:1080px;margin:auto;padding:30px 18px}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
h1{font-size:clamp(24px,4vw,34px);letter-spacing:-.8px;margin:0}
.sub{color:#9eafc5;margin:8px 0 28px}
.brand{font-size:13px;color:#93d8e8;letter-spacing:.17em;text-transform:uppercase}
.pill{border:1px solid #33455d;border-radius:30px;padding:8px 14px;color:#b8d0e6;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:22px 0}
.card{background:#141f2d;border:1px solid #233649;border-radius:18px;padding:22px}
.label{color:#9cb0c5;font-size:13px}.value{font-size:34px;font-weight:700;margin-top:10px}
h2{font-size:18px}.note{color:#99adbf;font-size:14px;line-height:1.6}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:12px;border-bottom:1px solid #2b394a;font-size:13px}
th{color:#9fb2c9;font-weight:500}td{overflow-wrap:anywhere}
.status{color:#78d3ac}
footer{margin-top:32px;color:#8498ab;font-size:12px}
@media(max-width:620px){.grid{grid-template-columns:1fr}.card{padding:18px}}
</style></head><body><div class="wrap">
<header><div><div class="brand">Lunex • PC Control</div><h1>Центр управления</h1></div>
<div class="pill">🔒 Защищённый доступ</div></header>
<p class="sub">Центр управления и мониторинга ИИ.</p>
<nav style="display:flex;gap:9px;margin-bottom:20px;flex-wrap:wrap">
<a style="color:#b6ddff;padding:10px 15px;border:1px solid #30475c;border-radius:12px" href="/portalmcp/">Обзор</a>
<a style="color:#b6ddff;padding:10px 15px;border:1px solid #30475c;border-radius:12px" href="/portalmcp/devices">Устройства</a>
<a style="color:#b6ddff;padding:10px 15px;border:1px solid #30475c;border-radius:12px" href="/portalmcp/live">Live View</a>
<a style="color:#b6ddff;padding:10px 15px;border:1px solid #30475c;border-radius:12px" href="/portalmcp/monitor">История</a>
</nav>
<section class="grid">
<div class="card"><div class="label">Зарегистрированные устройства</div>
<div class="value" id="devices">...</div></div>
<div class="card"><div class="label">Активные разрешения клиентов</div>
<div class="value" id="clients">...</div></div>
<div class="card"><div class="label">Устройств в сети</div>
<div class="value status" id="online">...</div></div>
</section>
<section class="card"><h2>Последние события</h2>
<p class="note">В журнале нет паролей, скриншотов и текстов команд.</p>
<div style="overflow-x:auto"><table><thead><tr><th>Время (UTC)</th>
<th>Событие</th><th>Операция</th><th>HTTP</th></tr></thead>
<tbody id="events"><tr><td colspan="4">Загрузка...</td></tr></tbody></table></div></section>
<section class="card" style="margin-top:16px"><h2>Как это работает</h2>
<p class="note">Windows подключается к VPS по исходящему SSH-туннелю.
В шлюзе разрешены только снимок экрана с подтверждением пользователя
и проверка состояния управления. Добавление устройств и обновления
будут отдельными защищёнными действиями после проверки прав.</p></section>
<footer>Источники: локальная база и обезличенный журнал LunexPCControl.
Панель не предоставляет команды управления.</footer>
</div><script>
async function load(){
 const response=await fetch('/portalmcp/api/status',{cache:'no-store'});
 if(!response.ok)throw Error('Невозможно загрузить статистику');
 const data=await response.json();
 document.getElementById('devices').textContent=data.devices;
 document.getElementById('clients').textContent=data.active_clients;
 try{
   const devicesResponse=await fetch('/portalmcp/api/devices',{cache:'no-store'});
   if(devicesResponse.ok){
     const devices=await devicesResponse.json();
     document.getElementById('online').textContent=devices.devices.filter(x=>x.tunnel_online).length;
   }else{document.getElementById('online').textContent='—'}
 }catch(e){document.getElementById('online').textContent='—'}
 const root=document.getElementById('events');root.replaceChildren();
 if(!data.audit.length){const r=root.insertRow();const c=r.insertCell();
   c.colSpan=4;c.textContent='Событий пока нет';return}
 for(const e of data.audit){
  const tr=root.insertRow();
  for(const k of ['time','event','method','status']){
   const td=tr.insertCell();td.textContent=String(e[k])
  }
 }
}
load().catch(()=>{document.getElementById('events').textContent='Ошибка загрузки'});
setInterval(()=>load().catch(()=>{}),10000)
</script></body></html>""".encode("utf-8")


class PanelHandler(BaseHTTPRequestHandler):
    server_version = "LunexPC-Panel"
    sys_version = ""

    def _trusted_host(self, mutation=False):
        if len(self.headers.get_all("Host", [])) != 1:
            return False
        host = self.headers.get("Host", "")
        port = self.server.server_port
        permitted = {f"127.0.0.1:{port}", f"localhost:{port}"}
        private_proxy_host = os.environ.get("LUNEXPC_PANEL_ALLOWED_HOST", "").strip()
        if private_proxy_host:
            permitted.add(private_proxy_host)
        permitted.add("rikagro.ru")
        if host not in permitted:
            return False
        origin = self.headers.get("Origin")
        if mutation:
            scheme = "https://" if host in (private_proxy_host, "rikagro.ru") else "http://"
            return len(self.headers.get_all("Origin", [])) == 1 and origin == scheme + host
        return not origin

    def _authenticated(self):
        auth = getattr(self.server, "panel_auth", None)
        if auth is None:
            self._write(503, b"Panel authentication not configured", "text/plain")
            return False
        if len(self.headers.get_all("Authorization", [])) != 1 or not auth.verify(self.headers.get("Authorization")):
            self._write(401, b"Access denied", "text/plain")
            return False
        return True

    def _ui(self, markup):
        """Preserve private Termalin root URLs; public Nginx uses /portalmcp/."""
        if self.headers.get("Host") == "rikagro.ru":
            return markup
        return markup.replace(b"/portalmcp/", b"/")

    def _screens(self):
        return getattr(self.server, "screen_history", None)

    def _registry(self):
        return getattr(self.server, "registry_path", GATEWAY_REGISTRY)

    def do_GET(self):
        if not self._trusted_host():
            self._write(403, b"Forbidden", "text/plain")
            return
        if not self._authenticated():
            return
        parsed = urlsplit(self.path)
        if parsed.fragment or (parsed.query and parsed.path not in ("/", "/devices", "/live", "/monitor")):
            self._write(404, b"Not found", "text/plain")
            return
        # Preserve existing private Termalin routes and proxy-public /portalmcp/.
        # Nginx removes the prefix before forwarding; no path alias is needed.
        if parsed.path == "/":
            self._write(200, self._ui(html_page()), "text/html; charset=utf-8")
        elif parsed.path == "/monitor":
            self._write(200, self._ui(monitor_page()), "text/html; charset=utf-8")
        elif parsed.path == "/devices":
            self._write(200, self._ui(devices_page()), "text/html; charset=utf-8")
        elif parsed.path == "/live":
            self._write(200, self._ui(live_page()), "text/html; charset=utf-8")
        elif parsed.path == "/api/devices":
            try:
                devices = probe_devices(self._registry())
                result = json.dumps({"devices":devices, "total":len(devices)},
                                    separators=(",",":")).encode()
                self._write(200, result, "application/json; charset=utf-8")
            except (OSError,sqlite3.Error,ValueError):
                self._write(503, b'{"error":"device status unavailable"}', "application/json")
        elif re.fullmatch(r"/api/live/stream/[A-Za-z0-9_-]{1,64}/(data|balanced|quality)\.mjpg",
                          parsed.path):
            self._serve_mjpeg(parsed.path)
        elif re.fullmatch(r"/api/live/frame/[A-Za-z0-9_-]{1,64}/(data|balanced|quality)\.jpg",
                          parsed.path):
            if (len(self.headers.get_all("X-LunexPC-LiveView", [])) != 1
                    or self.headers.get("X-LunexPC-LiveView") != "active"):
                self._write(403, b"Live View requires explicit request", "text/plain")
                return
            fragment = parsed.path.split("/")
            device = fragment[4]
            profile = fragment[5][:-4]
            viewer = getattr(self.server,"live_view",None)
            if viewer is None:
                self._write(503, b"Viewer unavailable", "text/plain")
                return
            try:
                jpeg, etag, captured = viewer.frame(device, profile)
                self._write(200, jpeg, "image/jpeg")
            except LiveError:
                self._write(503, b"Screen unavailable", "text/plain")
            except (OSError,sqlite3.Error):
                self._write(503, b"Viewer unavailable", "text/plain")
        elif parsed.path == "/api/screens":
            try:
                store = self._screens()
                if store is None:
                    raise OSError("history unavailable")
                payload = json.dumps({
                    "items":store.list(),
                    "settings":store.settings(),
                    "poll_interval_ms":3000
                }, separators=(",",":")).encode()
                self._write(200,payload,"application/json; charset=utf-8")
            except (OSError,sqlite3.Error,ValueError):
                self._write(503,b'{"error":"history unavailable"}',"application/json")
        elif re.fullmatch(r"/api/screens/[0-9a-f]{32}\.png",parsed.path):
            identifier=parsed.path.split("/")[-1][:-4]
            try:
                store=self._screens()
                image=store.image(identifier) if store is not None else None
                if image is None:
                    self._write(404,b"Not found","text/plain")
                else:
                    self._write(200,image,"image/png")
            except Exception:
                self._write(503,b"Image unavailable","text/plain")
        elif parsed.path == "/api/status":
            try:
                body = json.dumps(dashboard_data(),
                                  separators=(",", ":")).encode("utf-8")
                self._write(200, body, "application/json; charset=utf-8")
            except (OSError, sqlite3.Error):
                self._write(503, b'{"error":"unavailable"}', "application/json")
        else:
            self._write(404, b"Not found", "text/plain")

    def _serve_mjpeg(self, path):
        # A streaming URL can be used as an img.src. Browser Basic auth is
        # still mandatory; the special header only exists on the JPEG fallback.
        viewer=getattr(self.server,"live_view",None)
        gate=getattr(self.server,"stream_gate",None)
        if viewer is None or gate is None:
            self._write(503,b"Stream unavailable","text/plain")
            return
        parts=path.split("/")
        device=parts[4]
        profile=parts[5][:-5]
        try:
            gate.acquire()
        except StreamBusy:
            self._write(503,b"Too many viewers","text/plain")
            return
        try:
            try:
                # Check the registered device status before committing to an
                # indefinite response, but never disclose the device key.
                registered=any(d["id"]==device for d in probe_devices(self._registry()))
                if not registered:
                    self._write(404,b"Device not registered","text/plain")
                    return
            except (OSError,sqlite3.Error):
                self._write(503,b"Connection unavailable","text/plain")
                return
            self.send_response(200)
            self.send_header("Content-Type",content_type())
            self.send_header("Cache-Control","private, no-store, max-age=0")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Referrer-Policy","no-referrer")
            self.send_header("X-Robots-Tag","noindex, nofollow")
            self.send_header("X-Accel-Buffering","no")
            self.send_header("Connection","close")
            self.end_headers()
            self.close_connection=True
            for frame in stream_frames(viewer,device,profile):
                try:
                    self.wfile.write(frame)
                    self.wfile.flush()
                except (BrokenPipeError,ConnectionResetError,TimeoutError,OSError):
                    break
        finally:
            gate.release()

    def do_POST(self):
        if not self._trusted_host(mutation=True):
            self._write(403,b"Forbidden","text/plain")
            return
        if not self._authenticated():
            return
        target=urlsplit(self.path)
        actions={"/api/screens/settings":"screens-settings",
                 "/api/screens/clear":"screens-clear"}
        action=actions.get(target.path)
        if action is None or target.query:
            self._write(405,b"Operation not supported","text/plain")
            return
        if (len(self.headers.get_all("X-LunexPC-Action",[])) != 1
                or self.headers.get("X-LunexPC-Action") != action):
            self._write(403,b"Missing action authorization","text/plain")
            return
        if self.headers.get("Content-Type") != "application/json":
            self._write(415,b"Expected JSON","text/plain")
            return
        lengths=self.headers.get_all("Content-Length",[])
        if len(lengths)!=1 or not lengths[0].isdecimal() or self.headers.get("Transfer-Encoding"):
            self._write(400,b"Invalid request framing","text/plain")
            return
        size=int(lengths[0])
        if size>1024:
            self._write(413,b"Request too large","text/plain")
            return
        try:
            payload=json.loads(self.rfile.read(size))
            if not isinstance(payload,dict):
                raise ValueError("invalid body")
            store=self._screens()
            if store is None:
                raise OSError("history unavailable")
            if action=="screens-settings":
                if set(payload)!={"retention_hours","max_count"}:
                    raise ValueError("invalid settings")
                result=store.configure(payload["retention_hours"],payload["max_count"])
            else:
                if payload:
                    raise ValueError("clear requires empty body")
                store.clear()
                result={"cleared":True}
        except (ValueError,TypeError,UnicodeDecodeError):
            self._write(400,b"Invalid settings","text/plain")
            return
        except (OSError,sqlite3.Error):
            self._write(503,b"Storage unavailable","text/plain")
            return
        self._write(200,json.dumps(result,separators=(",",":")).encode(),"application/json")

    def do_PUT(self):
        self.do_POST()

    def do_DELETE(self):
        self.do_POST()

    def _write(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if status == 401:
            self.send_header("WWW-Authenticate", 'Basic realm="LunexPCControl Panel", charset="UTF-8"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'unsafe-inline'; "
                         "style-src 'unsafe-inline'; img-src 'self'; "
                         "connect-src 'self'; frame-ancestors 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Never log requested URLs or user-supplied headers.
        return


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18881)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--auth-file", required=True)
    parser.add_argument("--screens-dir",default="/var/lib/lunexpc-gateway/screens")
    args = parser.parse_args()
    if args.bind != "127.0.0.1":
        raise ValueError("panel must bind only to localhost")
    auth = PanelAuth(args.auth_file)
    if not auth.configured:
        raise ValueError("panel authentication is required")
    server = ThreadingHTTPServer((args.bind, args.port), PanelHandler)
    server.panel_auth = auth
    server.registry_path = GATEWAY_REGISTRY
    server.live_view = LiveFrameService(GATEWAY_REGISTRY)
    server.stream_gate = StreamGate()
    server.screen_history = ScreenHistory(args.screens_dir)
    server.serve_forever()


if __name__ == "__main__":
    main()
