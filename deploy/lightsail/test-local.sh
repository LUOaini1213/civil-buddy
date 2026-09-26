#!/bin/bash
# Local rehearsal of the Lightsail launch script on any Docker host (WSL2 here). It is NOT a Lightsail run:
# no instance, no static IP, no Let's Encrypt. It runs user-data.sh with Docker already installed
# (CIVIL_SKIP_DOCKER_INSTALL=1) against a clone of this checkout at one commit, then checks through Caddy:
#   plain HTTP (SITE_ADDRESS=http://localhost), then Caddy's internal CA (SITE_ADDRESS=localhost):
#   token 401/200, the landing page, ?token= -> cookie, /demo, the linked demo route, an upload, a 20 MB body
#   refused at Caddy, the WebSocket, the gateway bound to 127.0.0.1 only, .env mode 0600, the token in no log,
#   the typed agent request on the seeded job folder, and its output surviving a re-create.
#
#   bash deploy/lightsail/test-local.sh [<commit>]      (default: HEAD; the commit must be committed)
#   TEST_REPO_URL=<repo to clone>   when this checkout is a git worktree whose .git points elsewhere
set -euo pipefail

SRC="$(cd "$(dirname "$0")/../.." && pwd)"
REF="${1:-$(git -C "$SRC" rev-parse HEAD)}"
WORK="$(mktemp -d)"
INSTALL="$WORK/civil-buddy"
HTTP_PORT="${TEST_HTTP_PORT:-18080}"
HTTPS_PORT="${TEST_HTTPS_PORT:-18443}"
GW_PORT="${TEST_GATEWAY_PORT:-18000}"
export COMPOSE_PROJECT_NAME="cb-lightsail-test"
export CIVIL_REF="$REF" CIVIL_REPO_URL="${TEST_REPO_URL:-$SRC}" CIVIL_INSTALL_DIR="$INSTALL" CIVIL_SKIP_DOCKER_INSTALL=1
# a local clone of a repository owned by another user (a Windows drive under WSL) needs safe.directory; env only
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="*"
export CADDY_HTTP_PORT="$HTTP_PORT" CADDY_HTTPS_PORT="$HTTPS_PORT" GATEWAY_PORT="$GW_PORT"
EX="$SRC/examples/facade-demo"
PASS=0

ok() { PASS=$((PASS + 1)); echo "ok   $*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }
compose() { (cd "$INSTALL" && docker compose -f docker-compose.yml -f deploy/lightsail/compose.override.yml --env-file .env "$@"); }
cleanup() {
  status=$?
  [ "$status" -ne 0 ] && compose logs --no-color --tail 80 >&2 2>/dev/null || true
  compose down -v >/dev/null 2>&1 || true
  rm -rf "$WORK"
  exit "$status"
}
trap cleanup EXIT

echo "== user-data.sh at $REF (Docker install skipped), site http://localhost"
t0=$(date +%s)
SITE_ADDRESS="http://localhost" bash "$SRC/deploy/lightsail/user-data.sh" > "$WORK/setup.log" 2>&1 || { cat "$WORK/setup.log"; fail "user-data.sh failed"; }
ok "user-data.sh finished in $(( $(date +%s) - t0 )) s (build included)"
TOKEN="$(grep '^CIVIL_TOKEN=' "$INSTALL/.env" | cut -d= -f2-)"
[[ "$TOKEN" =~ ^[0-9a-f]{64}$ ]] || fail "no 64-hex token in .env"
[ "$(stat -c '%a' "$INSTALL/.env")" = "600" ] || fail ".env is not mode 600"
ok ".env mode 600 with a 64-hex CIVIL_TOKEN"
grep -q "$TOKEN" "$WORK/setup.log" && fail "the token is in the setup log"
ok "the token is not in the setup output (what cloud-init would log)"

bindings="$(docker inspect -f '{{json .HostConfig.PortBindings}}' "$(compose ps -q gateway)")"
echo "$bindings" | grep -q '"HostIp":"127.0.0.1"' || fail "gateway not bound to 127.0.0.1: $bindings"
echo "$bindings" | grep -q '"HostIp":""\|"HostIp":"0.0.0.0"' && fail "gateway also published beyond loopback: $bindings"
ok "gateway published on 127.0.0.1:${GW_PORT} only ($bindings)"

B="http://localhost:${HTTP_PORT}"
code() { curl -s -o "${OUT:-/dev/null}" -w '%{http_code}' "$@"; }
for _ in $(seq 1 60); do [ "$(code "$B/api/health")" = 200 ] && break; sleep 1; done
[ "$(code "$B/api/health")" = 200 ] || fail "/api/health through Caddy"
ok "GET /api/health through Caddy -> 200"
[ "$(code "$B/api/tools")" = 401 ] || fail "/api/tools without token"
[ "$(code -H "Authorization: Bearer wrong" "$B/api/tools")" = 401 ] || fail "/api/tools wrong token"
[ "$(code -H "Authorization: Bearer $TOKEN" "$B/api/tools")" = 200 ] || fail "/api/tools with token"
ok "token through Caddy: 401 without, 401 wrong, 200 with"
curl -s "$B/" | grep -q "This server is private" || fail "landing page without token"
ok "GET / without token -> the English landing page"
hdrs="$(curl -s -D - -o /dev/null "$B/?token=$TOKEN")"
echo "$hdrs" | grep -q "^HTTP/1.1 303" || fail "?token= did not redirect: $hdrs"
cookie="$(echo "$hdrs" | tr -d '\r' | sed -n 's/^[Ss]et-[Cc]ookie: \(cb_token=[^;]*\).*/\1/p')"
[ -n "$cookie" ] || fail "no cookie from ?token="
echo "$hdrs" | grep -qi "set-cookie:.*HttpOnly" || fail "cookie not HttpOnly"
ok "?token= -> 303 + HttpOnly cookie"
curl -s -H "Cookie: $cookie" "$B/demo" | grep -q "Run the linked demo" || fail "/demo with cookie"
ok "GET /demo with the cookie -> the English page"
OUT="$WORK/demo.json" code -X POST -H "Cookie: $cookie" "$B/api/tender/link/demo" >/dev/null
python3 - "$WORK/demo.json" <<'PY' || fail "demo route"
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
assert d["ok"] and d["stale_statements"] == ["S2", "S3", "S6", "S7"], d.get("stale_statements")
assert d["rev_a"]["plan"]["containers_used"] == 6 and d["rev_b"]["plan"]["containers_used"] == 8
print(f"ok   POST /api/tender/link/demo through Caddy: rev A 6 x 40HQ, rev B 8 x 40HQ, stale {', '.join(d['stale_statements'])}, {d['duration_ms']} ms")
PY
PASS=$((PASS + 1))
[ "$(OUT="$WORK/up.json" code -H "Cookie: $cookie" -F "tender=@$EX/facade_itt_doc.md" -F "panel_list=@$EX/facade_panels.xlsx" "$B/api/tender/link")" = 200 ] || fail "upload"
ok "multipart upload through Caddy -> 200"
head -c 20971520 /dev/zero > "$WORK/big.md"
[ "$(code -H "Cookie: $cookie" -F "tender=@$WORK/big.md" -F "panel_list=@$EX/facade_panels.xlsx" "$B/api/tender/link")" = 413 ] || fail "20 MB body not refused"
ok "20 MB upload -> 413"

ws_check() {  # ws_check <url> <header or empty> -> prints the first message type or the refusal
  docker run --rm -i --network host civil-buddy-gateway:0.7.0 python - "$1" "$2" <<'PY'
import asyncio, ssl, sys
import websockets
url, header = sys.argv[1], sys.argv[2]
async def main():
    kw = {"additional_headers": [tuple(header.split(": ", 1))]} if header else {}
    if url.startswith("wss:"):
        kw["ssl"] = ssl._create_unverified_context()
    try:
        async with websockets.connect(url, open_timeout=10, **kw) as ws:
            print(__import__("json").loads(await asyncio.wait_for(ws.recv(), 10))["type"])
    except Exception as e:
        print("refused", type(e).__name__, getattr(getattr(e, "response", None), "status_code", ""))
asyncio.run(main())
PY
}
[ "$(ws_check "ws://localhost:${HTTP_PORT}/ws/session/lightsail-test" "Cookie: $cookie")" = "ws_subscribed" ] || fail "WebSocket with cookie"
case "$(ws_check "ws://localhost:${HTTP_PORT}/ws/session/lightsail-test" "")" in refused*) ;; *) fail "WebSocket without token accepted";; esac
ok "WebSocket through Caddy: subscribed with the cookie, refused without"

compose exec -T gateway sh -c 'ls /app/output/job' | sort | tr '\n' ' ' | grep -q "^facade_itt_doc.md facade_panels.xlsx facade_panels_rev_b.xlsx $" || fail "the seeded job folder holds more than the three synthetic files"
ok "job folder seeded with the three SYNTHETIC facade files only"
OUT="$WORK/agent.json" code -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  --data '{"text":"Link the tender facade_itt_doc.md to the packing list facade_panels.xlsx and write the logistics response","session_id":"ls-agent"}' \
  "$B/api/agent" >/dev/null
grep -q "tender_packing_link" "$WORK/agent.json" || fail "typed agent request on the seeded job folder"
ok "typed agent request on the seeded SYNTHETIC job folder -> linked run"
compose up -d --force-recreate gateway >/dev/null 2>&1
for _ in $(seq 1 90); do [ "$(code "$B/api/health")" = 200 ] && break; sleep 1; done
compose exec -T gateway sh -c 'ls /app/demo/out/ls-agent/*/tender-packing-link.json' >/dev/null || fail "agent output lost on re-create"
ok "the agent turn's tender-packing-link.json survived a gateway re-create"
logs="$(compose logs --no-color 2>&1)"
echo "$logs" | grep -q "$TOKEN" && fail "the token is in docker compose logs"
echo "$logs" | grep -q '"uri"' || fail "Caddy wrote no access log"
ok "the token is in no container log (Caddy access log on, token/cookie/auth filtered; uvicorn access log off)"

echo "== Caddy internal CA: SITE_ADDRESS=localhost"
sed -i 's/^SITE_ADDRESS=.*/SITE_ADDRESS=localhost/' "$INSTALL/.env"
compose up -d --force-recreate caddy >/dev/null 2>&1
H="https://localhost:${HTTPS_PORT}"
for _ in $(seq 1 60); do [ "$(code -k "$H/api/health")" = 200 ] && break; sleep 1; done
[ "$(code -k "$H/api/health")" = 200 ] || fail "HTTPS /api/health"
[ "$(code -k "$H/api/tools")" = 401 ] || fail "HTTPS /api/tools without token"
[ "$(code -k -H "Authorization: Bearer $TOKEN" "$H/api/tools")" = 200 ] || fail "HTTPS /api/tools with token"
curl -sk -D - -o /dev/null "$H/?token=$TOKEN" | grep -qi "set-cookie:.*Secure" || fail "cookie over HTTPS not Secure"
curl -sk -D - -o /dev/null "$H/api/health" | grep -qi "strict-transport-security" || fail "no HSTS"
[ "$(code "http://localhost:${HTTP_PORT}/api/health")" = 308 ] || fail "HTTP not redirected to HTTPS"
[ "$(ws_check "wss://localhost:${HTTPS_PORT}/ws/session/lightsail-test" "Authorization: Bearer $TOKEN")" = "ws_subscribed" ] || fail "wss"
ok "HTTPS (internal CA): 401/200, Secure cookie, HSTS, HTTP -> 308, wss subscribed"

echo "lightsail local rehearsal: $PASS checks passed (not a Lightsail run)"
