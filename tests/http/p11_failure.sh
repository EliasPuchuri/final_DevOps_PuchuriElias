#!/bin/sh
# P11: persistence failure before saving -> 503, then recovery and retry with the same UUID -> 201.
# DESTRUCTIVE for the target stack's app role: run ONLY against an isolated test stack,
# never against the shared server.
# Usage: WEBHOOK_URL=... DB_EXEC="docker compose -p mira-dev exec -T postgres" PGUSER=mira_admin \
#        sh tests/http/p11_failure.sh
set -u
: "${WEBHOOK_URL:?}" "${DB_EXEC:?}" "${PGUSER:?}"
DB=${PGDATABASE:-miraflores}
N8N_DB_NAME=${N8N_DB_NAME:-n8n}
FAIL=0

sql()  { $DB_EXEC psql -U "$PGUSER" -d "$DB" -Atc "$1"; }
nsql() { $DB_EXEC psql -U "$PGUSER" -d "$N8N_DB_NAME" -Atc "$1"; }
restore() { sql "alter role mira_app login" >/dev/null; }
trap restore EXIT

U=$(python -c "import uuid;print(uuid.uuid4())")
BODY_JSON=$(printf '{"request_id":"%s","distrito":"MIRAFLORES","sector":"M01","categoria":"OMISION_RECOJO","referencia":"Av. Larco 123","descripcion":"Omision de recojo de residuos","obstruccion":false,"bolsas":null}' "$U")
post() {
  OUT=$(curl -s -w '\n%{http_code}' -X POST "$WEBHOOK_URL" -H 'Content-Type: application/json' -H 'X-Origen: prueba' -d "$BODY_JSON")
  HTTP=$(printf '%s' "$OUT" | tail -n1); BODY=$(printf '%s' "$OUT" | sed '$d')
}
ok() { if [ "$2" = "1" ]; then echo "PASS $1"; else echo "FAIL $1"; FAIL=1; fi; }

echo "request_id=$U"

# 1) Break the app role (new logins refused, open sessions closed) before saving.
sql "alter role mira_app nologin" >/dev/null
sql "select pg_terminate_backend(pid) from pg_stat_activity where usename='mira_app'" >/dev/null
post
echo "attempt 1: HTTP $HTTP $BODY"
[ "$HTTP" = "503" ] && printf '%s' "$BODY" | grep -q '"codigo":"ERROR_PERSISTENCIA"' && R=1 || R=0
ok "503 ERROR_PERSISTENCIA" $R
[ "$(sql "select count(*) from reportes where request_id='$U'")" = "0" ] && R=1 || R=0
ok "no row saved while failing" $R

# 2) The attempt must be traceable in n8n even though the app DB was down.
sleep 2
EV=$(nsql "select max(e.id) from execution_entity e join execution_metadata m on m.\"executionId\"=e.id where m.key='request_id' and m.value='$U'")
H=$(nsql "select value from execution_metadata where \"executionId\"=${EV:-0} and key='http_status'")
[ "$H" = "503" ] && R=1 || R=0
ok "n8n execution $EV recorded http_status=503" $R

# 3) Restore and retry the same UUID.
restore
sleep 1
post
echo "attempt 2: HTTP $HTTP $BODY"
[ "$HTTP" = "201" ] && printf '%s' "$BODY" | grep -q '"duplicado":false' && R=1 || R=0
ok "201 after recovery" $R
[ "$(sql "select count(*) from reportes where request_id='$U'")" = "1" ] && R=1 || R=0
ok "exactly one row" $R

# 4) The log holds the recovered attempt (the failed one could not be written: DB was down).
sleep 2
[ "$(sql "select count(*) from bitacora_intentos where request_id='$U' and http_status=201")" = "1" ] && R=1 || R=0
ok "bitacora has the 201 attempt" $R

[ $FAIL -eq 0 ] && echo "P11 PASS" || { echo "P11 FAIL"; exit 1; }
