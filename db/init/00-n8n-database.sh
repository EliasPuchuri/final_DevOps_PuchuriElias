#!/bin/sh
# Creates the separate database and role used by n8n for its own metadata.
# Runs only on first initialization of an empty data volume.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<SQL
CREATE ROLE "$N8N_DB_USER" LOGIN PASSWORD '$N8N_DB_PASSWORD';
CREATE DATABASE "$N8N_DB" OWNER "$N8N_DB_USER";
SQL
