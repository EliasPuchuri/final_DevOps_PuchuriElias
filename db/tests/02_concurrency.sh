#!/bin/sh
# Concurrency test: N overlapping attempts with the same UUID and the same data.
# Expected: exactly one 201, the rest 200, and a single row with the original deadline.
# Usage: DB_EXEC="docker compose exec -T postgres" PGUSER=... PGDATABASE=... sh db/tests/02_concurrency.sh
set -eu

: "${DB_EXEC:?set DB_EXEC, e.g. 'docker compose exec -T postgres'}"
: "${PGUSER:?}" "${PGDATABASE:?}"
N=${N:-10}
UUID=$($DB_EXEC psql -U "$PGUSER" -d "$PGDATABASE" -Atc "select gen_random_uuid()")
OUT=$(mktemp -d)

i=1
while [ "$i" -le "$N" ]; do
  $DB_EXEC psql -U "$PGUSER" -d "$PGDATABASE" -Atc \
    "select http_status from registrar_reporte('$UUID','M01','ACUMULACION','Av. Larco 123','Bolsas de basura acumuladas',false,5)" \
    > "$OUT/$i.txt" &
  i=$((i + 1))
done
wait

CREATED=$(cat "$OUT"/*.txt | grep -c '^201$' || true)
DUPS=$(cat "$OUT"/*.txt | grep -c '^200$' || true)
ROWS=$($DB_EXEC psql -U "$PGUSER" -d "$PGDATABASE" -Atc "select count(*) from reportes where request_id = '$UUID'")
$DB_EXEC psql -U "$PGUSER" -d "$PGDATABASE" -Atc "delete from reportes where request_id = '$UUID'" >/dev/null
rm -rf "$OUT"

echo "created=$CREATED duplicates=$DUPS rows=$ROWS"
[ "$CREATED" -eq 1 ] && [ "$DUPS" -eq $((N - 1)) ] && [ "$ROWS" -eq 1 ] && echo PASS || { echo FAIL; exit 1; }
