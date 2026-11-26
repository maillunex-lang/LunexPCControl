#!/usr/bin/env bash
# Read-only post-deployment verification; never prints credentials.
set -euo pipefail
systemctl is-active --quiet lunexpc-gateway.service || { echo "FAIL: service inactive"; exit 1; }
ss -H -ltn '( sport = :18880 )' | grep -Eq '127[.]0[.]0[.]1:18880[[:space:]]' || { echo "FAIL: loopback listener missing"; exit 1; }
if ss -H -ltn '( sport = :18880 )' | grep -Eq '(^|[[:space:]])(0[.]0[.]0[.]0:18880|\[::\]:18880)'; then
  echo "FAIL: public listener"; exit 1
fi
status=$(curl --silent --show-error --max-time 4 --output /dev/null --write-out '%{http_code}' http://127.0.0.1:18880/devices/unregistered/mcp)
[ "$status" = 401 ] || { echo "FAIL: missing auth returned $status"; exit 1; }
status=$(curl --silent --show-error --max-time 4 --output /dev/null --header 'Authorization: Bearer intentionally-invalid' --write-out '%{http_code}' http://127.0.0.1:18880/devices/unregistered/mcp)
[ "$status" = 403 ] || { echo "FAIL: bad auth returned $status"; exit 1; }
for file in /var/lib/lunexpc-gateway/registry.sqlite /var/log/lunexpc-gateway/audit.jsonl; do
  [ -f "$file" ] && [ "$(stat -c '%a' "$file")" = 600 ] || { echo "FAIL: private file permissions"; exit 1; }
done
nginx -t >/dev/null 2>&1 || { echo "FAIL: nginx syntax"; exit 1; }
echo 'PASS: isolated gateway, authentication rejection, private state, nginx syntax'
