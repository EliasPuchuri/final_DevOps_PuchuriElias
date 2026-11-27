-- Renames the catalog entries after the real urban sectors of Miraflores.
-- Codes and the enabled flag do not change. Idempotent; run on databases created before this change:
--   psql -v ON_ERROR_STOP=1 -d miraflores -f db/updates/001_nombres_sectores.sql
update sectores set nombre = 'Sector B · Paseo de la República hasta los malecones' where codigo = 'M01';
update sectores set nombre = 'Sector C · Chacarilla Santa Cruz'                     where codigo = 'M02';
update sectores set nombre = 'Sector A · San Antonio y Aurora'                      where codigo = 'M03';
