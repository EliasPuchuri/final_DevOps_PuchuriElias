# Reportes de limpieza pública de Miraflores (prototipo académico)

Automatización que recibe un reporte, lo valida, lo clasifica con prioridad y plazo, lo guarda una sola vez y deja rastro desde el formulario hasta la base. Usa solo datos sintéticos. El alcance termina en la asignación inicial; no incluye la atención en campo.

**Estado:** T0–T6 hechas y verificadas en un entorno local aislado. Faltan la publicación (T7), la aceptación en el servidor (T8), el tablero (T9), la reproducción en limpio (T10) y los entregables (T11). Ver [Estado por tarea](#estado-por-tarea).

## Ruta rápida (entorno local)

1. Copiar `.env.example` a `.env` y completar **valores propios y aleatorios** (`openssl rand -hex 32` para `N8N_ENCRYPTION_KEY`). Nunca versionar `.env`.
2. `docker compose up -d --wait postgres n8n`
3. Abrir `http://127.0.0.1:5678` y crear la cuenta de propietario de n8n (una sola vez).
4. Importar credencial y workflow:
   ```sh
   set -a; . ./.env; set +a
   sh scripts/n8n-import.sh
   ```
5. Esperar a que el webhook responda (tras un reinicio devuelve `404` unos segundos aunque n8n ya esté "ready").
6. Verificar:
   ```sh
   WEBHOOK_URL=http://127.0.0.1:18080/webhook/reportes sh tests/http/acceptance.sh
   ```
   Resultado esperado: `ALL PASS` (P01–P10). Esa URL pasa por nginx, como en producción; `127.0.0.1:5678` es el webhook directo de n8n y no aplica la validación previa.

## Cómo fluye un reporte

```
Navegador ──> Caddy ──> nginx (web) ──POST /webhook/reportes──> n8n ──> PostgreSQL registrar_reporte()
                          │                                        │            │
                          └── formulario estático                  │◄─ respuesta única
                                                                   └── bitácora + historial de ejecuciones
```

`nginx` es la **validación previa**: solo deja pasar `POST /webhook/reportes` (cuerpo máximo 16 KB) y bloquea el editor y el resto de rutas de n8n. Lo reenvía como `text/plain` para que n8n no rechace un JSON roto con su propio `422` (ver E2).

Por ahora funcionan formulario, nginx, n8n y PostgreSQL en local; la publicación por Caddy y el túnel llega en T7. En el servidor el tráfico entra así: Cloudflare → `cloudflared` → Caddy compartido → `mira-web:80`.

## Reparto de reglas entre capas

| Capa | Qué decide |
|---|---|
| n8n | Formato de los campos (UUID, distrito, categoría, longitudes, booleano, bolsas), jurisdicción (`422 FUERA_DE_JURISDICCION`), enrutamiento por resultado, armado de la respuesta HTTP única, bitácora y código HTTP en la ejecución |
| PostgreSQL | Catálogo de sectores (`422 SECTOR_NO_HABILITADO`), tabla de prioridad/cola/plazo, unicidad del UUID, clasificación de duplicado (`200`) y conflicto (`409`), cálculo de la fecha límite |

La regla de prioridad vive **solo** en SQL (`registrar_reporte()`); n8n no la repite.

### Resultados HTTP

| HTTP | Código | Cuándo |
|---|---|---|
| 201 | — (`duplicado=false`) | Reporte nuevo |
| 200 | — (`duplicado=true`) | Mismo UUID y mismos datos normalizados |
| 400 | `DATOS_INVALIDOS` | Formato inválido o cuerpo que no es JSON |
| 409 | `IDENTIFICADOR_EN_CONFLICTO` | Mismo UUID, datos distintos |
| 422 | `FUERA_DE_JURISDICCION` / `SECTOR_NO_HABILITADO` | Distrito distinto de Miraflores / sector inexistente o inactivo |
| 503 | `ERROR_PERSISTENCIA` | La base no pudo confirmar el registro |

### Prioridad (primera condición aplicable)

| Condición | Prioridad | Cola | Plazo |
|---|---|---|---|
| Obstrucción | URGENTE | COORDINACION_OPERATIVA | 4 h |
| VOLUMINOSO | PROGRAMADA | RECOJO_ESPECIAL | 48 h |
| ACUMULACION con 5 bolsas o más | ALTA | LIMPIEZA_PUBLICA | 12 h |
| Resto admitido | NORMAL | LIMPIEZA_PUBLICA | 24 h |

El plazo se cuenta en horas corridas desde el registro. Las fechas se muestran en hora de Lima.

## Estructura del repositorio

| Ruta | Contenido |
|---|---|
| `docker-compose.yml` | `postgres` (16), `n8n` (1.123.27 fija) y `web` (nginx) |
| `nginx/default.conf` | Punto de entrada: formulario estático y única ruta de webhook permitida |
| `db/init/` | Se ejecutan solo al crear un volumen vacío: base de n8n, esquema y función, rol `mira_app` |
| `db/tests/` | `01_registrar_reporte.sql` (pruebas SQL) y `02_concurrency.sh` (intentos solapados) |
| `workflow/miraflores-reportes.json` | Workflow de n8n exportado y saneado (15 nodos) |
| `scripts/n8n-import.sh` | Importa credencial y workflow, activa y reinicia n8n |
| `scripts/export-workflow.sh` | Exporta el workflow y conserva solo los campos portables |
| `tests/http/acceptance.sh` | Casos P01–P10 contra el webhook |
| `tests/http/p11_failure.sh` | Caso P11 (solo en entornos aislados) |
| `web/` | Formulario: `index.html`, `styles.css`, `app.js` (HTML/CSS/JS puros, sin dependencias). El aviso académico es un modal que se muestra una vez por sesión del navegador (`sessionStorage`: se olvida al cerrar la pestaña) |
| `db/updates/` | Cambios de datos para bases ya creadas (p. ej. nombres reales de los sectores) |
| `docs/registro-de-errores.md` | Errores encontrados, causa, solución y estado |
| `docs/sectores-y-distritos.md` | Sectores reales de Miraflores usados en el catálogo, fuente y salvedades |

## Pruebas

| Prueba | Comando | Qué demuestra |
|---|---|---|
| SQL | `psql -v ON_ERROR_STOP=1 -d miraflores -f db/tests/01_registrar_reporte.sql` | Tabla de prioridad, duplicado, conflicto, sector inactivo, sin huecos de identificador. Termina con ROLLBACK |
| Concurrencia | `DB_EXEC="docker compose exec -T postgres" PGUSER=... PGDATABASE=miraflores sh db/tests/02_concurrency.sh` | 10 intentos simultáneos, mismo UUID: un `201`, nueve `200`, una fila |
| HTTP | `tests/http/acceptance.sh` | P01–P10 con HTTP y respuesta esperados |
| P11 | `tests/http/p11_failure.sh` | `503` sin fila, evidencia en n8n, recuperación y `201` con una sola fila |

> **P11 es destructivo para el rol `mira_app`.** Úselo solo en un entorno aislado de prueba, nunca en el servidor compartido.

### Cómo se simula el fallo de P11

Se deshabilita el rol de la aplicación (`ALTER ROLE mira_app NOLOGIN`) y se cierran sus sesiones. No se apaga Postgres porque n8n guarda sus propios metadatos en la misma instancia (con otro rol) y se caería también, sin poder registrar el intento.

## Trazabilidad

- **Bitácora (`bitacora_intentos`):** fecha, UUID (si es válido), HTTP, resultado, id de reporte (si aplica), id de ejecución de n8n y origen (`demo` o `prueba`). Registra altas, duplicados y rechazos mientras la base esté disponible. Se escribe **después** de responder y sigue ante un error, así que nunca oculta la respuesta.
- **Historial de n8n:** cada ejecución guarda `http_status`, `resultado`, `request_id`, `reporte_id` y `origen` en `execution_metadata`. Es la única evidencia de un `503`, porque la base estaba caída.
- **Origen:** las pruebas automáticas envían `X-Origen: prueba`. Es solo una etiqueta para separar métricas, no un control de seguridad (cualquiera podría enviarla).

## Seguridad y límites conocidos

- El webhook es público y sin autenticación (conocer el enlace no identifica a nadie). Hay que usar datos sintéticos y mostrar el aviso académico.
- `mira_app` solo puede ejecutar `registrar_reporte()`, insertar en la bitácora y leer `sectores`; **no puede leer `reportes`**.
- El editor de n8n escucha solo en `127.0.0.1`; nunca se publica. Desde nginx solo es alcanzable `POST /webhook/reportes` (el resto responde 403/404). Postgres no publica puertos.
- No hay límite de tasa ni protección contra abuso más allá de lo que aplique Cloudflare.
- Las contraseñas del entorno local de pruebas son solo de desarrollo. Antes de desplegar, generar valores nuevos y aleatorios.

## Despliegue en el servidor

**URL pública:** `https://finalpuchuri.famespinoza.net.pe` (formulario y `POST /webhook/reportes`). El editor de n8n no es público.

| Elemento | Detalle |
|---|---|
| Ubicación | `/srv/docker/miraflores` (clon de este repositorio; `.env` generado en el servidor, permisos `600`, no versionado) |
| Contenedores | `miraflores-postgres-1`, `miraflores-n8n-1`, `miraflores-web-1` |
| Entrada | Cloudflare → `cloudflared` → Caddy compartido → `mira-web:80` (red `mira-proxy`) |
| Caddy compartido | Se agregó un sitio al `Caddyfile` y la red `mira-proxy` a su `compose.yaml`; copias previas: `*.bak-pre-miraflores` |
| Editor de n8n | Solo por túnel SSH: `ssh -L 5679:127.0.0.1:5678 <usuario>@<servidor>` y luego `http://127.0.0.1:5679` |

**Actualizar (manual, tras comprobar las pruebas de la misma revisión):**
```sh
cd /srv/docker/miraflores && git pull
docker compose up -d --wait postgres n8n web
set -a; . ./.env; set +a; sh scripts/n8n-import.sh </dev/null   # solo si cambió el workflow
```

**Primera vez:** crear el propietario de n8n (por el túnel o con `POST /rest/owner/setup`) antes de ejecutar `scripts/n8n-import.sh`.

**Datos de prueba en producción:** la prueba de humo dejó el reporte `MIR-000001` (origen `prueba`). No se debe simular una caída en el servidor compartido; P11 se ejecuta solo en el entorno aislado (T8).

## Estado por tarea

| Tarea | Estado |
|---|---|
| T0 Inventario del servidor | Hecha (solo lectura) |
| T1 Base Compose | Hecha |
| T2 Persistencia e idempotencia | Hecha y probada en local |
| T3 n8n y trazabilidad | Hecha en local |
| T4 Workflow y decisiones | Hecha; P01–P10 pasan en local |
| T5 Bitácora y recuperación | Hecha; P11 pasa en local |
| T6 Formulario | Hecho; alta, duplicado, conflicto y reintento tras `503` verificados desde el navegador en local |
| T7 Publicación (Caddy, túnel) | Hecha; URL pública activa y prueba de humo `201` verificada (ver [Despliegue](#despliegue-en-el-servidor)) |
| T8 Aceptación en práctica aislada | Pendiente |
| T9 Tablero de Grafana | Pendiente |
| T10 Respaldo y reproducción en limpio | Pendiente |
| T11 Entregables y sustentación | Pendiente |

**Importante:** todo lo verificado hasta ahora se ejecutó en una máquina local, no en el servidor. Ver [docs/registro-de-errores.md](docs/registro-de-errores.md) para los errores encontrados y lo que sigue abierto.
