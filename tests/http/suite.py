#!/usr/bin/env python3
"""Exhaustive HTTP + database suite for the report webhook (standard library only).

Run it ONLY against an isolated stack: groups G10/G11 disable roles and lock tables.

  WEBHOOK_URL=http://127.0.0.1:38080/webhook/reportes \
  DB_EXEC="docker compose -p mira-t8 --env-file t8.env exec -T" \
  PGUSER=mira_admin MIRA_APP_PASSWORD=... RESULTS=results.json \
  python tests/http/suite.py

Every case records: expected vs actual HTTP, code, database effect and a request_id for tracing.
kind="must"    -> a deviation is a FAIL (the exam/spec or a safety property requires it)
kind="observe" -> behaviour the spec does not define; recorded as INFO, never as a failure
"""
import concurrent.futures as cf
import http.client as httpc
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.parse
import uuid

BASE = os.environ["WEBHOOK_URL"]
U = urllib.parse.urlparse(BASE)
ORIGIN = f"{U.scheme}://{U.hostname}:{U.port}"
DB_EXEC = shlex.split(os.environ["DB_EXEC"])
PGUSER = os.environ.get("PGUSER", "mira_admin")
APP_PW = os.environ.get("MIRA_APP_PASSWORD", "")
RESULTS = os.environ.get("RESULTS", "results.json")
DB = os.environ.get("PGDATABASE", "miraflores")
N8N_DB = os.environ.get("N8N_DB_NAME", "n8n")

MISSING = object()
NOLOG = {"n": 0}  # attempts whose bitacora row cannot exist (database down / bitacora insert revoked)
results = []
rids_with_row = {}


# ------------------------------------------------------------------ helpers
def sh(db, sql, app=False):
    cmd = list(DB_EXEC)
    if app:
        cmd += ["-e", f"PGPASSWORD={APP_PW}", "postgres", "psql", "-h", "localhost", "-U", "mira_app", "-d", db, "-Atc", sql]
    else:
        cmd += ["postgres", "psql", "-U", PGUSER, "-d", db, "-Atc", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=120)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def q(sql, db=DB):
    return sh(db, sql)[1]


def http(method="POST", path=None, body=None, headers=None, timeout=60):
    c = httpc.HTTPConnection(U.hostname, U.port, timeout=timeout)
    h = {"Content-Type": "application/json", "X-Origen": "prueba"}
    if headers is not None:
        h.update({k: v for k, v in headers.items() if v is not None})
        for k, v in headers.items():
            if v is None:
                h.pop(k, None)
    data = body if (body is None or isinstance(body, (bytes, bytearray))) else json.dumps(body).encode()
    t0 = time.time()
    try:
        c.request(method, path or U.path, body=data, headers=h)
        r = c.getresponse()
        raw = r.read()
        ms = int((time.time() - t0) * 1000)
        try:
            parsed = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            parsed = raw.decode("utf-8", "replace")[:300]
        return {"status": r.status, "headers": {k.lower(): v for k, v in r.getheaders()}, "body": parsed, "ms": ms}
    except Exception as e:  # noqa: BLE001
        return {"status": 0, "headers": {}, "body": f"{type(e).__name__}: {e}", "ms": int((time.time() - t0) * 1000)}
    finally:
        c.close()


def base(**kw):
    p = {"request_id": str(uuid.uuid4()), "distrito": "MIRAFLORES", "sector": "M01", "categoria": "OMISION_RECOJO",
         "referencia": "Av. Larco 123", "descripcion": "Descripcion de prueba valida", "obstruccion": False}
    p.update(kw)
    return {k: v for k, v in p.items() if v is not MISSING}


def expected_prio(cat, obs, bolsas):
    if obs:
        return ("URGENTE", "COORDINACION_OPERATIVA", 4)
    if cat == "VOLUMINOSO":
        return ("PROGRAMADA", "RECOJO_ESPECIAL", 48)
    if cat == "ACUMULACION" and bolsas >= 5:
        return ("ALTA", "LIMPIEZA_PUBLICA", 12)
    return ("NORMAL", "LIMPIEZA_PUBLICA", 24)


def rec(cid, group, name, ok, expect, actual, rid=None, note="", kind="must", ms=None, row=None):
    status = "PASS" if ok else ("INFO" if kind == "observe" else "FAIL")
    results.append({"id": cid, "group": group, "name": name, "status": status, "expect": expect, "actual": actual,
                    "request_id": rid, "note": note, "kind": kind, "ms": ms})
    if row is not None and rid:
        rids_with_row[rid] = row


counter = {"n": 0}


def case(group, name, payload=None, *, raw=None, headers=None, method="POST", path=None, want_http=None,
         want_codigo=None, check=None, kind="must", row=None, note=""):
    counter["n"] += 1
    cid = f"{group}-{counter['n']:03d}"
    body = raw if raw is not None else payload
    rid = payload.get("request_id") if isinstance(payload, dict) else None
    rid = rid if isinstance(rid, str) else None  # non-string ids (numbers, null) cannot be traced
    r = http(method, path, body, headers)
    ok = True
    exp = []
    if want_http is not None:
        allowed = want_http if isinstance(want_http, (tuple, list)) else (want_http,)
        exp.append("HTTP " + "/".join(map(str, allowed)))
        ok &= r["status"] in allowed
    if want_codigo is not None:
        exp.append(f"codigo={want_codigo}")
        ok &= isinstance(r["body"], dict) and r["body"].get("codigo") == want_codigo
    if check is not None:
        try:
            good, desc = check(r)
        except Exception as e:  # noqa: BLE001
            good, desc = False, f"check error {e}"
        exp.append(desc)
        ok &= good
    actual = f"HTTP {r['status']}"
    if isinstance(r["body"], dict):
        b = r["body"]
        actual += " " + (b.get("codigo") or b.get("codigo_publico") or "")
        if "prioridad" in b:
            actual += f" {b['prioridad']}/{b['cola']}/{b['plazo_horas']}h dup={b.get('duplicado')}"
    else:
        actual += " " + str(r["body"])[:80].replace("\n", " ")
    rec(cid, group, name, ok, "; ".join(exp), actual, rid, note, kind, r["ms"], row)
    return r


def prio_check(cat, obs, bolsas):
    pr, co, pl = expected_prio(cat, obs, bolsas)

    def f(r):
        b = r["body"]
        good = isinstance(b, dict) and (b.get("prioridad"), b.get("cola"), b.get("plazo_horas")) == (pr, co, pl) \
            and b.get("duplicado") is False and b.get("estado") == "REGISTRADO"
        return good, f"{pr}/{co}/{pl}h REGISTRADO dup=False"
    return f


# ------------------------------------------------------------------ G1 priority matrix
def g1():
    g = "G1-prioridad"
    for obs in (False, True):
        for bolsas in (1, 4, 5, 6, 50):
            case(g, f"ACUMULACION bolsas={bolsas} obstruccion={obs}", base(categoria="ACUMULACION", bolsas=bolsas, obstruccion=obs),
                 want_http=201, check=prio_check("ACUMULACION", obs, bolsas), row=True)
    for cat in ("VOLUMINOSO", "OMISION_RECOJO"):
        for obs in (False, True):
            case(g, f"{cat} obstruccion={obs}", base(categoria=cat, obstruccion=obs, bolsas=None),
                 want_http=201, check=prio_check(cat, obs, 0), row=True)
    for sec in ("M01", "M02"):
        case(g, f"sector {sec} habilitado", base(sector=sec), want_http=201, row=True)
    case(g, "fecha_limite = registro + plazo (campo iso presente)", base(categoria="VOLUMINOSO"), want_http=201,
         check=lambda r: (isinstance(r["body"], dict) and str(r["body"].get("fecha_limite_iso", "")).endswith("-05:00"),
                          "fecha_limite_iso con -05:00 (Lima)"), row=True)


# ------------------------------------------------------------------ G2 accepted / normalisation
def g2():
    g = "G2-normalizacion"
    case(g, "distrito en minusculas", base(distrito="miraflores"), want_http=201, kind="observe", row=True)
    case(g, "categoria en minusculas", base(categoria="omision_recojo"), want_http=201, kind="observe", row=True)
    case(g, "sector en minusculas", base(sector="m01"), want_http=201, kind="observe", row=True)
    case(g, "sector con espacios", base(sector=" M01 "), want_http=201, kind="observe", row=True)
    case(g, "referencia/descripcion con espacios externos", base(referencia="   Av. Larco 123   ", descripcion="   Descripcion de prueba valida   "),
         want_http=201, row=True)
    case(g, "UUID en MAYUSCULAS", base(request_id=str(uuid.uuid4()).upper()), want_http=201, kind="observe", row=True)
    case(g, "UUID con espacios externos", base(request_id=" " + str(uuid.uuid4()) + " "), want_http=201, kind="observe")
    case(g, "UUID nil (todo ceros)", base(request_id="00000000-0000-0000-0000-000000000000"), want_http=(201, 200, 400, 409), kind="observe")
    case(g, "UUID version 1", base(request_id=str(uuid.uuid1())), want_http=201, kind="observe", row=True)
    case(g, "campos desconocidos se ignoran", base(extra="x", otro={"a": 1}), want_http=201, kind="observe", row=True)
    case(g, "descripcion con HTML/script", base(descripcion="<script>alert(1)</script> basura en la calle"), want_http=201, row=True)
    case(g, "descripcion con intento de inyeccion SQL", base(descripcion="'; DROP TABLE reportes; -- calle sucia"), want_http=201, row=True)
    case(g, "referencia con comillas y backslash", base(referencia="Jr. \"Lima\" \\ 100 'x'"), want_http=201, row=True)
    case(g, "acentos y enie", base(referencia="Calle Ñandú 45, Miraflores", descripcion="Acumulación de residuos junto al parque"), want_http=201, row=True)
    case(g, "saltos de linea y tabuladores en descripcion", base(descripcion="Linea uno\nLinea dos\tcon tab para probar"), want_http=201, kind="observe", row=True)
    case(g, "descripcion de 200 caracteres exactos", base(descripcion="d" * 200), want_http=201, row=True)
    case(g, "referencia de 120 caracteres exactos", base(referencia="r" * 120), want_http=201, row=True)
    case(g, "referencia de 5 caracteres exactos", base(referencia="abcde"), want_http=201, row=True)
    case(g, "descripcion de 15 caracteres exactos", base(descripcion="x" * 15), want_http=201, row=True)
    case(g, "bolsas 5.0 (JSON float entero)", raw=json.dumps(base(categoria="ACUMULACION", bolsas=5)).replace('"bolsas": 5', '"bolsas": 5.0').encode(),
         want_http=201, kind="observe")
    case(g, "bolsas 1e1 (notacion cientifica)", raw=json.dumps(base(categoria="ACUMULACION", bolsas=5)).replace('"bolsas": 5', '"bolsas": 1e1').encode(),
         want_http=201, kind="observe")
    case(g, "campos duplicados en el JSON (gana el ultimo)",
         raw=('{"request_id":"%s","distrito":"OTRO","distrito":"MIRAFLORES","sector":"M01","categoria":"OMISION_RECOJO",'
              '"referencia":"Av. Larco 123","descripcion":"Descripcion de prueba valida","obstruccion":false}' % uuid.uuid4()).encode(),
         want_http=201, kind="observe")


# ------------------------------------------------------------------ G3 field validation (400)
def g3():
    g = "G3-validacion"
    bad = lambda name, **kw: case(g, name, base(**kw), want_http=400, want_codigo="DATOS_INVALIDOS", row=False)  # noqa: E731
    bad("referencia de 4 caracteres", referencia="abcd")
    bad("referencia de 121 caracteres", referencia="r" * 121)
    bad("referencia solo espacios", referencia="          ")
    bad("referencia que queda en 3 tras recortar", referencia="   abc   ")
    bad("referencia ausente", referencia=MISSING)
    bad("referencia null", referencia=None)
    bad("referencia numerica", referencia=12345)
    bad("descripcion de 14 caracteres", descripcion="x" * 14)
    bad("descripcion de 201 caracteres", descripcion="d" * 201)
    bad("descripcion solo espacios", descripcion=" " * 30)
    bad("descripcion ausente", descripcion=MISSING)
    bad("descripcion arreglo", descripcion=["a" * 20])
    bad("obstruccion string 'true'", obstruccion="true")
    bad("obstruccion numero 1", obstruccion=1)
    bad("obstruccion null", obstruccion=None)
    bad("obstruccion ausente", obstruccion=MISSING)
    bad("obstruccion 'si'", obstruccion="si")
    bad("distrito vacio", distrito="")
    bad("distrito desconocido (LIMA)", distrito="LIMA")
    bad("distrito null", distrito=None)
    bad("distrito numerico", distrito=123)
    bad("distrito ausente", distrito=MISSING)
    bad("categoria vacia", categoria="")
    bad("categoria desconocida", categoria="OTRA")
    bad("categoria nombre antiguo OMISION", categoria="OMISION")
    bad("categoria con tilde ACUMULACIÓN", categoria="ACUMULACIÓN", bolsas=5)
    bad("categoria ausente", categoria=MISSING)
    bad("sector ausente en MIRAFLORES", sector=MISSING)
    bad("sector vacio en MIRAFLORES", sector="")
    bad("sector solo espacios en MIRAFLORES", sector="   ")
    bad("sector numerico en MIRAFLORES", sector=1)
    for n in (0, -1, 51, 100, 5.5, "5", "", None, True, [5], 2 ** 53):
        bad(f"ACUMULACION bolsas={n!r}", categoria="ACUMULACION", bolsas=n)
    bad("ACUMULACION sin bolsas", categoria="ACUMULACION", bolsas=MISSING)
    bad("OMISION_RECOJO con bolsas=3", categoria="OMISION_RECOJO", bolsas=3)
    bad("VOLUMINOSO con bolsas=0", categoria="VOLUMINOSO", bolsas=0)
    bad("VOLUMINOSO con bolsas=1", categoria="VOLUMINOSO", bolsas=1)
    case(g, "OMISION_RECOJO con bolsas null (permitido)", base(bolsas=None), want_http=201, row=True)
    case(g, "OMISION_RECOJO sin bolsas (permitido)", base(bolsas=MISSING), want_http=201, row=True)
    # several errors at once are all reported
    case(g, "multiples errores: detalle lista todos", base(referencia="a", descripcion="b", categoria="X", obstruccion="no"),
         want_http=400, want_codigo="DATOS_INVALIDOS", row=False,
         check=lambda r: (isinstance(r["body"], dict) and len(r["body"].get("detalle", [])) >= 4, "detalle con >=4 errores"))
    # unicode length semantics (characters vs UTF-16 code units)
    case(g, "referencia de 3 emojis (3 caracteres, <5): debe ser 400", base(referencia="\U0001F600" * 3),
         want_http=400, want_codigo="DATOS_INVALIDOS", row=False,
         note="JavaScript cuenta unidades UTF-16 (6); PostgreSQL cuenta caracteres (3)")
    case(g, "referencia de 61 emojis (61 caracteres, <=120): debe ser 201", base(referencia="\U0001F600" * 61),
         want_http=201, row=True, note="JavaScript cuenta 122 unidades UTF-16")
    case(g, "descripcion de 8 emojis (8 caracteres, <15): debe ser 400", base(descripcion="\U0001F600" * 8),
         want_http=400, want_codigo="DATOS_INVALIDOS", row=False)
    case(g, "descripcion de 101 emojis (101 caracteres, <=200): debe ser 201", base(descripcion="\U0001F600" * 101),
         want_http=201, row=True)
    case(g, "descripcion con caracter NUL (\\u0000)", base(descripcion="Descripcion con NUL\u0000 en medio"),
         want_http=400, want_codigo="DATOS_INVALIDOS", row=False,
         note="PostgreSQL no admite NUL en text: no debe presentarse como falla de persistencia")
    case(g, "referencia con caracter NUL", base(referencia="Av. Larco\u0000 123"), want_http=400, row=False)
    case(g, "descripcion con sustituto suelto (\\ud800)", raw=json.dumps(base(descripcion="Texto con sustituto \\ud800 aislado")).replace("\\\\ud800", "\\ud800").encode(),
         want_http=400, want_codigo="DATOS_INVALIDOS", row=False)
    case(g, "referencia con salto de linea", base(referencia="Av. Larco\n123"), want_http=400, want_codigo="DATOS_INVALIDOS", row=False)
    case(g, "referencia con caracter de control \\u0001", base(referencia="Av. Larco\u0001 123"), want_http=400, row=False)
    case(g, "descripcion con caracter de control \\u0001", base(descripcion="Descripcion\u0001 de prueba valida"), want_http=400, row=False)
    case(g, "descripcion con \\u007f (DEL)", base(descripcion="Descripcion\u007f de prueba valida"), want_http=400, row=False)
    case(g, "descripcion con salto de linea y tabulador (permitidos)", base(descripcion="Linea uno\nLinea dos\tcon tab"), want_http=201, row=True)


# ------------------------------------------------------------------ G4 jurisdiction & sector
def g4():
    g = "G4-jurisdiccion"
    case(g, "SURQUILLO valido sin sector", base(distrito="SURQUILLO", sector=MISSING), want_http=422, want_codigo="FUERA_DE_JURISDICCION", row=False)
    case(g, "OTRO valido sin sector", base(distrito="OTRO", sector=MISSING), want_http=422, want_codigo="FUERA_DE_JURISDICCION", row=False)
    case(g, "SURQUILLO con sector M01 (se ignora el sector)", base(distrito="SURQUILLO", sector="M01"), want_http=422, want_codigo="FUERA_DE_JURISDICCION", row=False)
    case(g, "SURQUILLO con sector M03 inactivo: gana jurisdiccion", base(distrito="SURQUILLO", sector="M03"), want_http=422, want_codigo="FUERA_DE_JURISDICCION", row=False)
    case(g, "OTRO con sector inexistente: gana jurisdiccion", base(distrito="OTRO", sector="ZZZ"), want_http=422, want_codigo="FUERA_DE_JURISDICCION", row=False)
    case(g, "orden: SURQUILLO + datos invalidos -> 400 antes que 422", base(distrito="SURQUILLO", descripcion="corta"), want_http=400, want_codigo="DATOS_INVALIDOS", row=False)
    case(g, "orden: OTRO + bolsas en OMISION -> 400", base(distrito="OTRO", bolsas=3), want_http=400, row=False)
    case(g, "MIRAFLORES + sector M03 inactivo", base(sector="M03"), want_http=422, want_codigo="SECTOR_NO_HABILITADO", row=False)
    case(g, "MIRAFLORES + sector inexistente M99", base(sector="M99"), want_http=422, want_codigo="SECTOR_NO_HABILITADO", row=False)
    case(g, "MIRAFLORES + sector 'ZZZ'", base(sector="ZZZ"), want_http=422, want_codigo="SECTOR_NO_HABILITADO", row=False)
    case(g, "MIRAFLORES + sector 'M01; DROP'", base(sector="M01; DROP TABLE sectores"), want_http=422, want_codigo="SECTOR_NO_HABILITADO", row=False)
    case(g, "422 sector inactivo en OMISION_RECOJO sin obstruccion (P07)", base(sector="M03", obstruccion=False), want_http=422, want_codigo="SECTOR_NO_HABILITADO", row=False)


# ------------------------------------------------------------------ G5 request_id and body shape
def g5():
    g = "G5-cuerpo"
    inv = lambda name, **kw: case(g, name, base(**kw), want_http=400, want_codigo="DATOS_INVALIDOS", row=False)  # noqa: E731
    inv("request_id ausente", request_id=MISSING)
    inv("request_id null", request_id=None)
    inv("request_id vacio", request_id="")
    inv("request_id 'abc'", request_id="abc")
    inv("request_id sin guiones (32 hex)", request_id=uuid.uuid4().hex)
    inv("request_id entre llaves", request_id="{" + str(uuid.uuid4()) + "}")
    inv("request_id numerico", request_id=123456)
    inv("request_id con caracter no hex", request_id="g" * 8 + "-" + "g" * 4 + "-" + "g" * 4 + "-" + "g" * 4 + "-" + "g" * 12)
    inv("request_id 37 caracteres", request_id=str(uuid.uuid4()) + "0")
    for name, raw in [("cuerpo vacio", b""), ("arreglo []", b"[]"), ("objeto {}", b"{}"), ("null", b"null"), ("string", b'"hola"'),
                      ("numero", b"123"), ("booleano", b"true"), ("JSON roto {bad", b"{bad"), ("JSON truncado", b'{"a":'),
                      ("BOM + JSON valido", b"\xef\xbb\xbf" + json.dumps(base()).encode()), ("bytes no UTF-8", b"\xff\xfe\x00\x00"),
                      ("anidamiento profundo [[[...]]]", b"[" * 3000 + b"]" * 3000)]:
        case(g, name, raw=raw, want_http=400, want_codigo="DATOS_INVALIDOS")
    for ct in ("text/plain", "application/json; charset=utf-8", "application/x-www-form-urlencoded", "application/xml", None):
        case(g, f"JSON valido con Content-Type {ct}", base(), headers={"Content-Type": ct}, want_http=201, kind="observe", row=True)
    case(g, "cuerpo ~15 KB valido (campo extra grande)", base(relleno="x" * 15000), want_http=201, kind="observe", row=True)
    case(g, "cuerpo ~17 KB (supera el limite de 16 KB)", base(relleno="x" * 17000), want_http=413, row=False)
    case(g, "query string se ignora", base(), path=U.path + "?x=1&y=2", want_http=201, kind="observe", row=True)


# ------------------------------------------------------------------ G6 idempotency
def g6():
    g = "G6-idempotencia"
    p = base(categoria="ACUMULACION", bolsas=5)
    r1 = case(g, "alta inicial", p, want_http=201, row=True)
    code = r1["body"].get("codigo_publico") if isinstance(r1["body"], dict) else None
    lim = r1["body"].get("fecha_limite_iso") if isinstance(r1["body"], dict) else None

    def same(r):
        b = r["body"]
        return isinstance(b, dict) and b.get("duplicado") is True and b.get("codigo_publico") == code and b.get("fecha_limite_iso") == lim, \
            "duplicado=true con mismo codigo y fecha limite"
    case(g, "reenvio identico -> 200 duplicado", p, want_http=200, check=same)
    case(g, "reenvio con espacios/mayusculas distintos (normalizados iguales) -> 200",
         dict(p, referencia="  " + p["referencia"] + "  ", categoria="acumulacion", sector=" m01 ", distrito="miraflores"), want_http=200, check=same)
    case(g, "reenvio con UUID en MAYUSCULAS -> 200", dict(p, request_id=p["request_id"].upper()), want_http=200, kind="observe", check=same)
    variants = {"bolsas 6": {"bolsas": 6}, "sector M02": {"sector": "M02"}, "categoria VOLUMINOSO": {"categoria": "VOLUMINOSO", "bolsas": None},
                "referencia distinta": {"referencia": "Otra referencia 999"}, "descripcion distinta": {"descripcion": "Otra descripcion valida distinta"},
                "obstruccion true": {"obstruccion": True}}
    for name, delta in variants.items():
        case(g, f"mismo UUID, cambia {name} -> 409", dict(p, **delta), want_http=409, want_codigo="IDENTIFICADOR_EN_CONFLICTO")
    case(g, "mismo UUID con distrito SURQUILLO -> 422 (jurisdiccion antes que UUID)", dict(p, distrito="SURQUILLO"), want_http=422, want_codigo="FUERA_DE_JURISDICCION")
    case(g, "mismo UUID con datos invalidos -> 400 (formato antes que UUID)", dict(p, descripcion="x"), want_http=400)
    case(g, "mismo UUID con sector M03 -> 422 (catalogo antes que UUID)", dict(p, sector="M03"), want_http=422, want_codigo="SECTOR_NO_HABILITADO")

    def intact(_):
        rows = q(f"select bolsas||'|'||prioridad||'|'||plazo_horas||'|'||codigo_publico from reportes where request_id='{p['request_id']}'")
        return rows == f"5|ALTA|12|{code}", f"fila original intacta (5|ALTA|12|{code})"
    case(g, "tras 409/422/400 la fila original sigue intacta", p, want_http=200, check=intact)
    cnt = q(f"select count(*) from reportes where request_id='{p['request_id']}'")
    rec(f"{g}-cnt", g, "una sola fila para el UUID tras todos los intentos", cnt == "1", "1 fila", f"{cnt} fila(s)", p["request_id"])

    # catalog changes after the report was created
    q("update sectores set habilitado=false where codigo='M01'")
    try:
        case(g, "UUID existente tras deshabilitar su sector -> 422", p, want_http=422, want_codigo="SECTOR_NO_HABILITADO",
             note="el catalogo se evalua antes de resolver el UUID, como pide el enunciado")
    finally:
        q("update sectores set habilitado=true where codigo='M01'")
    case(g, "tras reactivar el sector, el UUID vuelve a resolverse -> 200", p, want_http=200, check=same)


# ------------------------------------------------------------------ G7 concurrency
def g7():
    g = "G7-concurrencia"
    # same UUID, same data, 20 in parallel
    p = base(categoria="ACUMULACION", bolsas=7)
    with cf.ThreadPoolExecutor(20) as ex:
        rs = list(ex.map(lambda _: http("POST", None, p), range(20)))
    st = sorted(r["status"] for r in rs)
    rows = q(f"select count(*) from reportes where request_id='{p['request_id']}'")
    codes = {r["body"].get("codigo_publico") for r in rs if isinstance(r["body"], dict) and r["body"].get("codigo_publico")}
    ok = st.count(201) == 1 and st.count(200) == 19 and rows == "1" and len(codes) == 1
    rec(f"{g}-001", g, "20 envios simultaneos, mismo UUID y datos", ok, "1x201, 19x200, 1 fila, 1 codigo",
        f"{st.count(201)}x201 {st.count(200)}x200 otros={[s for s in st if s not in (200, 201)]} filas={rows} codigos={len(codes)}", p["request_id"], row=True)
    # same UUID, two different payloads in parallel
    rid = str(uuid.uuid4())
    a, b = base(request_id=rid, categoria="ACUMULACION", bolsas=5), base(request_id=rid, categoria="ACUMULACION", bolsas=6)
    with cf.ThreadPoolExecutor(20) as ex:
        rs = list(ex.map(lambda i: (i % 2, http("POST", None, a if i % 2 == 0 else b)), range(20)))
    row = q(f"select bolsas from reportes where request_id='{rid}'")
    cnt = q(f"select count(*) from reportes where request_id='{rid}'")
    winner = 0 if row == "5" else 1
    coherent = True
    n201 = 0
    for who, r in rs:
        s = r["status"]
        n201 += s == 201
        if who == winner and s not in (200, 201):
            coherent = False
        if who != winner and s != 409:
            coherent = False
    ok = cnt == "1" and n201 == 1 and coherent
    rec(f"{g}-002", g, "20 envios simultaneos, mismo UUID con 2 contenidos distintos (5 y 6 bolsas)", ok,
        "1 fila, un solo 201, el resto 200 (mismo contenido que el ganador) o 409 (distinto)",
        f"filas={cnt} ganador={row} bolsas, 201x{n201}, coherente={coherent}", rid, row=True)
    # 40 distinct UUIDs in parallel
    ps = [base() for _ in range(40)]
    with cf.ThreadPoolExecutor(20) as ex:
        rs = list(ex.map(lambda x: http("POST", None, x), ps))
    ok = all(r["status"] == 201 for r in rs)
    codes = [r["body"].get("codigo_publico") for r in rs if isinstance(r["body"], dict)]
    ids = ",".join(f"'{x['request_id']}'" for x in ps)
    cnt = q(f"select count(*) from reportes where request_id in ({ids})")
    ok &= cnt == "40" and len(set(codes)) == 40
    rec(f"{g}-003", g, "40 envios simultaneos con UUID distintos", ok, "40x201, 40 filas, 40 codigos unicos",
        f"estados={sorted(set(r['status'] for r in rs))} filas={cnt} codigos_unicos={len(set(codes))}")
    for x in ps:
        rids_with_row[x["request_id"]] = True


# ------------------------------------------------------------------ G8 transport & security
def g8():
    g = "G8-transporte"
    for m in ("GET", "HEAD", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE"):
        case(g, f"metodo {m} en el webhook", method=m, payload=None, want_http=(403, 405), row=False)
    for path, want in [(U.path + "/", (404,)), ("/webhook/Reportes", (404,)), ("/webhook/otro", (404,)), ("/webhook-test/reportes", (404,)),
                       ("/webhook", (404,)), ("/rest/settings", (404,)), ("/rest/login", (404,)), ("/signin", (404,)), ("/healthz", (404,)),
                       ("/metrics", (404,)), ("/.env", (404,)), ("/.git/config", (404,)), ("/nginx/default.conf", (404,)), ("/default.conf", (404,)),
                       ("/docker-compose.yml", (404,)), ("/..%2f..%2fetc/passwd", (400, 404)), ("/%2e%2e/%2e%2e/etc/passwd", (400, 404)),
                       ("/index.html", (200,)), ("/styles.css?v=2", (200,)), ("/app.js?v=2", (200,)), ("/", (200,))]:
        case(g, f"GET {path}", method="GET", path=path, payload=None, want_http=want, row=False)
    r = http("GET", "/")
    want = {"content-security-policy": "default-src 'self'", "x-content-type-options": "nosniff", "referrer-policy": "no-referrer", "cache-control": "no-cache"}
    for h, v in want.items():
        rec(f"{g}-h-{h}", g, f"encabezado {h} en /", v in r["headers"].get(h, ""), f"{h} contiene {v}", r["headers"].get(h, "(ausente)"), kind="must")
    rec(f"{g}-h-server", g, "el encabezado Server no revela la version de nginx", "/" not in r["headers"].get("server", "nginx/x"),
        "Server sin version", r["headers"].get("server", "(ausente)"), kind="must")
    rp = http("POST", None, base())
    for h in ("content-security-policy", "x-content-type-options"):
        rec(f"{g}-h2-{h}", g, f"encabezado {h} tambien en la respuesta del webhook", h in rp["headers"], h, rp["headers"].get(h, "(ausente)"), kind="observe")
    cors = http("OPTIONS", None, None, {"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    rec(f"{g}-cors", g, "preflight CORS de otro origen no concede acceso", "access-control-allow-origin" not in cors["headers"],
        "sin Access-Control-Allow-Origin", str(cors["status"]) + " " + cors["headers"].get("access-control-allow-origin", "-"))
    sp = http("POST", None, base(), {"X-Origen": "PRUEBA"})
    sp2 = http("POST", None, base(), {"X-Origen": "otra"})
    sp3 = http("POST", None, base(), {"X-Origen": None})
    rec(f"{g}-origen", g, "cabecera X-Origen: distingue prueba/demo (3 variantes responden 201)", sp["status"] == sp2["status"] == sp3["status"] == 201,
        "201 x3", f"{sp['status']},{sp2['status']},{sp3['status']}")


# ------------------------------------------------------------------ G10 failures (destructive)
def g10():
    g = "G10-fallos"
    existing = base(categoria="ACUMULACION", bolsas=5)
    case(g, "preparacion: reporte existente", existing, want_http=201, row=True)
    new = base()
    q("alter role mira_app nologin")
    q("select count(pg_terminate_backend(pid)) from pg_stat_activity where usename='mira_app'")
    try:
        case(g, "P11a: BD caida, reporte nuevo -> 503", new, want_http=503, want_codigo="ERROR_PERSISTENCIA", row=False)
        case(g, "BD caida, UUID existente -> 503 (no se puede confirmar)", existing, want_http=503, want_codigo="ERROR_PERSISTENCIA")
        case(g, "BD caida, datos invalidos -> 400 (no necesita BD)", base(descripcion="x"), want_http=400, row=False)
        case(g, "BD caida, SURQUILLO -> 422 (no necesita BD)", base(distrito="SURQUILLO"), want_http=422, row=False)
        case(g, "BD caida, UUID invalido -> 400", base(request_id="abc"), want_http=400, row=False)
    finally:
        q("alter role mira_app login")
    NOLOG["n"] += 5  # the five requests sent while the database was unreachable
    time.sleep(1)
    case(g, "P11b: recuperada la BD, reintento con el mismo UUID -> 201", new, want_http=201, row=True)
    case(g, "recuperada la BD, UUID existente -> 200", existing, want_http=200)
    cnt = q(f"select count(*) from reportes where request_id='{new['request_id']}'")
    rec(f"{g}-cnt", g, "una sola fila tras 503 + reintento", cnt == "1", "1 fila", f"{cnt} fila(s)", new["request_id"])

    # EXECUTE revoked on the function
    q("revoke execute on function registrar_reporte(uuid,text,text,text,text,boolean,integer) from mira_app")
    try:
        case(g, "permiso EXECUTE revocado -> 503", base(), want_http=503, row=False)
    finally:
        q("grant execute on function registrar_reporte(uuid,text,text,text,text,boolean,integer) to mira_app")

    # bitacora failing must not hide the response
    q("revoke insert on bitacora_intentos from mira_app")
    bp = base()
    try:
        case(g, "INSERT en bitacora revocado: la respuesta sigue siendo 201", bp, want_http=201, row=True)
        NOLOG["n"] += 1
    finally:
        q("grant insert on bitacora_intentos to mira_app")
    time.sleep(2)
    b = q(f"select count(*) from bitacora_intentos where request_id='{bp['request_id']}'")
    rec(f"{g}-bit", g, "con la bitacora rota el reporte se guarda y no hay fila de bitacora", b == "0", "0 filas de bitacora", f"{b}", bp["request_id"])

    # slow database: table lock held; the client gives up, the server still commits, the retry is a duplicate
    slow = base()
    holder = subprocess.Popen(DB_EXEC + ["postgres", "psql", "-U", PGUSER, "-d", DB, "-Atc",
                                         "begin; lock table reportes in share row exclusive mode; select pg_sleep(9); commit;"],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    t0 = time.time()
    r = http("POST", None, slow, timeout=4)
    rec(f"{g}-slow1", g, "BD lenta (bloqueo 9 s), el cliente abandona a los 4 s", r["status"] == 0, "timeout del cliente (status 0)",
        f"status={r['status']} en {int((time.time() - t0) * 1000)} ms", slow["request_id"])
    holder.wait(timeout=60)
    time.sleep(2)
    saved = q(f"select count(*) from reportes where request_id='{slow['request_id']}'")
    rec(f"{g}-slow2", g, "aunque el cliente abandonó, el servidor guardó el reporte", saved == "1", "1 fila", f"{saved} fila(s)", slow["request_id"], row=True)
    case(g, "el reintento del mismo UUID devuelve 200 duplicado (no crea otro)", slow, want_http=200,
         check=lambda r: (isinstance(r["body"], dict) and r["body"].get("duplicado") is True, "duplicado=true"))
    # bloqueo con espera tolerable: la respuesta llega
    holder = subprocess.Popen(DB_EXEC + ["postgres", "psql", "-U", PGUSER, "-d", DB, "-Atc",
                                         "begin; lock table reportes in share row exclusive mode; select pg_sleep(5); commit;"],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    case(g, "BD lenta (bloqueo 5 s): la respuesta llega con 201 tras esperar", base(), want_http=201, row=True,
         check=lambda r: (r["ms"] >= 2500, f"tarda >= 2.5 s (tardo {r['ms']} ms)"))
    holder.wait(timeout=60)


# ------------------------------------------------------------------ G11 database permissions
def g11():
    g = "G11-permisos-bd"
    chk = [("SELECT en reportes", "select count(*) from reportes", False),
           ("SELECT en bitacora_intentos", "select count(*) from bitacora_intentos", False),
           ("INSERT directo en reportes", "insert into reportes (request_id,sector,categoria,referencia,descripcion,obstruccion,prioridad,cola,plazo_horas,fecha_limite) values (gen_random_uuid(),'M01','OMISION_RECOJO','abcde','x'||repeat('y',20),false,'NORMAL','LIMPIEZA_PUBLICA',24,now())", False),
           ("UPDATE en sectores", "update sectores set habilitado=true", False),
           ("DELETE en bitacora_intentos", "delete from bitacora_intentos", False),
           ("TRUNCATE reportes", "truncate reportes", False),
           ("DROP TABLE reportes", "drop table reportes", False),
           ("CREATE TABLE", "create table x(a int)", False),
           ("SELECT en sectores (permitido)", "select count(*) from sectores", True),
           ("INSERT en bitacora (permitido)", "insert into bitacora_intentos (http_status,resultado,origen) values (0,'prueba-permisos','prueba')", True),
           ("EXECUTE registrar_reporte (permitido)", "select http_status from registrar_reporte(gen_random_uuid(),'M01','OMISION_RECOJO','Av. Larco 123','Descripcion de prueba valida',false,null)", True)]
    for name, sql, allowed in chk:
        rc, out, err = sh(DB, sql, app=True)
        low = err.lower()
        denied = rc != 0 and ("permission denied" in low or "must be owner" in low)  # DDL on a table it does not own
        ok = (rc == 0) if allowed else denied
        rec(f"{g}-{chk.index((name, sql, allowed)) + 1:02d}", g, f"mira_app: {name}", ok, "permitido" if allowed else "permission denied",
            "permitido" if rc == 0 else (err.splitlines()[0][:90] if err else "error"))
    rc, out, err = sh(DB, "select http_status from registrar_reporte(gen_random_uuid(),'M01','OMISION_RECOJO','Av. Larco 123','Descripcion de prueba valida',false,3)", app=True)
    rec(f"{g}-fn1", g, "funcion llamada directo con bolsas en una categoria que no es ACUMULACION", rc != 0, "rechazada por la restriccion de la tabla",
        (err.splitlines()[0][:100] if err else out), kind="observe", note="la funcion no valida por si misma; depende de n8n y de los CHECK")
    rc, out, err = sh(DB, "select http_status from registrar_reporte(null,'M01','OMISION_RECOJO','Av. Larco 123','Descripcion de prueba valida',false,null)", app=True)
    rec(f"{g}-fn2", g, "funcion llamada directo con UUID nulo", rc != 0, "error", (err.splitlines()[0][:100] if err else out), kind="observe")
    rc, out, err = sh(DB, "select http_status from registrar_reporte(gen_random_uuid(),'M01','FALSA','Av. Larco 123','Descripcion de prueba valida',false,null)", app=True)
    rec(f"{g}-fn3", g, "funcion llamada directo con categoria inexistente", rc != 0, "rechazada por CHECK", (err.splitlines()[0][:100] if err else out), kind="observe")


# ------------------------------------------------------------------ G12 performance
def g13():
    """Rate limit. Needs the stack started with the DEFAULT limit; set RATE_TEST=1 (the other groups need it relaxed)."""
    g = "G13-limite-de-tasa"
    if os.environ.get("RATE_TEST") != "1":
        return
    a = {"CF-Connecting-IP": "203.0.113.10"}
    ps = [base() for _ in range(80)]
    with cf.ThreadPoolExecutor(40) as ex:
        rs = list(ex.map(lambda x: http("POST", None, x, a), ps))
    st = [r["status"] for r in rs]
    n201, n429 = st.count(201), st.count(429)
    other = sorted(set(s for s in st if s not in (201, 429)))
    ids = ",".join(f"'{x['request_id']}'" for x in ps)
    rows = q(f"select count(*) from reportes where request_id in ({ids})")
    rec(f"{g}-001", g, "rafaga de 80 envios validos de un mismo cliente: se atiende lo permitido y se rechaza el resto con 429",
        n429 > 0 and n201 > 0 and not other and rows == str(n201), "mezcla de 201 y 429, sin otros codigos, filas = numero de 201",
        f"201x{n201} 429x{n429} otros={other} filas={rows}")
    r429 = next((r for r in rs if r["status"] == 429), None)
    rec(f"{g}-002", g, "la respuesta 429 es JSON legible y trae Retry-After",
        bool(r429) and isinstance(r429["body"], dict) and r429["body"].get("codigo") == "DEMASIADAS_SOLICITUDES" and "retry-after" in r429["headers"],
        "codigo=DEMASIADAS_SOLICITUDES + Retry-After", f"{r429['body'] if r429 else 'sin 429'} retry-after={r429['headers'].get('retry-after') if r429 else '-'}")
    rb = http("POST", None, base(), {"CF-Connecting-IP": "203.0.113.20"})
    rec(f"{g}-003", g, "otro cliente (otra IP real) no se ve afectado mientras el primero esta limitado", rb["status"] == 201,
        "201", f"{rb['status']}", kind="must")
    time.sleep(7)
    ra = http("POST", None, base(), a)
    rec(f"{g}-004", g, "pasados unos segundos el primer cliente vuelve a poder enviar", ra["status"] == 201, "201", f"{ra['status']}")
    ok = True
    codes = []
    for _ in range(12):
        r = http("POST", None, base(), {"CF-Connecting-IP": "203.0.113.30"})
        codes.append(r["status"])
        time.sleep(0.3)
    ok = all(c == 201 for c in codes)
    rec(f"{g}-005", g, "un ritmo normal (12 envios con 0,3 s de pausa) nunca se limita", ok, "12 x 201", f"{sorted(set(codes))}")
    time.sleep(6)


def g14():
    """The database rejects a value n8n considers valid: it must be a 400 (data problem), not a 503 (outage)."""
    g = "G14-errores-de-datos-en-la-bd"
    q("alter table reportes add constraint tmp_forzar_error check (referencia <> 'Forzar error de datos')")
    try:
        case(g, "la base rechaza un valor (CHECK temporal): 400 y no 503", base(referencia="Forzar error de datos"),
             want_http=400, want_codigo="DATOS_INVALIDOS", row=False)
    finally:
        q("alter table reportes drop constraint if exists tmp_forzar_error")
    case(g, "sin la restriccion temporal el mismo valor se acepta", base(referencia="Forzar error de datos"), want_http=201, row=True)


def g12():
    g = "G12-rendimiento"
    ms = []
    for _ in range(100):
        r = http("POST", None, base())
        ms.append(r["ms"])
    ms.sort()
    p50, p95, mx = ms[49], ms[94], ms[-1]
    rec(f"{g}-seq", g, "100 envios secuenciales validos", p95 < 1500, "p95 < 1500 ms", f"p50={p50} ms p95={p95} ms max={mx} ms", kind="observe")
    t0 = time.time()
    with cf.ThreadPoolExecutor(50) as ex:
        rs = list(ex.map(lambda _: http("POST", None, base()), range(150)))
    dt = time.time() - t0
    sts = sorted(set(r["status"] for r in rs))
    lat = sorted(r["ms"] for r in rs)
    rec(f"{g}-par", g, "150 envios con 50 en paralelo", sts == [201], "todos 201",
        f"estados={sts} total={dt:.1f}s ({150 / dt:.1f} req/s) p50={lat[74]} ms p95={lat[142]} ms max={lat[-1]} ms", kind="observe")


# ------------------------------------------------------------------ DB / trace verification
def verify():
    g = "G9-trazabilidad"
    existing = set(q("select request_id from reportes").split())
    norm = lambda s: s.lower().strip()  # noqa: E731
    miss = [r for r in results if r["request_id"] and rids_with_row.get(r["request_id"]) is True and norm(r["request_id"]) not in existing]
    rec(f"{g}-01", g, "cada caso que debia crear fila la creo", not miss, "0 casos sin fila", f"{len(miss)} sin fila: {[m['id'] for m in miss][:5]}")
    unexpected = [r for r in results if r["request_id"] and rids_with_row.get(r["request_id"]) is False and norm(r["request_id"]) in existing]
    rec(f"{g}-02", g, "ningun rechazo (400/422/413) dejo fila", not unexpected, "0 filas indebidas", f"{len(unexpected)}: {[m['id'] for m in unexpected][:5]}")
    total_rows = q("select count(*) from reportes")
    dup = q("select count(*) from (select request_id from reportes group by 1 having count(*)>1) t")
    rec(f"{g}-03", g, "ningun UUID repetido en reportes", dup == "0", "0 duplicados", f"{dup} (de {total_rows} filas)")
    codes = q("select count(*)-count(distinct codigo_publico) from reportes")
    rec(f"{g}-04", g, "codigos publicos unicos", codes == "0", "0 repetidos", codes)
    gaps = q("select coalesce(max(id),0)-count(*) from reportes")
    rec(f"{g}-05", g, "huecos en la numeracion de reportes", gaps == "0", "0 (informativo)", f"{gaps} hueco(s) acumulado(s)", kind="observe",
        note="los intentos simultaneos con el mismo UUID pueden consumir valores de la secuencia")
    nulls = q("select count(*) from bitacora_intentos where request_id is null")
    rec(f"{g}-06", g, "intentos con UUID invalido se registran con request_id nulo", int(nulls or 0) > 0, ">0 filas nulas", nulls, kind="observe")
    orphan = q("select count(*) from bitacora_intentos b where ejecucion_id is null or b.http_status is null")
    rec(f"{g}-07", g, "toda fila de bitacora trae ejecucion y HTTP", orphan == "0" or orphan == "1", "0 (la fila de prueba de permisos no cuenta)", orphan)
    exe = q("select count(*) from execution_entity where \"workflowId\"='miraReportes001'", N8N_DB)
    bit = q("select count(*) from bitacora_intentos where ejecucion_id is not null")
    meta503 = q("select count(*) from execution_metadata where key='http_status' and value='503'", N8N_DB)
    bit_not_logged = int(exe) - int(bit)
    rec(f"{g}-08", g, "toda ejecucion de n8n tiene fila de bitacora, salvo los intentos con la BD caida o la bitacora rota",
        bit_not_logged == NOLOG["n"], f"ejecuciones - bitacora = {NOLOG['n']} (intentos que no podian registrarse)",
        f"ejecuciones={exe} bitacora={bit} sin_bitacora={bit_not_logged} (503 en n8n={meta503}; los 503 con la BD arriba si quedan en bitacora)")
    # cross-database comparison: export both sides and compare in Python
    meta = dict(x.split("|") for x in q("select \"executionId\"||'|'||value from execution_metadata where key='http_status'", N8N_DB).split())
    bits = dict(x.split("|") for x in q("select ejecucion_id||'|'||http_status from bitacora_intentos where ejecucion_id ~ '^[0-9]+$'").split())
    diff = [k for k, v in bits.items() if meta.get(k) not in (None, v)]
    rec(f"{g}-09", g, "el HTTP de la bitacora coincide con el HTTP guardado en la ejecucion de n8n", not diff, "0 diferencias",
        f"{len(diff)} diferencia(s) de {len(bits)} comparadas")
    # panel queries
    prio = q("select prioridad||'='||count(*) from reportes group by prioridad order by prioridad").replace("\n", " ")
    tot = q("select count(*) from execution_entity where \"workflowId\"='miraReportes001'", N8N_DB)
    e5 = q("select count(*) from execution_metadata where key='http_status' and value ~ '^5'", N8N_DB)
    rate = f"{100 * int(e5) / int(tot):.2f}" if int(tot) else "sin datos"
    rec(f"{g}-10", g, "consultas de los paneles (informativo)", True, "-", f"reportes por prioridad: {prio} | 5xx={e5} de {tot} intentos = {rate}%", kind="observe")


def main():
    print("webhook:", BASE)
    t0 = time.time()
    groups = [("G1", g1), ("G2", g2), ("G3", g3), ("G4", g4), ("G5", g5), ("G6", g6), ("G7", g7), ("G8", g8), ("G11", g11), ("G14", g14), ("G10", g10), ("G12", g12), ("G13", g13)]
    only = os.environ.get("ONLY")
    for name, fn in groups:
        if only and name not in only.split(","):
            continue
        counter["n"] = 0
        n0 = len(results)
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            rec(f"{name}-ERR", name, f"error en el grupo {name}", False, "sin excepciones", repr(e)[:200])
        sub = results[n0:]
        print(f"{name}: {len(sub)} casos, FAIL={sum(r['status'] == 'FAIL' for r in sub)} INFO={sum(r['status'] == 'INFO' for r in sub)}")
        sys.stdout.flush()
    time.sleep(3)
    counter["n"] = 0
    if not only or "G9" in only.split(","):  # conciliation only makes sense after a full, isolated run
        verify()
    json.dump({"base": BASE, "seconds": round(time.time() - t0, 1), "results": results}, open(RESULTS, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    tot = len(results)
    print(f"TOTAL {tot}: PASS={sum(r['status'] == 'PASS' for r in results)} FAIL={sum(r['status'] == 'FAIL' for r in results)} "
          f"INFO={sum(r['status'] == 'INFO' for r in results)} en {time.time() - t0:.0f}s -> {RESULTS}")
    for r in results:
        if r["status"] == "FAIL":
            print("FAIL", r["id"], "|", r["name"], "| esperado:", r["expect"], "| actual:", r["actual"])


if __name__ == "__main__":
    main()
