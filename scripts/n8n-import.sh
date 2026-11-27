#!/bin/sh
# Imports the PostgreSQL credential and the workflow into n8n, activates it and restarts n8n.
# Prerequisites: the stack is up and the n8n owner account was created once in the editor.
# Usage: MIRA_APP_PASSWORD=... [COMPOSE="docker compose"] sh scripts/n8n-import.sh
# The credential file is built in memory and streamed through stdin; no secret touches the repo.
set -eu

: "${MIRA_APP_PASSWORD:?set MIRA_APP_PASSWORD (same value as in .env)}"
COMPOSE=${COMPOSE:-docker compose}
WORKFLOW_FILE=${WORKFLOW_FILE:-workflow/miraflores-reportes.json}
WORKFLOW_ID=miraReportes001

# On a brand-new database the n8n server runs its schema migrations at start-up. Running the CLI at the same
# time makes both processes migrate concurrently ("duplicate key value ... pg_type_typname_nsp_index"),
# so wait until the server answers its readiness probe.
printf 'Waiting for n8n to be ready'
ready=0
for _ in $(seq 1 90); do
  if $COMPOSE exec -T n8n wget -q -O /dev/null http://127.0.0.1:5678/healthz/readiness </dev/null 2>/dev/null; then ready=1; break; fi
  printf '.'; sleep 2
done
echo
[ "$ready" = 1 ] || { echo "n8n did not become ready in time" >&2; exit 1; }

esc=$(printf '%s' "$MIRA_APP_PASSWORD" | sed 's/\\/\\\\/g; s/"/\\"/g')
printf '[{"id":"miraPgCred0001","name":"Miraflores PostgreSQL (mira_app)","type":"postgres","data":{"host":"postgres","port":5432,"database":"miraflores","user":"mira_app","password":"%s","ssl":"disable","allowUnauthorizedCerts":false,"maxConnections":5}}]' "$esc" \
  | $COMPOSE exec -T n8n sh -c 'cat > /home/node/cred.json'
$COMPOSE exec -T n8n sh -c 'cat > /home/node/wf.json' < "$WORKFLOW_FILE"

$COMPOSE exec -T n8n n8n import:credentials --input=/home/node/cred.json
$COMPOSE exec -T n8n n8n import:workflow --input=/home/node/wf.json
$COMPOSE exec -T n8n n8n update:workflow --id="$WORKFLOW_ID" --active=true
$COMPOSE exec -T n8n rm -f /home/node/cred.json /home/node/wf.json
$COMPOSE restart n8n
echo "Imported and activated workflow $WORKFLOW_ID"
