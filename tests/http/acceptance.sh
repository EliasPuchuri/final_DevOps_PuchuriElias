#!/bin/sh
# HTTP acceptance cases P01-P10 against the webhook. P11 needs a controlled DB failure (see T5).
# Usage: WEBHOOK_URL=http://127.0.0.1:5678/webhook/reportes sh tests/http/acceptance.sh
set -u
: "${WEBHOOK_URL:?set WEBHOOK_URL}"
FAIL=0

uuid() { python -c "import uuid;print(uuid.uuid4())"; }

# post <json> -> sets HTTP and BODY
post() {
  OUT=$(curl -s -w '\n%{http_code}' -X POST "$WEBHOOK_URL" -H 'Content-Type: application/json' -H 'X-Origen: prueba' -d "$1")
  HTTP=$(printf '%s' "$OUT" | tail -n1)
  BODY=$(printf '%s' "$OUT" | sed '$d')
}

# check <id> <expected http> <expected substring...>
check() {
  id=$1; want=$2; shift 2
  ok=1
  [ "$HTTP" = "$want" ] || ok=0
  for s in "$@"; do printf '%s' "$BODY" | grep -q "$s" || ok=0; done
  if [ $ok -eq 1 ]; then echo "PASS $id  HTTP $HTTP"; else echo "FAIL $id  HTTP $HTTP (want $want $*)"; echo "     $BODY"; FAIL=1; fi
}

mk() { # mk <uuid> <distrito> <sector|-> <categoria> <obstruccion> <bolsas|null>
  sector=""; [ "$3" != "-" ] && sector="\"sector\":\"$3\","
  printf '{"request_id":"%s","distrito":"%s",%s"categoria":"%s","referencia":"Av. Larco 123","descripcion":"Descripcion de prueba valida","obstruccion":%s,"bolsas":%s}' \
    "$1" "$2" "$sector" "$4" "$5" "$6"
}

post "$(mk "$(uuid)" MIRAFLORES M01 ACUMULACION false 4)"
check P01 201 '"prioridad":"NORMAL"' '"cola":"LIMPIEZA_PUBLICA"' '"plazo_horas":24' '"duplicado":false'

U02=$(uuid)
P02=$(mk "$U02" MIRAFLORES M01 ACUMULACION false 5)
post "$P02"
check P02 201 '"prioridad":"ALTA"' '"cola":"LIMPIEZA_PUBLICA"' '"plazo_horas":12'
CODE02=$(printf '%s' "$BODY" | sed 's/.*"codigo_publico":"\([^"]*\)".*/\1/')
LIM02=$(printf '%s' "$BODY" | sed 's/.*"fecha_limite_iso":"\([^"]*\)".*/\1/')

post "$(mk "$(uuid)" MIRAFLORES M01 VOLUMINOSO true null)"
check P03 201 '"prioridad":"URGENTE"' '"cola":"COORDINACION_OPERATIVA"' '"plazo_horas":4'

post "$(mk "$(uuid)" MIRAFLORES M01 VOLUMINOSO false null)"
check P04 201 '"prioridad":"PROGRAMADA"' '"cola":"RECOJO_ESPECIAL"' '"plazo_horas":48'

post "$(mk "$(uuid)" MIRAFLORES M01 OMISION_RECOJO false null)"
check P05 201 '"prioridad":"NORMAL"' '"cola":"LIMPIEZA_PUBLICA"' '"plazo_horas":24'

post "$(mk "$(uuid)" SURQUILLO - OMISION_RECOJO false null)"
check P06 422 '"codigo":"FUERA_DE_JURISDICCION"'

post "$(mk "$(uuid)" MIRAFLORES M03 OMISION_RECOJO false null)"
check P07 422 '"codigo":"SECTOR_NO_HABILITADO"'

post "$(mk "$(uuid)" MIRAFLORES M01 ACUMULACION false 0)"
check P08 400 '"codigo":"DATOS_INVALIDOS"'

post "$P02"
check P09 200 '"duplicado":true' "\"codigo_publico\":\"$CODE02\"" "\"fecha_limite_iso\":\"$LIM02\""

post "$(mk "$U02" MIRAFLORES M01 ACUMULACION false 6)"
check P10 409 '"codigo":"IDENTIFICADOR_EN_CONFLICTO"'

[ $FAIL -eq 0 ] && echo "ALL PASS" || { echo "SOME FAILED"; exit 1; }
