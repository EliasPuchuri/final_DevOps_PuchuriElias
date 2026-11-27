-- SQL tests for registrar_reporte(). Runs in one transaction and rolls back.
-- Usage: psql -v ON_ERROR_STOP=1 -d miraflores -f db/tests/01_registrar_reporte.sql
begin;

do $$
declare
  r  record;
  r2 record;
  u  uuid;
  n  integer;
begin
  -- Priority table, one case per row (P01/P02/P03/P04/P05)
  select * into r from registrar_reporte(gen_random_uuid(), 'M01', 'ACUMULACION',
    'Av. Larco 123', 'Bolsas de basura acumuladas', false, 4);
  assert r.http_status = 201 and r.prioridad = 'NORMAL' and r.cola = 'LIMPIEZA_PUBLICA'
     and r.plazo_horas = 24, 'P01: 4 bags, no obstruction';

  u := gen_random_uuid();
  select * into r from registrar_reporte(u, 'M01', 'ACUMULACION',
    'Av. Larco 123', 'Bolsas de basura acumuladas', false, 5);
  assert r.http_status = 201 and r.prioridad = 'ALTA' and r.cola = 'LIMPIEZA_PUBLICA'
     and r.plazo_horas = 12 and r.estado = 'REGISTRADO' and r.duplicado = false, 'P02: 5 bags';
  assert r.fecha_limite = (select registrado_en from reportes where id = r.reporte_id)
                          + interval '12 hours', 'P02: deadline = registration + 12h';

  select * into r2 from registrar_reporte(gen_random_uuid(), 'M02', 'VOLUMINOSO',
    'Calle Berlin 45', 'Mueble abandonado en la vereda', true, null);
  assert r2.http_status = 201 and r2.prioridad = 'URGENTE'
     and r2.cola = 'COORDINACION_OPERATIVA' and r2.plazo_horas = 4, 'P03: bulky + obstruction';

  select * into r2 from registrar_reporte(gen_random_uuid(), 'M02', 'VOLUMINOSO',
    'Calle Berlin 45', 'Mueble abandonado en la vereda', false, null);
  assert r2.http_status = 201 and r2.prioridad = 'PROGRAMADA'
     and r2.cola = 'RECOJO_ESPECIAL' and r2.plazo_horas = 48, 'P04: bulky, no obstruction';

  select * into r2 from registrar_reporte(gen_random_uuid(), 'M01', 'OMISION_RECOJO',
    'Jr. Lima 100', 'Omision de recojo de residuos', false, null);
  assert r2.http_status = 201 and r2.prioridad = 'NORMAL'
     and r2.cola = 'LIMPIEZA_PUBLICA' and r2.plazo_horas = 24, 'P05: omission';

  -- P07: inactive sector -> 422, no row
  select count(*) into n from reportes;
  select * into r2 from registrar_reporte(gen_random_uuid(), 'M03', 'OMISION_RECOJO',
    'Jr. Lima 100', 'Omision de recojo de residuos', false, null);
  assert r2.http_status = 422 and r2.resultado = 'SECTOR_NO_HABILITADO', 'P07: inactive sector';
  assert (select count(*) from reportes) = n, 'P07: no row inserted';

  -- Unknown sector is the same rejection
  select * into r2 from registrar_reporte(gen_random_uuid(), 'M99', 'OMISION_RECOJO',
    'Jr. Lima 100', 'Omision de recojo de residuos', false, null);
  assert r2.http_status = 422 and r2.resultado = 'SECTOR_NO_HABILITADO', 'unknown sector';

  -- P09: same UUID, same data -> 200 duplicate, original returned, still one row
  select * into r2 from registrar_reporte(u, 'M01', 'ACUMULACION',
    '  Av. Larco 123 ', 'Bolsas de basura acumuladas', false, 5);
  assert r2.http_status = 200 and r2.duplicado = true and r2.reporte_id = r.reporte_id
     and r2.codigo_publico = r.codigo_publico and r2.fecha_limite = r.fecha_limite,
     'P09: duplicate returns original (normalized comparison)';

  -- P10: same UUID, different data -> 409, original untouched
  select * into r2 from registrar_reporte(u, 'M01', 'ACUMULACION',
    'Av. Larco 123', 'Bolsas de basura acumuladas', false, 6);
  assert r2.http_status = 409 and r2.resultado = 'IDENTIFICADOR_EN_CONFLICTO', 'P10: conflict';
  assert (select count(*) from reportes where request_id = u) = 1, 'P10: single row';
  assert (select bolsas from reportes where request_id = u) = 5
     and (select prioridad from reportes where request_id = u) = 'ALTA'
     and (select fecha_limite from reportes where request_id = u) = r.fecha_limite,
     'P10: original data, priority and deadline intact';

  -- Catalog check runs before UUID resolution: existing UUID + now-invalid sector -> 422
  select * into r2 from registrar_reporte(u, 'M03', 'ACUMULACION',
    'Av. Larco 123', 'Bolsas de basura acumuladas', false, 5);
  assert r2.http_status = 422, 'catalog before UUID';

  -- A retry must not burn an identity value: public codes stay contiguous
  u := gen_random_uuid();
  select * into r from registrar_reporte(u, 'M01', 'OMISION_RECOJO',
    'Jr. Lima 100', 'Omision de recojo de residuos', false, null);
  perform * from registrar_reporte(u, 'M01', 'OMISION_RECOJO',
    'Jr. Lima 100', 'Omision de recojo de residuos', false, null);
  select * into r2 from registrar_reporte(gen_random_uuid(), 'M01', 'OMISION_RECOJO',
    'Jr. Lima 100', 'Omision de recojo de residuos', false, null);
  assert r2.reporte_id = r.reporte_id + 1, 'no identity gap after a duplicate retry';

  -- Constraints reject invalid data at the table level
  begin
    insert into reportes (request_id, sector, categoria, referencia, descripcion, obstruccion,
                          bolsas, prioridad, cola, plazo_horas, fecha_limite)
    values (gen_random_uuid(), 'M01', 'OMISION_RECOJO', 'Jr. Lima 100', 'Omision de recojo de residuos',
            false, 3, 'NORMAL', 'LIMPIEZA_PUBLICA', 24, now());
    raise exception 'bags on non-accumulation must be rejected';
  exception when check_violation then null;
  end;
end;
$$;

rollback;
