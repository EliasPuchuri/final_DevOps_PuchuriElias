# Registro de errores y decisiones

Qué falló, por qué, cómo se resolvió y qué sigue abierto. Los hechos de esta página se observaron en un entorno local aislado (ver el [README](../README.md)).

**Abierto hoy:** solo [E7](#e7--secretos-del-archivo-de-ejemplo) (revisión de `.env.example`).

| ID | Error | Estado |
|---|---|---|
| E1 | Nombre de categoría incorrecto (`OMISION`) | Corregido |
| E2 | JSON malformado devuelve `422` en lugar de `400` | Corregido (verificado en local) |
| E3 | Huecos en los códigos públicos | Corregido |
| E4 | El export del workflow filtraba el correo del propietario | Corregido |
| E5 | Versión de n8n flotante | Corregido |
| E6 | Webhook en `404` justo después de reiniciar | Documentado |
| E7 | Secretos del archivo de ejemplo | **Abierto** |
| E8 | Fallo de P11: por qué no se apaga Postgres | Decisión de diseño |
| E9 | Problemas de herramientas en Git Bash | Documentado |
| E10 | Tras un despliegue, el navegador mostraba la página sin estilos | Corregido |

---

## E1 — Nombre de categoría incorrecto

- **Qué pasó:** el esquema y las pruebas usaban `OMISION`. El enunciado define `OMISION_RECOJO`.
- **Causa:** el plan decía solo «Omisión» y se asumió un nombre.
- **Cómo se detectó:** al leer el enunciado y contrastarlo con el plan.
- **Solución:** se corrigió el CHECK del esquema y las pruebas; se repitieron las pruebas SQL y la de concurrencia.
- **Lección:** los identificadores salen del enunciado, no de suposiciones.

## E2 — JSON malformado devuelve `422` en lugar de `400`

**Explicación corta:** cuando alguien envía un JSON roto declarado como `application/json`, n8n lo rechaza con su propio `422` **antes** de ejecutar el workflow. El enunciado pide `400 DATOS_INVALIDOS`, y `422` está reservado para fuera de jurisdicción y sector no habilitado.

- **Qué se observó:**

  | Entrada | Resultado |
  |---|---|
  | `{bad json` como `application/json` | `422` con `Failed to parse request body` (respuesta de n8n, no del workflow) |
  | Cuerpo vacío | `400 DATOS_INVALIDOS` |
  | `[]` o `{"request_id":"x"}` | `400 DATOS_INVALIDOS` |
  | JSON roto como `text/plain` | `400 DATOS_INVALIDOS` |

- **Causa:** el analizador de cuerpo de n8n corre antes del nodo Webhook. Ninguna opción del nodo lo evita.
- **Solución en dos piezas:**
  1. El webhook recibe el cuerpo crudo (`rawBody`) y un nodo Code lo interpreta; cualquier cuerpo no JSON devuelve `400`.
  2. El `nginx` del servicio `web` (`nginx/default.conf`) es la **validación previa**: solo acepta `POST /webhook/reportes`, limita el cuerpo a 16 KB y lo reenvía a n8n como `text/plain`. Así n8n no ejecuta su analizador JSON y el workflow decide.
- **Por qué en nginx y no en Caddy:** se prueba hoy en local, no depende de editar el Caddy compartido y deja a Caddy con un único `reverse_proxy` hacia `mira-web:80`.
- **Verificado en local:** JSON roto declarado como `application/json` → `400 DATOS_INVALIDOS`; P01–P10 y P11 siguen pasando a través de nginx.
- **Efecto adicional (seguridad):** nginx es el único punto de entrada y bloquea el resto de n8n.

  | Petición | Resultado |
  |---|---|
  | `GET /webhook/reportes` | 403 |
  | `POST /webhook/otro` y `/webhook-test/reportes` | 404 |
  | `/rest/settings` y `/signin` (editor) | 404 |
  | Cuerpo de más de 16 KB | 413 |

- **Limitación:** la validación se limita a JSON bien formado; el resto de las reglas sigue en el workflow. Una solicitud rechazada por nginx (403, 404, 413) no deja ejecución en n8n.

## E3 — Huecos en los códigos públicos

- **Qué pasó:** `INSERT ... ON CONFLICT DO NOTHING` consume un valor de la secuencia aunque no inserte. Cada reintento duplicado "quemaba" un número, y el código `MIR-xxxxxx` mostraba saltos.
- **Solución:** `registrar_reporte()` busca el UUID antes de insertar. El `INSERT ... ON CONFLICT` queda como árbitro ante intentos solapados, que es lo que garantiza una sola fila.
- **Prueba:** un reintento duplicado seguido de un alta nueva da identificadores consecutivos.
- **Resto:** un solapamiento real todavía puede dejar un hueco aislado. Es cosmético y no afecta la unicidad.

## E4 — El export del workflow filtraba datos de la cuenta

- **Qué pasó:** `n8n export:workflow` incluye un campo `shared` con el nombre y el correo del propietario de la instancia.
- **Solución:** `scripts/export-workflow.sh` conserva solo `id`, `name`, `active`, `nodes`, `connections` y `settings`. Se verificó que el JSON no contiene `@` ni contraseñas.
- **Regla:** no exportar a mano; usar el script.

## E5 — Versión de n8n flotante

- **Qué pasó:** la imagen se resolvía por la etiqueta `1`, que cambia con el tiempo.
- **Riesgo:** `execution_metadata` y los nodos podían comportarse distinto en el servidor.
- **Solución:** imagen fija `n8nio/n8n:1.123.27`.

## E6 — Webhook en `404` justo después de reiniciar

- **Qué pasó:** tras reiniciar n8n, `/healthz/readiness` ya responde `200`, pero el webhook devuelve `404` unos segundos.
- **Causa:** los webhooks de producción se registran después de que n8n está listo.
- **Mitigación:** los scripts y pruebas deben **sondear el webhook** y no confiar solo en `readiness`.

## E7 — Secretos del archivo de ejemplo

- **Qué pasó:** al revisar el entorno se compartió un bloque de variables con valores débiles y repetidos (una misma cadena para la contraseña de la base de n8n y para `N8N_ENCRYPTION_KEY`).
- **Riesgos:**
  - `.env.example` se versiona: si contiene valores reales, quedan en el historial de git y en la entrega.
  - `N8N_ENCRYPTION_KEY` cifra las credenciales guardadas; debe ser aleatoria, y cambiarla después deja las credenciales ilegibles.
- **Estado:** no se pudo verificar el contenido de `.env.example` (los permisos de la herramienta impiden leerlo). **Se dejó fuera del commit.**
- **Acciones pendientes del propietario:**
  - [ ] Dejar `.env.example` solo con marcadores (`change-me`).
  - [ ] Generar valores nuevos y aleatorios (`openssl rand -hex 32`) antes del despliegue.
  - [ ] No reutilizar en otros servicios ninguna contraseña compartida en conversaciones.

## E8 — Cómo se simula el fallo de P11

- **Problema:** el enunciado pide un fallo de persistencia antes de guardar, con n8n registrando el intento.
- **Descartado:** apagar Postgres. n8n guarda su historial en la misma instancia (otro rol) y se caería, sin poder registrar nada.
- **Decisión:** deshabilitar el rol `mira_app` (`NOLOGIN`) y cerrar sus sesiones; la conexión de la aplicación falla y n8n sigue operando.
- **Resultado observado:** `503 ERROR_PERSISTENCIA`, ninguna fila, ejecución de n8n con `http_status=503`; tras restaurar, el mismo UUID devuelve `201` y hay una fila.
- **Consecuencia:** el `503` no aparece en la bitácora (la base estaba caída). La ejecución de n8n es la única evidencia, como exige el enunciado.
- **Aviso:** `tests/http/p11_failure.sh` es destructivo para ese rol. No ejecutarlo en el servidor compartido.

## E9 — Problemas de herramientas en Git Bash

| Síntoma | Causa | Solución |
|---|---|---|
| `ENOENT ... C:/Users/.../Temp/cred.json` al importar | Git Bash convierte rutas que empiezan con `/` en rutas de Windows | `export MSYS_NO_PATHCONV=1` |
| `rm: Operation not permitted` en `/tmp` del contenedor | `docker cp` deja el archivo con otro propietario | Enviar archivos por entrada estándar (`exec ... sh -c 'cat > ...'`) |
| Fin de línea CRLF en scripts `.sh` | `core.autocrlf` en Windows | `.gitattributes` fuerza LF en `.sh`, `.sql`, `.yml` y `.json` |

## E10 — Página sin estilos tras un despliegue (caché del navegador)

- **Qué pasó:** después de publicar la nueva interfaz, la URL pública mostraba el HTML nuevo con los estilos y el script **viejos**: sin modal y con el diseño roto. El servidor entregaba los archivos nuevos (`200`).
- **Causa:** nginx no enviaba `Cache-Control`. Con solo `Last-Modified`, el navegador reutiliza por heurística las copias que ya tenía de `styles.css` y `app.js`.
- **Cómo se detectó:** la verificación visual en el navegador tras el despliegue. Las comprobaciones con `curl` no lo habrían mostrado.
- **Solución:** `expires -1` en nginx (`Cache-Control: no-cache`, el navegador revalida con ETag en cada carga) y versión en las URL de los recursos (`styles.css?v=2`, `app.js?v=2`).
- **Verificado:** los encabezados por la URL pública incluyen `cache-control: no-cache` y la política de seguridad; el sitio se ve bien tras recargar.
- **Lección:** verificar siempre el resultado visual de un despliegue en un navegador, no solo los códigos HTTP. Subir el número `?v=` cuando cambien los recursos.
- **Nota operativa:** el archivo `nginx/default.conf` se monta como un solo archivo; tras un `git pull` hay que reiniciar el contenedor `web` para que lo vea.

---

## Verificaciones que pasaron (entorno local)

| Verificación | Resultado |
|---|---|
| Pruebas SQL (incluida la de sin huecos) | Pasan |
| Concurrencia, 10 intentos con el mismo UUID | 1 × `201`, 9 × `200`, 1 fila |
| HTTP P01–P10 | `ALL PASS`; P06–P08 sin fila; P09/P10 sin segunda fila |
| P11 | `P11 PASS` |
| Bitácora de P01–P10 | 10 filas, con ejecución de n8n y origen |
| Fallo de bitácora | La respuesta sigue siendo `201`; el reporte se guarda |
| Privilegios de `mira_app` | No puede leer `reportes` |
| Exposición de puertos | Editor en `127.0.0.1`; Postgres sin puertos publicados |

## Pendiente de verificar en el servidor

- Que el Caddy compartido enrute al alias `mira-web` y que la validación de E2 siga funcionando detrás de Cloudflare.
- La repetición de P01–P11 en un entorno aislado del servidor (T8).
- Que `$execution.customData` se comporte igual con la versión fija (T3/T8).
