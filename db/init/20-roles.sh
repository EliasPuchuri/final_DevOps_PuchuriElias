#!/bin/sh
# Least-privilege application role used by the n8n PostgreSQL credential.
# It can call registrar_reporte() (SECURITY DEFINER) and append to the attempt log.
# It cannot read or write reportes directly.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE mira_app LOGIN PASSWORD '$MIRA_APP_PASSWORD';

REVOKE ALL ON FUNCTION registrar_reporte(uuid, text, text, text, text, boolean, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION registrar_reporte(uuid, text, text, text, text, boolean, integer) TO mira_app;

GRANT SELECT ON sectores TO mira_app;
GRANT INSERT ON bitacora_intentos TO mira_app;
GRANT USAGE ON SEQUENCE bitacora_intentos_id_seq TO mira_app;
SQL
