# Reporte de pruebas: formulario y flujo de reportes de limpieza pública

**Fecha:** 27/11/2026 · **Versión probada:** commit `5ed7546` más las correcciones de esta ronda (sin commitear al momento de escribir este informe) · **Entorno:** stacks aislados y limpios (n8n 1.123.27, PostgreSQL 16, nginx 1.27), más una verificación en producción previa a las correcciones.

## 1. Veredicto

**El flujo cumple todas las reglas del enunciado.** Los once casos P01–P11 pasan con el HTTP, el resultado y el efecto en la base esperados.

Las pruebas encontraron **13 hallazgos** (12 en la primera ronda y uno más, F-13, al reconstruir el entorno en la segunda). **Los 8 accionables se corrigieron y se volvieron a probar; los 5 informativos se documentan como aceptados, con su razón.**

| Resultado de la suite | Antes de corregir | Después de corregir |
|---|---|---|
| Verificaciones | 235 | 247 |
| PASS | 226 | 246 |
| FAIL | 7 | 0 |
| INFO (comportamiento no definido por el enunciado) | 2 | 1 |

| # | Severidad | Hallazgo | Estado |
|---|---|---|---|
| F-01 | **Alta** | Tras enviar un reporte y recargar, el siguiente reporte distinto recibía `409` | **Corregido** y verificado |
| F-02 | Media | Emojis y el carácter NUL daban `503` (o `400`) incorrectos | **Corregido** y verificado |
| F-03 | Media | La tarjeta de resultado anterior seguía visible tras un envío inválido | **Corregido** y verificado |
| F-04 | Media | Sin limitación de tasa | **Corregido** (nginx) y verificado en local; falta confirmarlo en producción |
| F-05 | Baja | Con n8n caído (`502`) no había botón de reintento | **Corregido** y verificado |
| F-06 | Baja | nginx revelaba su versión | **Corregido** y verificado |
| F-07 | Baja | Contraste insuficiente en bordes de campos y en el texto de ejemplo | **Corregido** y verificado |
| F-13 | Media | El script de importación falla en una instalación nueva (carrera con las migraciones de n8n) | **Corregido** y verificado (hallazgo de la segunda ronda) |
| F-08 | Informativo | Capacidad | Aceptado |
| F-09 | Informativo | Huecos de numeración | Aceptado |
| F-10 | Informativo | Comportamientos no definidos por el enunciado | Aceptado y documentado |
| F-11 | Informativo | La función SQL no valida por sí misma | Aceptado (mitigado por F-02) |
| F-12 | Informativo | Hallazgos de entorno | Documentado |

## 2. Qué se probó y cómo

- **Suite automática** `tests/http/suite.py` (solo biblioteca estándar de Python): **247 verificaciones** en la corrida final, con resultado esperado independiente del SQL (la tabla de prioridades se recalcula en la propia prueba). Antes de corregir se ejecutó completa tres veces sobre una base vacía: los 6 fallos de texto (F-02) se repitieron idénticos en todas las corridas, y las demás diferencias fueron errores de la propia suite (sección 6).
- **Formulario en un navegador real** (Chrome) con un arnés de pruebas dentro de la página, pulsaciones reales de teclado y fallos de infraestructura provocados (n8n detenido, n8n pausado, nginx detenido).
- **Producción**: un alta hecha a mano desde el formulario publicado, y comprobación de fila, bitácora y ejecución en el servidor.
- **Evidencias** en `docs/evidencias/`: `resultados-suite-inicial.json` (antes de corregir), `resultados-suite-final.json` (después) y capturas. Cada caso trae su UUID, lo esperado y lo observado.

Cada caso se marca **PASS**, **FAIL** (desvío de algo que el enunciado o la seguridad exigen) o **INFO** (comportamiento que el enunciado no define; se registra pero no se califica).

**El entorno de pruebas es aislado a propósito:** varios grupos deshabilitan el rol de la aplicación, bloquean tablas o apagan contenedores. No se ejecutaron contra el servidor compartido.

## 3. Resultados de la suite automática (corrida final)

| Área | Casos | PASS | FAIL | INFO | FAIL antes de corregir |
|---|---|---|---|---|---|
| Tabla de prioridad (matriz completa) | 17 | 17 | 0 | 0 | 0 |
| Normalización y entradas válidas atípicas | 22 | 22 | 0 | 0 | 0 |
| Validación de campos (400) y límites | 61 | 61 | 0 | 0 | 6 |
| Jurisdicción y sector (422) y su orden | 12 | 12 | 0 | 0 | 0 |
| Identificador, forma del cuerpo y Content-Type | 29 | 29 | 0 | 0 | 0 |
| Idempotencia: duplicado (200) y conflicto (409) | 17 | 17 | 0 | 0 | 0 |
| Intentos simultáneos | 3 | 3 | 0 | 0 | 0 |
| Transporte, rutas, métodos y encabezados | 37 | 37 | 0 | 0 | 0 |
| Permisos del rol de la aplicación en PostgreSQL | 14 | 14 | 0 | 0 | 0 |
| Errores de datos de la base traducidos a 400 | 2 | 2 | 0 | 0 | — |
| Fallos inducidos (503, recuperación, bitácora, BD lenta) | 16 | 16 | 0 | 0 | 0 |
| Rendimiento y carga | 2 | 2 | 0 | 0 | 0 |
| Límite de tasa por cliente | 5 | 5 | 0 | 0 | — |
| Trazabilidad y conciliación fila ↔ bitácora ↔ n8n | 10 | 9 | 0 | 1 | 1 |
| **Total** | **247** | **246** | **0** | **1** | **7** |

El grupo de límite de tasa solo se ejecuta contra un stack con el límite por defecto (`RATE_TEST=1`); el resto se ejecuta con el límite relajado, porque genera ráfagas a propósito.

### 3.1 Casos del enunciado

| Caso | Qué se envió | Esperado | Observado | Estado | Efecto en la base | Evidencia (caso · UUID) |
|---|---|---|---|---|---|---|
| P01 | Acumulación, 4 bolsas, sin obstrucción | 201 · NORMAL · LIMPIEZA_PUBLICA · 24 h | HTTP 201 MIR-000002 NORMAL/LIMPIEZA_PUBLICA/24h dup=False | PASS | una fila | `G1-prioridad-002` · `8a281dd1-df85-4f10-8785-d234f25145b5` |
| P02 | Acumulación, 5 bolsas, sin obstrucción | 201 · ALTA · LIMPIEZA_PUBLICA · 12 h | HTTP 201 MIR-000003 ALTA/LIMPIEZA_PUBLICA/12h dup=False | PASS | una fila | `G1-prioridad-003` · `6839d122-ce77-4358-92ca-2e257f8fa585` |
| P03 | Voluminoso con obstrucción | 201 · URGENTE · COORDINACION_OPERATIVA · 4 h | HTTP 201 MIR-000012 URGENTE/COORDINACION_OPERATIVA/4h dup=False | PASS | una fila | `G1-prioridad-012` · `335801fe-1de8-45a0-bea8-8cc8f31a8a86` |
| P04 | Voluminoso sin obstrucción | 201 · PROGRAMADA · RECOJO_ESPECIAL · 48 h | HTTP 201 MIR-000011 PROGRAMADA/RECOJO_ESPECIAL/48h dup=False | PASS | una fila | `G1-prioridad-011` · `61494f86-9f9d-42a3-ba0e-64cd3f746318` |
| P05 | Omisión de recojo sin obstrucción | 201 · NORMAL · LIMPIEZA_PUBLICA · 24 h | HTTP 201 MIR-000013 NORMAL/LIMPIEZA_PUBLICA/24h dup=False | PASS | una fila | `G1-prioridad-013` · `981ee200-2840-4624-9097-2f3e30529786` |
| P06 | Surquillo con datos válidos | 422 · FUERA_DE_JURISDICCION | HTTP 422 FUERA_DE_JURISDICCION | PASS | ninguna fila | `G4-jurisdiccion-001` · `47160c16-30be-4620-bdc7-78b6bcb67a23` |
| P07 | Miraflores, sector M03 inactivo | 422 · SECTOR_NO_HABILITADO | HTTP 422 SECTOR_NO_HABILITADO | PASS | ninguna fila | `G4-jurisdiccion-012` · `5b48d462-cc09-4438-b560-66ffadcfb468` |
| P08 | Acumulación con 0 bolsas, directo al webhook | 400 · DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS | PASS | ninguna fila | `G3-validacion-032` · `33d628bd-7f83-441b-ab2a-326dff8381df` |
| P09 | Reenviar P02 con el mismo UUID y datos | 200 · duplicado, mismo código y fecha límite | HTTP 200 MIR-000052 ALTA/LIMPIEZA_PUBLICA/12h dup=True | PASS | sigue una sola fila | `G6-idempotencia-002` · `418e6d8c-9030-42f7-be11-fd10cbd3e6bf` |
| P10 | Mismo UUID de P02 con 6 bolsas | 409 · IDENTIFICADOR_EN_CONFLICTO | HTTP 409 IDENTIFICADOR_EN_CONFLICTO | PASS | fila original intacta (5 bolsas, ALTA, 12 h) | `G6-idempotencia-005` · `418e6d8c-9030-42f7-be11-fd10cbd3e6bf` |
| P11a | Fallo de la base antes de guardar | 503 · ERROR_PERSISTENCIA | HTTP 503 ERROR_PERSISTENCIA | PASS | ninguna fila; el `503` queda en el historial de n8n | `G10-fallos-002` · `7ec32781-e85a-4ad0-a7d5-311e34e410c0` |
| P11b | Restaurar y repetir el mismo UUID | 201 | HTTP 201 MIR-000106 NORMAL/LIMPIEZA_PUBLICA/24h dup=False | PASS | una sola fila con ese UUID (`G10-fallos-cnt`) | `G10-fallos-007` · `7ec32781-e85a-4ad0-a7d5-311e34e410c0` |

P09 y P10 se ejecutaron sobre un alta equivalente a P02 (acumulación, 5 bolsas, sin obstrucción) creada dentro de su propio grupo, para poder comprobar la fila original sin depender del orden de otros casos. La evidencia de que el `503` de P11a queda en el historial de n8n se verificó por separado en la primera corrida: el UUID `b0e18024-e89f-4627-85f4-4eda6b073c31` tuvo la ejecución 1267 con `http_status=503` y la 1272 con `201`, una sola fila, y la bitácora solo contiene el `201` (la base estaba caída durante el `503`). En la corrida final lo cubre la conciliación `G9-trazabilidad-08/09`.

**P11 se simuló** deshabilitando el rol de la aplicación (`ALTER ROLE ... NOLOGIN` y cierre de sus sesiones), no apagando Postgres: n8n guarda su propio historial en la misma instancia y se caería también, sin poder registrar el intento.

### 3.2 Lo que quedó verificado

- **Prioridad:** las 17 combinaciones (categoría × obstrucción × 1, 4, 5, 6 y 50 bolsas, ambos sectores habilitados) dan prioridad, cola y plazo correctos, y la fecha límite lleva el desfase `-05:00` de Lima.
- **Orden de decisión:** formato (400) → jurisdicción (422) → catálogo (422) → UUID (200/409). Un distrito distinto de Miraflores con datos inválidos da `400`; con sector inactivo da `422` de jurisdicción; con un UUID existente y su sector deshabilitado después, gana el catálogo.
- **Idempotencia:** el reenvío normalizado (espacios, mayúsculas, UUID en mayúsculas) devuelve `200` con el mismo código y la misma fecha límite. Cada campo de negocio que cambia da `409`, y la fila original queda intacta.
- **Concurrencia:** 20 envíos simultáneos con el mismo UUID dan un solo `201`, 19 `200` y una fila. Con dos contenidos distintos a la vez (5 y 6 bolsas) queda una fila y cada respuesta es coherente con el ganador. 40 envíos con UUID distintos dan 40 filas con códigos únicos.
- **Fallos:** con la base caída, un reporte nuevo y un UUID existente dan `503`; los datos inválidos, otro distrito y un UUID inválido siguen respondiendo `400/422` (no necesitan la base). Al recuperar, el mismo UUID da `201` y queda una fila. Con la bitácora rota, el reporte se guarda y la respuesta no cambia. Un valor que la base rechaza por una restricción se informa como `400` y no como `503` (grupo G14).
- **Base lenta:** con la tabla bloqueada 9 s, un cliente que abandona a los 4 s **no pierde el reporte**: el servidor lo guarda y el reintento con el mismo UUID devuelve `200` duplicado. Con un bloqueo de 5 s la respuesta llega con `201` tras esperar.
- **Permisos de `mira_app`:** no puede leer `reportes` ni `bitacora_intentos`, ni insertar, actualizar o borrar directamente, ni hacer `TRUNCATE`, `DROP` o `CREATE`. Sí puede leer `sectores`, insertar en la bitácora y ejecutar `registrar_reporte()`.
- **Seguridad de transporte:** solo `POST /webhook/reportes` llega a n8n. `GET`, `HEAD`, `PUT`, `PATCH`, `DELETE` y `OPTIONS` dan `403` (`TRACE`, `405`). El editor, la API REST, `/webhook-test`, `/healthz`, archivos ocultos y rutas con `..` dan `404`/`400`. Un cuerpo mayor de 16 KB da `413`. La política de seguridad de contenido y `nosniff` están presentes, el encabezado `Server` ya no revela la versión, y una petición CORS de otro origen no recibe permiso.
- **Límite de tasa:** una ráfaga de 80 envíos válidos de un cliente se atiende hasta el cupo y el resto recibe `429` JSON con `Retry-After`; las filas creadas coinciden exactamente con los `201`. Otro cliente (otra IP real) no se ve afectado, el primero se recupera a los pocos segundos y un ritmo normal nunca se limita.
- **Trazabilidad:** el HTTP guardado en la bitácora coincide con el de la ejecución de n8n en todos los casos comparables (0 diferencia(s) de 500 comparadas). Conciliación de ejecuciones: ejecuciones=506 bitacora=500 sin_bitacora=6 (503 en n8n=3; los 503 con la BD arriba si quedan en bitacora).
- **Métricas de los paneles** (consulta de ejemplo sobre esta corrida): reportes por prioridad: ALTA=9 NORMAL=337 PROGRAMADA=2 URGENTE=7 | 5xx=3 de 506 intentos = 0.59%.

## 4. Formulario en el navegador

### 4.1 Primera ronda

| Bloque | Comprobaciones | Resultado |
|---|---|---|
| Aviso modal: aparece al entrar, foco dentro, etiquetas ARIA, botón y Esc lo cierran, queda en `sessionStorage` (no en `localStorage`), foco pasa al primer campo | 8 | Todas pasan |
| Validación: enviar vacío muestra 5 errores sin llamar al servidor, foco al primer campo inválido, `aria-invalid` | 3 | Todas pasan |
| Campos condicionales (sector solo en Miraflores, bolsas solo en acumulación, se limpian al ocultarse) | 9 | Todas pasan |
| Límites en el cliente: bolsas 0, -1, 51, 5,5 y vacío se rechazan; 1, 5 y 50 se aceptan; referencia 4/5/120/121; descripción 14/15/200/201; solo espacios; recorte; contadores | 20 | Todas pasan |
| Resultados legibles por prioridad (Alta, Urgente, Programada, Normal con su equipo y plazo en hora de Lima), sin códigos internos | 5 | Todas pasan |
| Idempotencia desde la interfaz: duplicado (`200`), conflicto (`409`), volver a los datos originales, «Empezar de nuevo» | 5 | Todas pasan |
| Rechazos: Surquillo y sector M03 con mensaje claro y sin reintento; el identificador no cambia tras un rechazo | 3 | Todas pasan |
| Doble clic: una sola petición; el botón se rehabilita | 2 | Todas pasan |
| Texto con HTML y `<script>`: no se ejecuta ni se inyecta | 1 | Pasa |
| Accesibilidad estructural: etiquetas, un `h1`, `lang="es"`, región `aria-live`, `fieldset`/`legend`, botones con texto, sin scripts ni estilos en línea | 8 | Todas pasan |
| Foco al resultado, sin `tabindex` positivo, orden de tabulación lógico | 3 | Pasan |
| Teclado real: Enter en un campo envía y valida; Enter en el área de texto inserta salto de línea | 2 | Pasan |
| Consola del navegador | 1 | Sin errores |
| Diseño móvil (iframe de 371 px): sin desplazamiento horizontal, opciones en una columna, márgenes de 16 px, botones de 51 px | 1 | Pasa |
| Contraste del texto (24 pares) y del anillo de foco (2), ambos modos | 26 | Todos pasan |
| Fallos de infraestructura: nginx caído → «Sin conexión» con reintento; n8n pausado → a los 15 s «Sin conexión» con reintento y el botón deshabilitado mientras tanto; el reintento con el mismo UUID crea una sola fila | 2 | Pasan |
| **Producción:** alta desde el formulario publicado | 1 | Pasa (`MIR-000002`) |
| Emojis de punta a punta; tarjeta anterior tras envío inválido; segundo reporte tras recargar; n8n caído (`502`); contraste de bordes y texto de ejemplo | 8 | **Fallaban** (F-01, F-02, F-03, F-05, F-07); ver 4.2 |

El control de «lado menor a 24 px» de los botones de opción (radios de 20 px) se descartó como falso positivo: toda la tarjeta de la opción es clicable.

**Producción, alta desde el formulario publicado** (antes de las correcciones). Se envió a mano desde `https://finalpuchuri.famespinoza.net.pe/` (el modal apareció al entrar). Resultado: `MIR-000002 · Alta · Limpieza pública · 12 h`. En el servidor: la fila `MIR-000002` (registrada 01:36, límite 13:36, hora de Lima), la bitácora `ejecución 5 · 201 · REGISTRADO · origen demo` y las cinco claves de `execution_metadata` (`http_status`, `origen`, `reporte_id`, `request_id`, `resultado`) corresponden al mismo UUID `1b8c3432-2904-42c3-9be3-d5c64fffba96`. Captura: `docs/evidencias/produccion-alta-formulario-publicado.jpg`.

### 4.2 Segunda ronda: verificación de las correcciones

Se repitió cada escenario que fallaba, sobre un stack nuevo construido desde cero con el código corregido.

| Hallazgo | Comprobación | Resultado |
|---|---|---|
| F-01 | Tras enviar y recargar, el identificador es nuevo; un segundo reporte **distinto** se registra con `201` (códigos distintos) y no queda envío pendiente | Pasa |
| F-01 | Con n8n caído: el envío queda **pendiente**; al recargar, el mismo identificador, el formulario completo restaurado (incluidos sector y bolsas, con sus contadores) y el aviso «Tienes un envío sin confirmar» | Pasa |
| F-01 | Al reintentar con n8n de vuelta: `201` con el mismo identificador, **una sola fila**, y al recargar de nuevo no hay nada pendiente | Pasa |
| F-03 | Tras un éxito, un envío inválido oculta la tarjeta anterior y muestra los errores | Pasa |
| F-02 | 3 emojis: rechazo claro en el cliente («entre 5 y 120 caracteres»), sin llegar al servidor ni dar un `503` engañoso | Pasa |
| F-02 | 61 emojis (61 caracteres): el contador marca `61 / 120` y el servidor responde `201` | Pasa |
| F-02 | Salto de línea en la descripción (permitido): `201`. Carácter de control: mensaje claro en el cliente | Pasan |
| F-04 | Ráfaga de 120 peticiones desde el navegador: parte atendida (`400`) y parte limitada (`429`); el formulario muestra «Demasiados envíos seguidos… Espera unos segundos» con botón de reintento y deja el envío pendiente | Pasa |
| F-04 | A los 7 s el reintento con el mismo identificador da `201` y limpia el pendiente | Pasa |
| F-05 | Con n8n caído: «El servicio no está disponible», código `HTTP 502`, **botón de reintento** y envío pendiente | Pasa |
| F-06 | Encabezado `Server: nginx` (sin versión); la política de seguridad y `Cache-Control` siguen presentes | Pasa |
| F-07 | Borde de campos 3,9:1 / 3,6:1 (claro) y 3,5:1 / 4,0:1 (oscuro); texto de ejemplo 5,9:1 (claro) y 8,7:1 (oscuro) | Pasa (mínimo 3:1 y 4,5:1) |

**Cuatro «fallos» de mi arnés en esta ronda no eran del producto** y se repitieron correctamente: reutilicé el mismo identificador con datos distintos (que da `409` por diseño; el mensaje ahora sugiere «Empezar de nuevo»), un `<input>` de texto elimina por sí mismo los saltos de línea que se le asignan, y mi primer intento de provocar el `429` iba por debajo del límite.

## 5. Hallazgos y resolución

### F-01 · Alta · Un segundo reporte, tras recargar, recibía `409` — **Corregido**

- **Qué pasaba:** el identificador del envío se guardaba en `sessionStorage` y sobrevivía a la recarga, pero el formulario se vaciaba. Quien enviaba un reporte, recargaba y enviaba **otro reporte distinto** reutilizaba el mismo UUID y recibía `409 IDENTIFICADOR_EN_CONFLICTO`. Captura del problema: `docs/evidencias/ui-conflicto-tras-recargar.jpg`.
- **Corrección** (`web/app.js`): el identificador es nuevo en cada carga de la página y solo se conserva mientras haya un envío **sin confirmar** (error del servidor, límite de tasa o falta de conexión). En ese caso se guarda también el contenido del formulario y, al recargar, se restaura para que el reintento use el mismo identificador y nunca cree un segundo reporte. Una respuesta definitiva lo libera. Además, el mensaje de `409` ahora indica «Si quieres enviar un reporte distinto, pulsa «Empezar de nuevo»».
- **Verificado:** sección 4.2.

### F-02 · Media · Emojis y NUL: errores de validación que se reportaban como fallo de persistencia — **Corregido**

- **Qué pasaba:** el workflow y el formulario contaban caracteres con `.length` de JavaScript (unidades UTF-16; un emoji vale 2), mientras PostgreSQL cuenta caracteres reales. Además, el carácter NUL no se puede guardar en `text`. Evidencia de la primera corrida:
  - referencia de 3 emojis (3 caracteres, <5): debe ser 400 (`G3-validacion-050`): antes → HTTP 503 ERROR_PERSISTENCIA; ahora → HTTP 400 DATOS_INVALIDOS
  - referencia de 61 emojis (61 caracteres, <=120): debe ser 201 (`G3-validacion-051`): antes → HTTP 400 DATOS_INVALIDOS; ahora → HTTP 201 MIR-000042 NORMAL/LIMPIEZA_PUBLICA/24h dup=False
  - descripcion de 8 emojis (8 caracteres, <15): debe ser 400 (`G3-validacion-052`): antes → HTTP 503 ERROR_PERSISTENCIA; ahora → HTTP 400 DATOS_INVALIDOS
  - descripcion de 101 emojis (101 caracteres, <=200): debe ser 201 (`G3-validacion-053`): antes → HTTP 400 DATOS_INVALIDOS; ahora → HTTP 201 MIR-000043 NORMAL/LIMPIEZA_PUBLICA/24h dup=False
  - descripcion con caracter NUL (\u0000) (`G3-validacion-054`): antes → HTTP 503 ERROR_PERSISTENCIA; ahora → HTTP 400 DATOS_INVALIDOS
  - referencia con caracter NUL (`G3-validacion-055`): antes → HTTP 503 ERROR_PERSISTENCIA; ahora → HTTP 400 DATOS_INVALIDOS
- **Efecto que tenía:** los textos «cortos» pasaban la validación y la base los rechazaba, así que el usuario recibía `503 ERROR_PERSISTENCIA` («Puedes reintentar») sin posibilidad de éxito; los textos «largos pero válidos» se rechazaban con `400`. En la corrida inicial, 4 de los 7 resultados `5xx` fueron de este origen y habrían inflado la tasa de errores del Panel 2.
- **Corrección:** (1) n8n y el formulario cuentan **puntos de código**; (2) se rechazan los caracteres de control y las cadenas mal formadas (referencia: ninguno; descripción: se permiten salto de línea y tabulador); (3) el nodo de error de persistencia distingue: un valor que la base rechaza (restricciones, codificación, tamaño) se devuelve como `400 DATOS_INVALIDOS`, y las caídas, permisos y tiempos de espera siguen siendo `503`.
- **Verificado:** los 6 casos pasan y se agregaron 5 más (control, DEL, salto de línea en la referencia, sustituto suelto). El grupo G14 fuerza un `CHECK` temporal en la base y confirma `400` y no `503`.
- **Nota de contrato:** el rechazo de caracteres de control es una regla nueva que el enunciado no menciona.

### F-03 · Media · La tarjeta de resultado anterior quedaba visible tras un envío inválido — **Corregido**

- **Corrección** (`web/app.js`): el resultado anterior se oculta al iniciar cualquier envío, sea válido o no. Verificado en 4.2.

### F-04 · Media · Sin limitación de tasa — **Corregido** (falta confirmarlo en producción)

- **Qué pasaba:** el endpoint es público, sin autenticación, y cada envío válido inserta una fila. Una ráfaga de 150 envíos (50 en paralelo) se aceptó completa.
- **Corrección** (`nginx/default.conf.template`): límite por IP real de **5 envíos por segundo con una ráfaga de 20** (configurable con `RATE_LIMIT_RPS` y `RATE_LIMIT_BURST`), respuesta `429` JSON con `Retry-After`, y el formulario muestra un aviso con reintento. La IP real se toma de `CF-Connecting-IP` solo cuando la petición llega desde una red privada (el contenedor de Caddy), para no limitar a todos los usuarios como si fueran uno.
- **Verificado en local** (grupo G13 y sección 4.2), simulando `CF-Connecting-IP`.
- **Pendiente en producción:** confirmar que Caddy reenvía ese encabezado y que nginx registra la IP real del cliente; si no, todos los usuarios compartirían un mismo cupo.

### F-05 · Baja · Con n8n caído no había reintento — **Corregido**

- **Corrección** (`web/app.js`): cualquier `5xx` y el `429` se tratan como reintentables, con título propio («El servicio no está disponible», «El servicio no respondió a tiempo») y el botón de reintento. Verificado en 4.2.

### F-06 · Baja · El encabezado `Server` revelaba la versión de nginx — **Corregido**

- `server_tokens off;` en la configuración de nginx. Verificado (`Server: nginx`).

### F-07 · Baja · Accesibilidad: contraste — **Corregido**

- **Corrección** (`web/styles.css`): nuevo color `--field-border` para los controles (3,6:1 a 4,0:1 según modo y fondo) y el texto de ejemplo sin transparencia (5,9:1 claro, 8,7:1 oscuro). El texto de lectura ya cumplía 4,5:1 (24 de 24 pares).
- **Limitación:** el contraste se calculó desde los valores del CSS; no se pudo alternar el esquema de color del navegador para comprobarlo visualmente.

### F-13 · Media · El script de importación falla en una instalación nueva — **Corregido**

- **Qué pasaba** (apareció al reconstruir el entorno de la segunda ronda): `scripts/n8n-import.sh` ejecutaba el CLI de n8n mientras el servidor aún corría sus migraciones iniciales sobre la base vacía. Ambos procesos migraban a la vez y el CLI fallaba con «duplicate key value violates unique constraint». La primera ronda no lo mostró porque había una espera previa.
- **Corrección:** el script espera ahora a que n8n responda su sonda de disponibilidad antes de importar. Verificado reconstruyendo el stack desde cero.
- **Importancia:** afecta directamente a la reproducción desde cero (T10) y a quien despliegue por primera vez.

### F-08 · Informativo · Capacidad — aceptado

- Secuencial: p50=103 ms p95=137 ms max=188 ms.
- 150 envíos con 50 en paralelo: estados=[201] total=20.9s (7.2 req/s) p50=7086 ms p95=7393 ms max=7496 ms.
- Suficiente para la demostración. Con el límite de tasa por IP, un solo cliente no puede saturar el servicio.

### F-09 · Informativo · Huecos en la numeración — aceptado

- 4 hueco(s) acumulado(s). Se producen cuando varios intentos simultáneos con el mismo UUID pierden la carrera del `INSERT` y consumen un valor de la secuencia. Es cosmético y no afecta la unicidad; una numeración sin huecos exigiría serializar los altas y no compensa.

### F-10 · Informativo · Comportamientos que el enunciado no define — aceptado y documentado

Se **aceptan** (`201`): distrito, categoría y sector en minúsculas o con espacios (se normalizan); UUID en mayúsculas (se normaliza y se deduplica con el original), UUID nil y UUID versión 1; campos desconocidos (se ignoran); `bolsas` como `5.0` o `1e1` (JSON numérico entero); cualquier `Content-Type` y el parámetro de consulta. Se **rechazan** desde esta ronda: caracteres de control (salvo salto de línea y tabulador en la descripción). Si se quiere un contrato más estricto, hay que decidirlo explícitamente.

### F-11 · Informativo · La función SQL no valida por sí misma — aceptado

- `registrar_reporte()` confía en que n8n valida el formato. Llamada directo con datos inconsistentes, las restricciones `CHECK` la rechazan (verificado), así que la integridad está protegida. Tras F-02, ese rechazo de la base llega al usuario como `400` y no como `503`.

### F-12 · Informativo · Hallazgos de entorno — documentado

- En la máquina de desarrollo había un stack ajeno, `mira-audit-isolated`, ocupando los puertos 28080 y 25678. No se tocó; se usaron otros puertos.
- Con n8n 1.123.27, `POST /rest/owner/setup` respondió `404` en un stack limpio, pero la importación por CLI funcionó sin propietario. En producción el propietario se creó desde la interfaz por un túnel SSH. Documentado en el README.
- La red `mira-proxy` tenía nombre fijo, lo que impedía correr dos stacks en un mismo equipo. Se parametrizó con `PROXY_NETWORK` (por defecto, el mismo nombre).

## 6. Errores de la propia suite y del arnés que se corrigieron

Por transparencia, estos fallos eran **de las pruebas**, no del producto:

1. Un normalizador asumía que el `request_id` siempre era texto (un caso envía un número).
2. La verificación de `DROP TABLE` esperaba «permission denied», pero PostgreSQL responde «must be owner» (el rol **sí** queda bloqueado).
3. Una invariante de conciliación estaba mal planteada: las ejecuciones sin fila de bitácora deben ser exactamente los intentos hechos con la base caída más el caso de bitácora rota, no los `503`.
4. Cuatro falsos fallos del arnés de la interfaz en la segunda ronda (sección 4.2).

## 7. Qué no se probó

- La ruta real Cloudflare → túnel → Caddy bajo carga, y límites de Cloudflare. **Las correcciones de esta ronda no están desplegadas en producción.**
- Otros navegadores (Firefox, Safari), dispositivos móviles reales y lectores de pantalla. El diseño móvil se verificó con un iframe de 371 px.
- El modo claro del navegador de forma visual (solo el cálculo de contraste).
- Pruebas de larga duración; el respaldo y la restauración de la base (T10).
- El tablero de Grafana (T9 no está construido); las consultas de los paneles se probaron como SQL.
- Las pruebas de interfaz se ejecutaron con un arnés dentro de la página que **no está versionado** en el repositorio.

## 8. Cómo reproducir

```sh
# 1. Stack aislado desde un clon de la revisión a probar (puertos y red propios)
git clone <repo> t9 && cd t9
cp .env.example .env   # completar con valores aleatorios y añadir:
#   PROXY_NETWORK=mira-t9-proxy  WEB_PORT=38080  N8N_EDITOR_PORT=35678
#   RATE_LIMIT_RPS=1000 RATE_LIMIT_BURST=1000     (límite relajado para la suite general)
docker compose -p mira-t9 up -d --wait postgres n8n web
set -a; . ./.env; set +a; COMPOSE="docker compose -p mira-t9" sh scripts/n8n-import.sh </dev/null

# 2. Suite (solo en entornos aislados: G10, G11 y G14 deshabilitan roles, bloquean tablas o crean restricciones)
WEBHOOK_URL=http://127.0.0.1:38080/webhook/reportes \
DB_EXEC="docker compose -p mira-t9 exec -T" PGUSER=mira_admin MIRA_APP_PASSWORD=... \
RESULTS=resultados.json python tests/http/suite.py

# 3. Límite de tasa: recrear el servicio web con los valores por defecto (sin RATE_LIMIT_*) y ejecutar solo ese grupo
ONLY=G13 RATE_TEST=1 ... python tests/http/suite.py
```

`ONLY=G1,G6` ejecuta solo algunos grupos (la conciliación G9 solo se ejecuta tras una corrida completa). La salida lista cada FAIL con lo esperado y lo observado.

## Apéndice A · Todos los casos de la suite (corrida final)

| ID | Estado | Caso | Esperado | Observado |
|---|---|---|---|---|
| `G1-prioridad-001` | PASS | ACUMULACION bolsas=1 obstruccion=False | HTTP 201; NORMAL/LIMPIEZA_PUBLICA/24h REGISTRADO dup=False | HTTP 201 MIR-000001 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G1-prioridad-002` | PASS | ACUMULACION bolsas=4 obstruccion=False | HTTP 201; NORMAL/LIMPIEZA_PUBLICA/24h REGISTRADO dup=False | HTTP 201 MIR-000002 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G1-prioridad-003` | PASS | ACUMULACION bolsas=5 obstruccion=False | HTTP 201; ALTA/LIMPIEZA_PUBLICA/12h REGISTRADO dup=False | HTTP 201 MIR-000003 ALTA/LIMPIEZA_PUBLICA/12h dup=False |
| `G1-prioridad-004` | PASS | ACUMULACION bolsas=6 obstruccion=False | HTTP 201; ALTA/LIMPIEZA_PUBLICA/12h REGISTRADO dup=False | HTTP 201 MIR-000004 ALTA/LIMPIEZA_PUBLICA/12h dup=False |
| `G1-prioridad-005` | PASS | ACUMULACION bolsas=50 obstruccion=False | HTTP 201; ALTA/LIMPIEZA_PUBLICA/12h REGISTRADO dup=False | HTTP 201 MIR-000005 ALTA/LIMPIEZA_PUBLICA/12h dup=False |
| `G1-prioridad-006` | PASS | ACUMULACION bolsas=1 obstruccion=True | HTTP 201; URGENTE/COORDINACION_OPERATIVA/4h REGISTRADO dup=False | HTTP 201 MIR-000006 URGENTE/COORDINACION_OPERATIVA/4h dup=False |
| `G1-prioridad-007` | PASS | ACUMULACION bolsas=4 obstruccion=True | HTTP 201; URGENTE/COORDINACION_OPERATIVA/4h REGISTRADO dup=False | HTTP 201 MIR-000007 URGENTE/COORDINACION_OPERATIVA/4h dup=False |
| `G1-prioridad-008` | PASS | ACUMULACION bolsas=5 obstruccion=True | HTTP 201; URGENTE/COORDINACION_OPERATIVA/4h REGISTRADO dup=False | HTTP 201 MIR-000008 URGENTE/COORDINACION_OPERATIVA/4h dup=False |
| `G1-prioridad-009` | PASS | ACUMULACION bolsas=6 obstruccion=True | HTTP 201; URGENTE/COORDINACION_OPERATIVA/4h REGISTRADO dup=False | HTTP 201 MIR-000009 URGENTE/COORDINACION_OPERATIVA/4h dup=False |
| `G1-prioridad-010` | PASS | ACUMULACION bolsas=50 obstruccion=True | HTTP 201; URGENTE/COORDINACION_OPERATIVA/4h REGISTRADO dup=False | HTTP 201 MIR-000010 URGENTE/COORDINACION_OPERATIVA/4h dup=False |
| `G1-prioridad-011` | PASS | VOLUMINOSO obstruccion=False | HTTP 201; PROGRAMADA/RECOJO_ESPECIAL/48h REGISTRADO dup=False | HTTP 201 MIR-000011 PROGRAMADA/RECOJO_ESPECIAL/48h dup=False |
| `G1-prioridad-012` | PASS | VOLUMINOSO obstruccion=True | HTTP 201; URGENTE/COORDINACION_OPERATIVA/4h REGISTRADO dup=False | HTTP 201 MIR-000012 URGENTE/COORDINACION_OPERATIVA/4h dup=False |
| `G1-prioridad-013` | PASS | OMISION_RECOJO obstruccion=False | HTTP 201; NORMAL/LIMPIEZA_PUBLICA/24h REGISTRADO dup=False | HTTP 201 MIR-000013 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G1-prioridad-014` | PASS | OMISION_RECOJO obstruccion=True | HTTP 201; URGENTE/COORDINACION_OPERATIVA/4h REGISTRADO dup=False | HTTP 201 MIR-000014 URGENTE/COORDINACION_OPERATIVA/4h dup=False |
| `G1-prioridad-015` | PASS | sector M01 habilitado | HTTP 201 | HTTP 201 MIR-000015 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G1-prioridad-016` | PASS | sector M02 habilitado | HTTP 201 | HTTP 201 MIR-000016 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G1-prioridad-017` | PASS | fecha_limite = registro + plazo (campo iso presente) | HTTP 201; fecha_limite_iso con -05:00 (Lima) | HTTP 201 MIR-000017 PROGRAMADA/RECOJO_ESPECIAL/48h dup=False |
| `G2-normalizacion-001` | PASS | distrito en minusculas | HTTP 201 | HTTP 201 MIR-000018 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-002` | PASS | categoria en minusculas | HTTP 201 | HTTP 201 MIR-000019 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-003` | PASS | sector en minusculas | HTTP 201 | HTTP 201 MIR-000020 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-004` | PASS | sector con espacios | HTTP 201 | HTTP 201 MIR-000021 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-005` | PASS | referencia/descripcion con espacios externos | HTTP 201 | HTTP 201 MIR-000022 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-006` | PASS | UUID en MAYUSCULAS | HTTP 201 | HTTP 201 MIR-000023 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-007` | PASS | UUID con espacios externos | HTTP 201 | HTTP 201 MIR-000024 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-008` | PASS | UUID nil (todo ceros) | HTTP 201/200/400/409 | HTTP 201 MIR-000025 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-009` | PASS | UUID version 1 | HTTP 201 | HTTP 201 MIR-000026 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-010` | PASS | campos desconocidos se ignoran | HTTP 201 | HTTP 201 MIR-000027 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-011` | PASS | descripcion con HTML/script | HTTP 201 | HTTP 201 MIR-000028 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-012` | PASS | descripcion con intento de inyeccion SQL | HTTP 201 | HTTP 201 MIR-000029 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-013` | PASS | referencia con comillas y backslash | HTTP 201 | HTTP 201 MIR-000030 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-014` | PASS | acentos y enie | HTTP 201 | HTTP 201 MIR-000031 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-015` | PASS | saltos de linea y tabuladores en descripcion | HTTP 201 | HTTP 201 MIR-000032 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-016` | PASS | descripcion de 200 caracteres exactos | HTTP 201 | HTTP 201 MIR-000033 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-017` | PASS | referencia de 120 caracteres exactos | HTTP 201 | HTTP 201 MIR-000034 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-018` | PASS | referencia de 5 caracteres exactos | HTTP 201 | HTTP 201 MIR-000035 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-019` | PASS | descripcion de 15 caracteres exactos | HTTP 201 | HTTP 201 MIR-000036 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G2-normalizacion-020` | PASS | bolsas 5.0 (JSON float entero) | HTTP 201 | HTTP 201 MIR-000037 ALTA/LIMPIEZA_PUBLICA/12h dup=False |
| `G2-normalizacion-021` | PASS | bolsas 1e1 (notacion cientifica) | HTTP 201 | HTTP 201 MIR-000038 ALTA/LIMPIEZA_PUBLICA/12h dup=False |
| `G2-normalizacion-022` | PASS | campos duplicados en el JSON (gana el ultimo) | HTTP 201 | HTTP 201 MIR-000039 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G3-validacion-001` | PASS | referencia de 4 caracteres | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-002` | PASS | referencia de 121 caracteres | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-003` | PASS | referencia solo espacios | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-004` | PASS | referencia que queda en 3 tras recortar | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-005` | PASS | referencia ausente | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-006` | PASS | referencia null | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-007` | PASS | referencia numerica | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-008` | PASS | descripcion de 14 caracteres | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-009` | PASS | descripcion de 201 caracteres | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-010` | PASS | descripcion solo espacios | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-011` | PASS | descripcion ausente | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-012` | PASS | descripcion arreglo | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-013` | PASS | obstruccion string 'true' | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-014` | PASS | obstruccion numero 1 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-015` | PASS | obstruccion null | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-016` | PASS | obstruccion ausente | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-017` | PASS | obstruccion 'si' | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-018` | PASS | distrito vacio | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-019` | PASS | distrito desconocido (LIMA) | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-020` | PASS | distrito null | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-021` | PASS | distrito numerico | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-022` | PASS | distrito ausente | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-023` | PASS | categoria vacia | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-024` | PASS | categoria desconocida | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-025` | PASS | categoria nombre antiguo OMISION | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-026` | PASS | categoria con tilde ACUMULACIÓN | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-027` | PASS | categoria ausente | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-028` | PASS | sector ausente en MIRAFLORES | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-029` | PASS | sector vacio en MIRAFLORES | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-030` | PASS | sector solo espacios en MIRAFLORES | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-031` | PASS | sector numerico en MIRAFLORES | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-032` | PASS | ACUMULACION bolsas=0 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-033` | PASS | ACUMULACION bolsas=-1 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-034` | PASS | ACUMULACION bolsas=51 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-035` | PASS | ACUMULACION bolsas=100 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-036` | PASS | ACUMULACION bolsas=5.5 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-037` | PASS | ACUMULACION bolsas='5' | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-038` | PASS | ACUMULACION bolsas='' | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-039` | PASS | ACUMULACION bolsas=None | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-040` | PASS | ACUMULACION bolsas=True | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-041` | PASS | ACUMULACION bolsas=[5] | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-042` | PASS | ACUMULACION bolsas=9007199254740992 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-043` | PASS | ACUMULACION sin bolsas | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-044` | PASS | OMISION_RECOJO con bolsas=3 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-045` | PASS | VOLUMINOSO con bolsas=0 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-046` | PASS | VOLUMINOSO con bolsas=1 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-047` | PASS | OMISION_RECOJO con bolsas null (permitido) | HTTP 201 | HTTP 201 MIR-000040 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G3-validacion-048` | PASS | OMISION_RECOJO sin bolsas (permitido) | HTTP 201 | HTTP 201 MIR-000041 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G3-validacion-049` | PASS | multiples errores: detalle lista todos | HTTP 400; codigo=DATOS_INVALIDOS; detalle con >=4 errores | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-050` | PASS | referencia de 3 emojis (3 caracteres, <5): debe ser 400 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-051` | PASS | referencia de 61 emojis (61 caracteres, <=120): debe ser 201 | HTTP 201 | HTTP 201 MIR-000042 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G3-validacion-052` | PASS | descripcion de 8 emojis (8 caracteres, <15): debe ser 400 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-053` | PASS | descripcion de 101 emojis (101 caracteres, <=200): debe ser 201 | HTTP 201 | HTTP 201 MIR-000043 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G3-validacion-054` | PASS | descripcion con caracter NUL (\u0000) | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-055` | PASS | referencia con caracter NUL | HTTP 400 | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-056` | PASS | descripcion con sustituto suelto (\ud800) | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-057` | PASS | referencia con salto de linea | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-058` | PASS | referencia con caracter de control \u0001 | HTTP 400 | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-059` | PASS | descripcion con caracter de control \u0001 | HTTP 400 | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-060` | PASS | descripcion con \u007f (DEL) | HTTP 400 | HTTP 400 DATOS_INVALIDOS |
| `G3-validacion-061` | PASS | descripcion con salto de linea y tabulador (permitidos) | HTTP 201 | HTTP 201 MIR-000044 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G4-jurisdiccion-001` | PASS | SURQUILLO valido sin sector | HTTP 422; codigo=FUERA_DE_JURISDICCION | HTTP 422 FUERA_DE_JURISDICCION |
| `G4-jurisdiccion-002` | PASS | OTRO valido sin sector | HTTP 422; codigo=FUERA_DE_JURISDICCION | HTTP 422 FUERA_DE_JURISDICCION |
| `G4-jurisdiccion-003` | PASS | SURQUILLO con sector M01 (se ignora el sector) | HTTP 422; codigo=FUERA_DE_JURISDICCION | HTTP 422 FUERA_DE_JURISDICCION |
| `G4-jurisdiccion-004` | PASS | SURQUILLO con sector M03 inactivo: gana jurisdiccion | HTTP 422; codigo=FUERA_DE_JURISDICCION | HTTP 422 FUERA_DE_JURISDICCION |
| `G4-jurisdiccion-005` | PASS | OTRO con sector inexistente: gana jurisdiccion | HTTP 422; codigo=FUERA_DE_JURISDICCION | HTTP 422 FUERA_DE_JURISDICCION |
| `G4-jurisdiccion-006` | PASS | orden: SURQUILLO + datos invalidos -> 400 antes que 422 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G4-jurisdiccion-007` | PASS | orden: OTRO + bolsas en OMISION -> 400 | HTTP 400 | HTTP 400 DATOS_INVALIDOS |
| `G4-jurisdiccion-008` | PASS | MIRAFLORES + sector M03 inactivo | HTTP 422; codigo=SECTOR_NO_HABILITADO | HTTP 422 SECTOR_NO_HABILITADO |
| `G4-jurisdiccion-009` | PASS | MIRAFLORES + sector inexistente M99 | HTTP 422; codigo=SECTOR_NO_HABILITADO | HTTP 422 SECTOR_NO_HABILITADO |
| `G4-jurisdiccion-010` | PASS | MIRAFLORES + sector 'ZZZ' | HTTP 422; codigo=SECTOR_NO_HABILITADO | HTTP 422 SECTOR_NO_HABILITADO |
| `G4-jurisdiccion-011` | PASS | MIRAFLORES + sector 'M01; DROP' | HTTP 422; codigo=SECTOR_NO_HABILITADO | HTTP 422 SECTOR_NO_HABILITADO |
| `G4-jurisdiccion-012` | PASS | 422 sector inactivo en OMISION_RECOJO sin obstruccion (P07) | HTTP 422; codigo=SECTOR_NO_HABILITADO | HTTP 422 SECTOR_NO_HABILITADO |
| `G5-cuerpo-001` | PASS | request_id ausente | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-002` | PASS | request_id null | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-003` | PASS | request_id vacio | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-004` | PASS | request_id 'abc' | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-005` | PASS | request_id sin guiones (32 hex) | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-006` | PASS | request_id entre llaves | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-007` | PASS | request_id numerico | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-008` | PASS | request_id con caracter no hex | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-009` | PASS | request_id 37 caracteres | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-010` | PASS | cuerpo vacio | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-011` | PASS | arreglo [] | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-012` | PASS | objeto {} | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-013` | PASS | null | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-014` | PASS | string | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-015` | PASS | numero | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-016` | PASS | booleano | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-017` | PASS | JSON roto {bad | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-018` | PASS | JSON truncado | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-019` | PASS | BOM + JSON valido | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-020` | PASS | bytes no UTF-8 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-021` | PASS | anidamiento profundo [[[...]]] | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G5-cuerpo-022` | PASS | JSON valido con Content-Type text/plain | HTTP 201 | HTTP 201 MIR-000045 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G5-cuerpo-023` | PASS | JSON valido con Content-Type application/json; charset=utf-8 | HTTP 201 | HTTP 201 MIR-000046 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G5-cuerpo-024` | PASS | JSON valido con Content-Type application/x-www-form-urlencoded | HTTP 201 | HTTP 201 MIR-000047 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G5-cuerpo-025` | PASS | JSON valido con Content-Type application/xml | HTTP 201 | HTTP 201 MIR-000048 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G5-cuerpo-026` | PASS | JSON valido con Content-Type None | HTTP 201 | HTTP 201 MIR-000049 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G5-cuerpo-027` | PASS | cuerpo ~15 KB valido (campo extra grande) | HTTP 201 | HTTP 201 MIR-000050 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G5-cuerpo-028` | PASS | cuerpo ~17 KB (supera el limite de 16 KB) | HTTP 413 | HTTP 413 <html>  <head><title>413 Request Entity Too Large</title></head>  <body>  <cente |
| `G5-cuerpo-029` | PASS | query string se ignora | HTTP 201 | HTTP 201 MIR-000051 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G6-idempotencia-001` | PASS | alta inicial | HTTP 201 | HTTP 201 MIR-000052 ALTA/LIMPIEZA_PUBLICA/12h dup=False |
| `G6-idempotencia-002` | PASS | reenvio identico -> 200 duplicado | HTTP 200; duplicado=true con mismo codigo y fecha limite | HTTP 200 MIR-000052 ALTA/LIMPIEZA_PUBLICA/12h dup=True |
| `G6-idempotencia-003` | PASS | reenvio con espacios/mayusculas distintos (normalizados iguales) -> 200 | HTTP 200; duplicado=true con mismo codigo y fecha limite | HTTP 200 MIR-000052 ALTA/LIMPIEZA_PUBLICA/12h dup=True |
| `G6-idempotencia-004` | PASS | reenvio con UUID en MAYUSCULAS -> 200 | HTTP 200; duplicado=true con mismo codigo y fecha limite | HTTP 200 MIR-000052 ALTA/LIMPIEZA_PUBLICA/12h dup=True |
| `G6-idempotencia-005` | PASS | mismo UUID, cambia bolsas 6 -> 409 | HTTP 409; codigo=IDENTIFICADOR_EN_CONFLICTO | HTTP 409 IDENTIFICADOR_EN_CONFLICTO |
| `G6-idempotencia-006` | PASS | mismo UUID, cambia sector M02 -> 409 | HTTP 409; codigo=IDENTIFICADOR_EN_CONFLICTO | HTTP 409 IDENTIFICADOR_EN_CONFLICTO |
| `G6-idempotencia-007` | PASS | mismo UUID, cambia categoria VOLUMINOSO -> 409 | HTTP 409; codigo=IDENTIFICADOR_EN_CONFLICTO | HTTP 409 IDENTIFICADOR_EN_CONFLICTO |
| `G6-idempotencia-008` | PASS | mismo UUID, cambia referencia distinta -> 409 | HTTP 409; codigo=IDENTIFICADOR_EN_CONFLICTO | HTTP 409 IDENTIFICADOR_EN_CONFLICTO |
| `G6-idempotencia-009` | PASS | mismo UUID, cambia descripcion distinta -> 409 | HTTP 409; codigo=IDENTIFICADOR_EN_CONFLICTO | HTTP 409 IDENTIFICADOR_EN_CONFLICTO |
| `G6-idempotencia-010` | PASS | mismo UUID, cambia obstruccion true -> 409 | HTTP 409; codigo=IDENTIFICADOR_EN_CONFLICTO | HTTP 409 IDENTIFICADOR_EN_CONFLICTO |
| `G6-idempotencia-011` | PASS | mismo UUID con distrito SURQUILLO -> 422 (jurisdiccion antes que UUID) | HTTP 422; codigo=FUERA_DE_JURISDICCION | HTTP 422 FUERA_DE_JURISDICCION |
| `G6-idempotencia-012` | PASS | mismo UUID con datos invalidos -> 400 (formato antes que UUID) | HTTP 400 | HTTP 400 DATOS_INVALIDOS |
| `G6-idempotencia-013` | PASS | mismo UUID con sector M03 -> 422 (catalogo antes que UUID) | HTTP 422; codigo=SECTOR_NO_HABILITADO | HTTP 422 SECTOR_NO_HABILITADO |
| `G6-idempotencia-014` | PASS | tras 409/422/400 la fila original sigue intacta | HTTP 200; fila original intacta (5\|ALTA\|12\|MIR-000052) | HTTP 200 MIR-000052 ALTA/LIMPIEZA_PUBLICA/12h dup=True |
| `G6-idempotencia-cnt` | PASS | una sola fila para el UUID tras todos los intentos | 1 fila | 1 fila(s) |
| `G6-idempotencia-015` | PASS | UUID existente tras deshabilitar su sector -> 422 | HTTP 422; codigo=SECTOR_NO_HABILITADO | HTTP 422 SECTOR_NO_HABILITADO |
| `G6-idempotencia-016` | PASS | tras reactivar el sector, el UUID vuelve a resolverse -> 200 | HTTP 200; duplicado=true con mismo codigo y fecha limite | HTTP 200 MIR-000052 ALTA/LIMPIEZA_PUBLICA/12h dup=True |
| `G7-concurrencia-001` | PASS | 20 envios simultaneos, mismo UUID y datos | 1x201, 19x200, 1 fila, 1 codigo | 1x201 19x200 otros=[] filas=1 codigos=1 |
| `G7-concurrencia-002` | PASS | 20 envios simultaneos, mismo UUID con 2 contenidos distintos (5 y 6 bolsas) | 1 fila, un solo 201, el resto 200 (mismo contenido que el ganador) o 409 (distinto) | filas=1 ganador=6 bolsas, 201x1, coherente=True |
| `G7-concurrencia-003` | PASS | 40 envios simultaneos con UUID distintos | 40x201, 40 filas, 40 codigos unicos | estados=[201] filas=40 codigos_unicos=40 |
| `G8-transporte-001` | PASS | metodo GET en el webhook | HTTP 403/405 | HTTP 403 <html>  <head><title>403 Forbidden</title></head>  <body>  <center><h1>403 Forbi |
| `G8-transporte-002` | PASS | metodo HEAD en el webhook | HTTP 403/405 | HTTP 403  |
| `G8-transporte-003` | PASS | metodo PUT en el webhook | HTTP 403/405 | HTTP 403 <html>  <head><title>403 Forbidden</title></head>  <body>  <center><h1>403 Forbi |
| `G8-transporte-004` | PASS | metodo PATCH en el webhook | HTTP 403/405 | HTTP 403 <html>  <head><title>403 Forbidden</title></head>  <body>  <center><h1>403 Forbi |
| `G8-transporte-005` | PASS | metodo DELETE en el webhook | HTTP 403/405 | HTTP 403 <html>  <head><title>403 Forbidden</title></head>  <body>  <center><h1>403 Forbi |
| `G8-transporte-006` | PASS | metodo OPTIONS en el webhook | HTTP 403/405 | HTTP 403 <html>  <head><title>403 Forbidden</title></head>  <body>  <center><h1>403 Forbi |
| `G8-transporte-007` | PASS | metodo TRACE en el webhook | HTTP 403/405 | HTTP 405 <html>  <head><title>405 Not Allowed</title></head>  <body>  <center><h1>405 Not |
| `G8-transporte-008` | PASS | GET /webhook/reportes/ | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-009` | PASS | GET /webhook/Reportes | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-010` | PASS | GET /webhook/otro | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-011` | PASS | GET /webhook-test/reportes | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-012` | PASS | GET /webhook | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-013` | PASS | GET /rest/settings | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-014` | PASS | GET /rest/login | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-015` | PASS | GET /signin | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-016` | PASS | GET /healthz | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-017` | PASS | GET /metrics | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-018` | PASS | GET /.env | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-019` | PASS | GET /.git/config | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-020` | PASS | GET /nginx/default.conf | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-021` | PASS | GET /default.conf | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-022` | PASS | GET /docker-compose.yml | HTTP 404 | HTTP 404 <html>  <head><title>404 Not Found</title></head>  <body>  <center><h1>404 Not F |
| `G8-transporte-023` | PASS | GET /..%2f..%2fetc/passwd | HTTP 400/404 | HTTP 400 <html>  <head><title>400 Bad Request</title></head>  <body>  <center><h1>400 Bad |
| `G8-transporte-024` | PASS | GET /%2e%2e/%2e%2e/etc/passwd | HTTP 400/404 | HTTP 400 <html>  <head><title>400 Bad Request</title></head>  <body>  <center><h1>400 Bad |
| `G8-transporte-025` | PASS | GET /index.html | HTTP 200 | HTTP 200 <!doctype html> <html lang="es"> <head>   <meta charset="utf-8">   <meta name="v |
| `G8-transporte-026` | PASS | GET /styles.css?v=2 | HTTP 200 | HTTP 200 :root {   --bg: #f3f6f5;   --card: #ffffff;   --text: #17211f;   --muted: #53625 |
| `G8-transporte-027` | PASS | GET /app.js?v=2 | HTTP 200 | HTTP 200 (() => {   'use strict';    const ENDPOINT = '/webhook/reportes';   const TIMEOU |
| `G8-transporte-028` | PASS | GET / | HTTP 200 | HTTP 200 <!doctype html> <html lang="es"> <head>   <meta charset="utf-8">   <meta name="v |
| `G8-transporte-h-content-security-policy` | PASS | encabezado content-security-policy en / | content-security-policy contiene default-src 'self' | default-src 'self'; frame-ancestors 'none' |
| `G8-transporte-h-x-content-type-options` | PASS | encabezado x-content-type-options en / | x-content-type-options contiene nosniff | nosniff |
| `G8-transporte-h-referrer-policy` | PASS | encabezado referrer-policy en / | referrer-policy contiene no-referrer | no-referrer |
| `G8-transporte-h-cache-control` | PASS | encabezado cache-control en / | cache-control contiene no-cache | no-cache |
| `G8-transporte-h-server` | PASS | el encabezado Server no revela la version de nginx | Server sin version | nginx |
| `G8-transporte-h2-content-security-policy` | PASS | encabezado content-security-policy tambien en la respuesta del webhook | content-security-policy | default-src 'self'; frame-ancestors 'none' |
| `G8-transporte-h2-x-content-type-options` | PASS | encabezado x-content-type-options tambien en la respuesta del webhook | x-content-type-options | nosniff |
| `G8-transporte-cors` | PASS | preflight CORS de otro origen no concede acceso | sin Access-Control-Allow-Origin | 403 - |
| `G8-transporte-origen` | PASS | cabecera X-Origen: distingue prueba/demo (3 variantes responden 201) | 201 x3 | 201,201,201 |
| `G11-permisos-bd-01` | PASS | mira_app: SELECT en reportes | permission denied | ERROR:  permission denied for table reportes |
| `G11-permisos-bd-02` | PASS | mira_app: SELECT en bitacora_intentos | permission denied | ERROR:  permission denied for table bitacora_intentos |
| `G11-permisos-bd-03` | PASS | mira_app: INSERT directo en reportes | permission denied | ERROR:  permission denied for table reportes |
| `G11-permisos-bd-04` | PASS | mira_app: UPDATE en sectores | permission denied | ERROR:  permission denied for table sectores |
| `G11-permisos-bd-05` | PASS | mira_app: DELETE en bitacora_intentos | permission denied | ERROR:  permission denied for table bitacora_intentos |
| `G11-permisos-bd-06` | PASS | mira_app: TRUNCATE reportes | permission denied | ERROR:  permission denied for table reportes |
| `G11-permisos-bd-07` | PASS | mira_app: DROP TABLE reportes | permission denied | ERROR:  must be owner of table reportes |
| `G11-permisos-bd-08` | PASS | mira_app: CREATE TABLE | permission denied | ERROR:  permission denied for schema public |
| `G11-permisos-bd-09` | PASS | mira_app: SELECT en sectores (permitido) | permitido | permitido |
| `G11-permisos-bd-10` | PASS | mira_app: INSERT en bitacora (permitido) | permitido | permitido |
| `G11-permisos-bd-11` | PASS | mira_app: EXECUTE registrar_reporte (permitido) | permitido | permitido |
| `G11-permisos-bd-fn1` | PASS | funcion llamada directo con bolsas en una categoria que no es ACUMULACION | rechazada por la restriccion de la tabla | ERROR:  new row for relation "reportes" violates check constraint "reportes_bolsas_check" |
| `G11-permisos-bd-fn2` | PASS | funcion llamada directo con UUID nulo | error | ERROR:  null value in column "request_id" of relation "reportes" violates not-null constraint |
| `G11-permisos-bd-fn3` | PASS | funcion llamada directo con categoria inexistente | rechazada por CHECK | ERROR:  new row for relation "reportes" violates check constraint "reportes_categoria_check" |
| `G14-errores-de-datos-en-la-bd-001` | PASS | la base rechaza un valor (CHECK temporal): 400 y no 503 | HTTP 400; codigo=DATOS_INVALIDOS | HTTP 400 DATOS_INVALIDOS |
| `G14-errores-de-datos-en-la-bd-002` | PASS | sin la restriccion temporal el mismo valor se acepta | HTTP 201 | HTTP 201 MIR-000104 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G10-fallos-001` | PASS | preparacion: reporte existente | HTTP 201 | HTTP 201 MIR-000105 ALTA/LIMPIEZA_PUBLICA/12h dup=False |
| `G10-fallos-002` | PASS | P11a: BD caida, reporte nuevo -> 503 | HTTP 503; codigo=ERROR_PERSISTENCIA | HTTP 503 ERROR_PERSISTENCIA |
| `G10-fallos-003` | PASS | BD caida, UUID existente -> 503 (no se puede confirmar) | HTTP 503; codigo=ERROR_PERSISTENCIA | HTTP 503 ERROR_PERSISTENCIA |
| `G10-fallos-004` | PASS | BD caida, datos invalidos -> 400 (no necesita BD) | HTTP 400 | HTTP 400 DATOS_INVALIDOS |
| `G10-fallos-005` | PASS | BD caida, SURQUILLO -> 422 (no necesita BD) | HTTP 422 | HTTP 422 FUERA_DE_JURISDICCION |
| `G10-fallos-006` | PASS | BD caida, UUID invalido -> 400 | HTTP 400 | HTTP 400 DATOS_INVALIDOS |
| `G10-fallos-007` | PASS | P11b: recuperada la BD, reintento con el mismo UUID -> 201 | HTTP 201 | HTTP 201 MIR-000106 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G10-fallos-008` | PASS | recuperada la BD, UUID existente -> 200 | HTTP 200 | HTTP 200 MIR-000105 ALTA/LIMPIEZA_PUBLICA/12h dup=True |
| `G10-fallos-cnt` | PASS | una sola fila tras 503 + reintento | 1 fila | 1 fila(s) |
| `G10-fallos-009` | PASS | permiso EXECUTE revocado -> 503 | HTTP 503 | HTTP 503 ERROR_PERSISTENCIA |
| `G10-fallos-010` | PASS | INSERT en bitacora revocado: la respuesta sigue siendo 201 | HTTP 201 | HTTP 201 MIR-000107 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G10-fallos-bit` | PASS | con la bitacora rota el reporte se guarda y no hay fila de bitacora | 0 filas de bitacora | 0 |
| `G10-fallos-slow1` | PASS | BD lenta (bloqueo 9 s), el cliente abandona a los 4 s | timeout del cliente (status 0) | status=0 en 4005 ms |
| `G10-fallos-slow2` | PASS | aunque el cliente abandonó, el servidor guardó el reporte | 1 fila | 1 fila(s) |
| `G10-fallos-011` | PASS | el reintento del mismo UUID devuelve 200 duplicado (no crea otro) | HTTP 200; duplicado=true | HTTP 200 MIR-000108 NORMAL/LIMPIEZA_PUBLICA/24h dup=True |
| `G10-fallos-012` | PASS | BD lenta (bloqueo 5 s): la respuesta llega con 201 tras esperar | HTTP 201; tarda >= 2.5 s (tardo 3761 ms) | HTTP 201 MIR-000109 NORMAL/LIMPIEZA_PUBLICA/24h dup=False |
| `G12-rendimiento-seq` | PASS | 100 envios secuenciales validos | p95 < 1500 ms | p50=103 ms p95=137 ms max=188 ms |
| `G12-rendimiento-par` | PASS | 150 envios con 50 en paralelo | todos 201 | estados=[201] total=20.9s (7.2 req/s) p50=7086 ms p95=7393 ms max=7496 ms |
| `G9-trazabilidad-01` | PASS | cada caso que debia crear fila la creo | 0 casos sin fila | 0 sin fila: [] |
| `G9-trazabilidad-02` | PASS | ningun rechazo (400/422/413) dejo fila | 0 filas indebidas | 0: [] |
| `G9-trazabilidad-03` | PASS | ningun UUID repetido en reportes | 0 duplicados | 0 (de 355 filas) |
| `G9-trazabilidad-04` | PASS | codigos publicos unicos | 0 repetidos | 0 |
| `G9-trazabilidad-05` | INFO | huecos en la numeracion de reportes | 0 (informativo) | 4 hueco(s) acumulado(s) |
| `G9-trazabilidad-06` | PASS | intentos con UUID invalido se registran con request_id nulo | >0 filas nulas | 23 |
| `G9-trazabilidad-07` | PASS | toda fila de bitacora trae ejecucion y HTTP | 0 (la fila de prueba de permisos no cuenta) | 1 |
| `G9-trazabilidad-08` | PASS | toda ejecucion de n8n tiene fila de bitacora, salvo los intentos con la BD caida o la bitacora rota | ejecuciones - bitacora = 6 (intentos que no podian registrarse) | ejecuciones=506 bitacora=500 sin_bitacora=6 (503 en n8n=3; los 503 con la BD arriba si quedan en bitacora) |
| `G9-trazabilidad-09` | PASS | el HTTP de la bitacora coincide con el HTTP guardado en la ejecucion de n8n | 0 diferencias | 0 diferencia(s) de 500 comparadas |
| `G9-trazabilidad-10` | PASS | consultas de los paneles (informativo) | - | reportes por prioridad: ALTA=9 NORMAL=337 PROGRAMADA=2 URGENTE=7 \| 5xx=3 de 506 intentos = 0.59% |
| `G13-limite-de-tasa-001` | PASS | rafaga de 80 envios validos de un mismo cliente: se atiende lo permitido y se rechaza el resto con 429 | mezcla de 201 y 429, sin otros codigos, filas = numero de 201 | 201x21 429x59 otros=[] filas=21 |
| `G13-limite-de-tasa-002` | PASS | la respuesta 429 es JSON legible y trae Retry-After | codigo=DEMASIADAS_SOLICITUDES + Retry-After | {'codigo': 'DEMASIADAS_SOLICITUDES', 'mensaje': 'Demasiados envíos seguidos. Espera unos segundos e inténtalo  |
| `G13-limite-de-tasa-003` | PASS | otro cliente (otra IP real) no se ve afectado mientras el primero esta limitado | 201 | 201 |
| `G13-limite-de-tasa-004` | PASS | pasados unos segundos el primer cliente vuelve a poder enviar | 201 | 201 |
| `G13-limite-de-tasa-005` | PASS | un ritmo normal (12 envios con 0,3 s de pausa) nunca se limita | 12 x 201 | [201] |

