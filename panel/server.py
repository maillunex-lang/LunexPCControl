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
<div class="pill">🔒 Только локальный доступ</div></header>
<p class="sub">Первая версия панели. Статистика доступна только для просмотра.</p>
<section class="grid">
<div class="card"><div class="label">Зарегистрированные устройства</div>
<div class="value" id="devices">...</div></div>
<div class="card"><div class="label">Активные разрешения клиентов</div>
<div class="value" id="clients">...</div></div>
<div class="card"><div class="label">Режим доступа</div>
<div class="value status" style="font-size:21px" id="mode">...</div></div>
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
 const response=await fetch('/api/status',{cache:'no-store'});
 if(!response.ok)throw Error('Невозможно загрузить статистику');
 const data=await response.json();
 document.getElementById('devices').textContent=data.devices;
 document.getElementById('clients').textContent=data.active_clients;
 document.getElementById('mode').textContent='Чтение';
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
load().catch(()=>{document.getElementById('events').textContent='Ошибка загрузки'})
</script></body></html>""".encode("utf-8")


class PanelHandler(BaseHTTPRequestHandler):
    server_version = "LunexPC-Panel"
    sys_version = ""

    def _trusted_host(self):
        host = self.headers.get("Host", "")
        port = self.server.server_port
        permitted = {f"127.0.0.1:{port}", f"localhost:{port}"}
        private_proxy_host = os.environ.get("LUNEXPC_PANEL_ALLOWED_HOST", "").strip()
        if private_proxy_host:
            permitted.add(private_proxy_host)
        return host in permitted and not self.headers.get("Origin")

    def do_GET(self):
        if not self._trusted_host():
            self._write(403, b"Forbidden", "text/plain")
            return
        # The entire dashboard is disabled until a credential is configured
        # in the server process. Never fall back to anonymous access.
        auth = getattr(self.server, "panel_auth", None)
        if auth is None:
            self._write(503, b'Panel authentication not configured', "text/plain")
            return
        if not auth.verify(self.headers.get("Authorization")):
            self._write(401, b'Access denied', "text/plain")
            return
        parsed = urlsplit(self.path)
        if parsed.query or parsed.fragment:
            self._write(404, b"Not found", "text/plain")
            return
        if parsed.path == "/":
            self._write(200, html_page(), "text/html; charset=utf-8")
        elif parsed.path == "/api/status":
            try:
                body = json.dumps(dashboard_data(),
                                  separators=(",", ":")).encode("utf-8")
                self._write(200, body, "application/json; charset=utf-8")
            except (OSError, sqlite3.Error):
                self._write(503, b'{"error":"unavailable"}', "application/json")
        else:
            self._write(404, b"Not found", "text/plain")

    def do_POST(self):
        self._write(405, b"Read-only", "text/plain")

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
                         "style-src 'unsafe-inline'; img-src 'none'; "
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
    args = parser.parse_args()
    if args.bind != "127.0.0.1":
        raise ValueError("panel must bind only to localhost")
    auth = PanelAuth(args.auth_file)
    if not auth.configured:
        raise ValueError("panel authentication is required")
    server = ThreadingHTTPServer((args.bind, args.port), PanelHandler)
    server.panel_auth = auth
    server.serve_forever()


if __name__ == "__main__":
    main()
