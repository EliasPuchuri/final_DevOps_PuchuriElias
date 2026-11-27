-- Schema for the Miraflores public-cleaning report prototype (synthetic data only).
-- Runs once, in POSTGRES_DB, on first initialization of an empty volume.

create table sectores (
  codigo     text primary key,
  nombre     text not null,
  habilitado boolean not null default true
);

insert into sectores (codigo, nombre, habilitado) values
  ('M01', 'Sector B · Paseo de la República hasta los malecones', true),
  ('M02', 'Sector C · Chacarilla Santa Cruz', true),
  ('M03', 'Sector A · San Antonio y Aurora', false);

create table reportes (
  id             bigint generated always as identity primary key,
  codigo_publico text generated always as ('MIR-' || lpad(id::text, 6, '0')) stored,
  request_id     uuid not null,
  sector         text not null references sectores (codigo),
  categoria      text not null check (categoria in ('ACUMULACION', 'VOLUMINOSO', 'OMISION_RECOJO')),
  referencia     text not null check (char_length(referencia) between 5 and 120),
  descripcion    text not null check (char_length(descripcion) between 15 and 200),
  obstruccion    boolean not null,
  bolsas         integer,
  estado         text not null default 'REGISTRADO' check (estado = 'REGISTRADO'),
  prioridad      text not null check (prioridad in ('URGENTE', 'ALTA', 'PROGRAMADA', 'NORMAL')),
  cola           text not null check (cola in ('COORDINACION_OPERATIVA', 'RECOJO_ESPECIAL', 'LIMPIEZA_PUBLICA')),
  plazo_horas    integer not null check (plazo_horas in (4, 12, 24, 48)),
  registrado_en  timestamptz not null default now(),
  fecha_limite   timestamptz not null,
  constraint reportes_request_id_key unique (request_id),
  constraint reportes_codigo_publico_key unique (codigo_publico),
  constraint reportes_bolsas_check check (
    (categoria = 'ACUMULACION' and bolsas between 1 and 50)
    or (categoria <> 'ACUMULACION' and bolsas is null)
  )
);

-- Attempt log. request_id is nullable and not a FK: invalid attempts have no valid UUID.
create table bitacora_intentos (
  id           bigint generated always as identity primary key,
  fecha        timestamptz not null default now(),
  request_id   uuid,
  http_status  integer not null,
  resultado    text not null,
  reporte_id   bigint references reportes (id),
  ejecucion_id text,
  origen       text not null default 'demo' check (origen in ('demo', 'prueba'))
);

-- Single source of truth for the priority table and the idempotency decision.
-- Returns one row: 201 created, 200 duplicate (same data), 409 conflict (other data),
-- 422 sector unknown or inactive. Catalog check runs before the UUID is resolved.
create or replace function registrar_reporte(
  p_request_id  uuid,
  p_sector      text,
  p_categoria   text,
  p_referencia  text,
  p_descripcion text,
  p_obstruccion boolean,
  p_bolsas      integer
)
returns table (
  http_status    integer,
  resultado      text,
  reporte_id     bigint,
  codigo_publico text,
  estado         text,
  prioridad      text,
  cola           text,
  plazo_horas    integer,
  fecha_limite   timestamptz,
  duplicado      boolean
)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
#variable_conflict use_column
declare
  v_sector text := upper(btrim(p_sector));
  v_cat    text := upper(btrim(p_categoria));
  v_ref    text := btrim(p_referencia);
  v_desc   text := btrim(p_descripcion);
  v_now    timestamptz := now();
  v_prio   text;
  v_cola   text;
  v_plazo  integer;
  v_row    reportes%rowtype;
begin
  if not exists (select 1 from sectores s where s.codigo = v_sector and s.habilitado) then
    return query select 422, 'SECTOR_NO_HABILITADO', null::bigint, null::text, null::text,
                        null::text, null::text, null::integer, null::timestamptz, false;
    return;
  end if;

  if p_obstruccion then
    v_prio := 'URGENTE';    v_cola := 'COORDINACION_OPERATIVA'; v_plazo := 4;
  elsif v_cat = 'VOLUMINOSO' then
    v_prio := 'PROGRAMADA'; v_cola := 'RECOJO_ESPECIAL';        v_plazo := 48;
  elsif v_cat = 'ACUMULACION' and p_bolsas >= 5 then
    v_prio := 'ALTA';       v_cola := 'LIMPIEZA_PUBLICA';       v_plazo := 12;
  else
    v_prio := 'NORMAL';     v_cola := 'LIMPIEZA_PUBLICA';       v_plazo := 24;
  end if;

  -- Look first so a plain retry does not burn an identity value (no gaps in public codes).
  select * into v_row from reportes r where r.request_id = p_request_id;

  if not found then
    -- The unique constraint stays the arbiter when two attempts overlap.
    insert into reportes (request_id, sector, categoria, referencia, descripcion, obstruccion,
                          bolsas, prioridad, cola, plazo_horas, registrado_en, fecha_limite)
    values (p_request_id, v_sector, v_cat, v_ref, v_desc, p_obstruccion,
            p_bolsas, v_prio, v_cola, v_plazo, v_now, v_now + make_interval(hours => v_plazo))
    on conflict (request_id) do nothing
    returning * into v_row;

    if found then
      return query select 201, 'REGISTRADO', v_row.id, v_row.codigo_publico, v_row.estado,
                          v_row.prioridad, v_row.cola, v_row.plazo_horas, v_row.fecha_limite, false;
      return;
    end if;

    -- A concurrent attempt committed the same UUID first: classify against it.
    select * into v_row from reportes r where r.request_id = p_request_id;
  end if;

  if v_row.sector = v_sector
     and v_row.categoria = v_cat
     and v_row.referencia = v_ref
     and v_row.descripcion = v_desc
     and v_row.obstruccion = p_obstruccion
     and v_row.bolsas is not distinct from p_bolsas then
    return query select 200, 'DUPLICADO', v_row.id, v_row.codigo_publico, v_row.estado,
                        v_row.prioridad, v_row.cola, v_row.plazo_horas, v_row.fecha_limite, true;
  else
    return query select 409, 'IDENTIFICADOR_EN_CONFLICTO', null::bigint, null::text, null::text,
                        null::text, null::text, null::integer, null::timestamptz, false;
  end if;
end;
$$;
