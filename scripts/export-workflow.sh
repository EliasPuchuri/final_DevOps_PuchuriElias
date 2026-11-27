#!/bin/sh
# Exports the workflow from n8n and keeps only the portable fields.
# The raw export includes instance data (owner name/email under "shared"), which must not be committed.
# Usage: [COMPOSE="docker compose"] sh scripts/export-workflow.sh
set -eu

COMPOSE=${COMPOSE:-docker compose}
WORKFLOW_FILE=${WORKFLOW_FILE:-workflow/miraflores-reportes.json}
WORKFLOW_ID=miraReportes001

$COMPOSE exec -T n8n n8n export:workflow --id="$WORKFLOW_ID" --output=/home/node/out.json >/dev/null 2>&1
$COMPOSE exec -T n8n node - > "$WORKFLOW_FILE" <<'JS'
const fs = require('fs');
const w = JSON.parse(fs.readFileSync('/home/node/out.json', 'utf8'))[0];
const out = {};
['id', 'name', 'active', 'nodes', 'connections', 'settings'].forEach((k) => { if (k in w) out[k] = w[k]; });
process.stdout.write(JSON.stringify([out], null, 2) + '\n');
JS
$COMPOSE exec -T n8n rm -f /home/node/out.json
echo "Exported to $WORKFLOW_FILE"
