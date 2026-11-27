# Plan de la práctica: reportes de limpieza pública de Miraflores

**Objetivo:** demostrar que un reporte válido se registra una sola vez, recibe la prioridad y el plazo correctos y puede rastrearse desde el formulario hasta la base. El alcance termina en la asignación inicial; no incluye la atención en campo. Usar datos sintéticos.

**Estado:** plan de trabajo individual, no evidencia de ejecución. Corresponde a la Parte B (12 puntos); la Parte A se entrega por separado. El enunciado menciona equipos, pero el usuario confirmó que realizará toda la evaluación individualmente. Fuente: `Examen_Final_Desarrollo_de_Operaciones_de_Software_UCH.docx`, apartados «Parte B», «Pruebas de aceptación» y «Entregables y rúbrica».

**Alcance de la demo:** entrega para el 29 de noviembre; el formulario se comparte por enlace para probarlo con datos sintéticos. Mostrar el aviso académico y solicitar que no se ingresen datos personales. Conocer el enlace no autentica a las personas: cualquiera que lo reciba podría reenviarlo. El uso con datos reales no forma parte de esta demo académica. Conservar los reportes de prueba hasta la evaluación para los informes de uso y las métricas; no programar su borrado periódico. Identificar y distinguir las pruebas automatizadas de los envíos de la demo al interpretar las métricas.

**Adaptación:** según la autorización docente comunicada por el usuario, Caddy sirve el formulario en lugar de Netlify y PostgreSQL propio reemplaza la persistencia en Supabase. El informe debe explicar la equivalencia y mostrar el despliegue real. n8n mantiene la orquestación. Se usará Grafana como tablero de la práctica, sin Prometheus; es una decisión del proyecto, no una exigencia de la rúbrica.

**Forma de trabajo:** avanzar por bloques y explicar cada proceso al terminarlo. Reutilizar la infraestructura existente cuando sea apropiado, sin afectar otros proyectos; demostrar la reproducción en un entorno limpio. El usuario configurará un repositorio privado en GitHub y se trabajará en `main`. El objetivo es automatizar las pruebas en el servidor, sin GitHub Actions, en un entorno aislado; después de comprobar el resultado para la revisión correspondiente, el despliegue desde el clon será manual. No se configurará despliegue automático. Definir y comprobar el aislamiento, la identidad de acceso al repositorio y la recuperación antes de implementar la automatización. Esta planificación no ejecuta ni habilita por sí sola el acceso remoto ni el despliegue. La Parte A se abordará después.

## Flujo de un reporte

1. El formulario genera un UUID por envío y lo conserva para reintentar. Envía un POST al webhook público.
2. n8n normaliza y valida los campos. Un formato inválido devuelve `400 DATOS_INVALIDOS`; un distrito válido distinto de Miraflores devuelve `422 FUERA_DE_JURISDICCION`. Para Miraflores, sector vacío es un error de formato.
3. PostgreSQL comprueba el catálogo antes de resolver el UUID. Un sector desconocido o inactivo devuelve `422 SECTOR_NO_HABILITADO`. Si el UUID ya existe, los mismos datos normalizados devuelven el original (`200`); datos distintos devuelven `409 IDENTIFICADOR_EN_CONFLICTO` sin sobrescribirlo.
4. Para un alta, se aplica la primera regla de la tabla, se guarda el estado `REGISTRADO` y se confirma con `201`. El plazo se calcula en horas corridas desde el registro; las fechas se muestran en hora de Lima.
5. n8n vincula el intento con su ejecución y devuelve una sola respuesta. En `200`/`201` incluye identificador público, estado, prioridad, cola, fecha límite y `duplicado`. Ante un fallo de persistencia devuelve `503 ERROR_PERSISTENCIA`, sin afirmar que se guardó. La interfaz muestra el resultado y permite reintentar el mismo envío.

| Primera condición aplicable | Prioridad | Cola | Plazo |
|---|---|---|---|
| Obstrucción | URGENTE | COORDINACION_OPERATIVA | 4 h |
| VOLUMINOSO | PROGRAMADA | RECOJO_ESPECIAL | 48 h |
| ACUMULACION con al menos 5 bolsas | ALTA | LIMPIEZA_PUBLICA | 12 h |
| Resto admitido | NORMAL | LIMPIEZA_PUBLICA | 24 h |

## Pipeline de cambios: del repositorio a la operación

| Etapa | Trabajo y condición para avanzar |
|---|---|
| Desarrollo | Versionar formulario, SQL, workflow exportado y configuración sin secretos. Anotar qué salida debe cambiar y cuál debe conservarse. |
| Integración | Automatizar en el servidor la validación de Compose y las pruebas SQL y HTTP en un entorno aislado con base de prueba limpia, catálogo y workflow importado. Registrar la revisión probada y el resultado; un HTTP correcto con una fila incorrecta también bloquea el cambio. El mecanismo y la frecuencia de ejecución quedan por definir. |
| Entrega | Preparar una versión identificable con archivos coherentes, instrucciones y evidencias. Estar lista para desplegar no significa que ya esté desplegada. |
| Despliegue | Tras comprobar las pruebas aprobadas, actualizar manualmente el clon y publicar únicamente el stack académico autorizado. Verificar desde el formulario público un alta sintética, su fila y la ejecución asociada. No simular una caída en el servidor compartido. |
| Operación | Revisar ambos paneles de Grafana para el mismo intervalo de prueba. Ante un error, localizar el intento en n8n, revisar la persistencia y verificar la recuperación antes de dar el incidente por resuelto. |

Estas etapas son el diseño acordado; todavía no existe automatización implementada. Un script ejecutado manualmente aporta evidencia, pero no demuestra por sí solo integración continua automática.

## Pendientes para resolver por bloques

La planificación funcional permite comenzar; los siguientes puntos requieren comprobación o diseño durante el trabajo:

1. **Inventario en lectura:** identificar Caddy, túnel y monitoreo existentes que puedan reutilizarse sin afectar otros proyectos; comprobar qué métricas de recursos ya están disponibles. No revisar ni copiar secretos.
2. **Pruebas automáticas:** definir el mecanismo y la frecuencia, la identidad de solo lectura para el repositorio privado y cómo registrar la revisión exacta y el resultado. Mantener las pruebas y su base aisladas de la demo.
3. **Despliegue y recuperación:** documentar el `pull` y despliegue manual después de verificar las pruebas de la misma revisión, así como el respaldo y la recuperación sin perder reportes.
4. **Grafana:** identificar una fuente verificable para el resumen de ejecuciones de n8n y añadir consumo de recursos solo si se puede aprovechar lo existente sin complejidad desproporcionada. El acceso de solo lectura del docente se configurará y comprobará durante T9; no se ha creado ninguna cuenta ni invitación.
5. **Actividad de la demo:** distinguir los envíos de visitantes de los automatizados al interpretar las métricas. La frecuencia y el mecanismo de pruebas sintéticas periódicas quedan pendientes; no presentar sus envíos como actividad humana.
6. **Entrega:** reservar tiempo antes del 29 de noviembre para comprobar reproducibilidad, evidencias, video y acceso a los enlaces. La Parte A se abordará por separado.

**Primer bloque previsto:** T0, inventario de infraestructura y fuentes de monitoreo en lectura. La inspección inicial de recursos no equivale al inventario completo. El acceso de escritura y el despliegue remoto requieren autorización específica por separado.

## Tareas, dependencias y criterios de cierre

### T0 — Preparación
Inventariar, en lectura y con acceso autorizado, CPU, memoria disponible, uso de swap, disco y carga de los servicios existentes. Identificar el recorrido del túnel sin copiar secretos. **Cierre:** registrar capacidad observada y límites de intervención; no tomar una estimación anterior como medición actual.

### T1 — Base reproducible del proyecto · apoya P6
Definir servicios `web`, `n8n` y `postgres`, red y volúmenes del proyecto y `.env.example` sin secretos. **Depende de:** T0 para las decisiones del servidor. **Cierre:** configuración Compose válida y documentada; no modificar otros proyectos.

### T2 — Persistencia e idempotencia · P3
Crear `sectores` (M01/M02 habilitados, M03 inactivo), `reportes` y `bitacora_intentos`. Aplicar FK, unicidad de `request_id`, comparación de campos de negocio normalizados y clasificación transaccional. **Depende de:** T1. **Cierre:** pruebas SQL de alta, duplicado y conflicto, incluidos intentos solapados: una sola fila, datos y plazo originales intactos.

### T3 — n8n y trazabilidad básica · apoya P2 y P3
Configurar webhook, hora de Lima, credencial PostgreSQL en n8n e historial de ejecuciones con HTTP observable tanto para éxitos como para errores controlados. **Depende de:** T1–T2. **Cierre:** editor privado, conexión verificada y ejecución de prueba localizable.

### T4 — Workflow y decisiones · P2
Implementar en el servidor el orden del flujo anterior. Validar UUID, distrito, sector condicional, categoría, referencia (5–120) y descripción (15–200) tras recorte, obstrucción booleana y bolsas (entero 1–50 solo en acumulación; ausente o nulo en el resto). Distinguir en n8n admisión, clasificación y error, sin duplicar la regla SQL. **Depende de:** T2–T3. **Cierre:** P01–P10 con respuesta única y efecto esperado.

### T5 — Bitácora y recuperación · P3 y P4
Registrar fecha, UUID cuando sea válido, HTTP, resultado, identificador de reporte si aplica e identificador de ejecución. Incluir altas, duplicados y rechazos mientras la base esté disponible. Un error de bitácora no debe ocultar la respuesta. **Depende de:** T3–T4. **Cierre:** P11 en entorno aislado, con fallo antes de guardar, ejecución del `503`, recuperación, reintento `201` con el mismo UUID y una sola fila.

### T6 — Formulario · P1
Desarrollar interfaz con aviso de prototipo académico, validaciones visibles, resultado legible y UUID estable por envío. Puede avanzar en paralelo con T4/T5 una vez acordado el contrato HTTP. **Cierre:** tras T7, un alta desde el navegador muestra el resultado y coincide con la fila persistida.

### T7 — Publicación del prototipo · P1
Servir el formulario y el webhook mediante Caddy y el túnel previsto, sin ruta pública al editor. Separar cualquier control de tráfico del comportamiento probado en la rúbrica. El `nginx` del servicio `web` es el único punto de entrada del stack: acepta solo `POST /webhook/reportes`, limita el cuerpo y lo reenvía como `text/plain`. Así n8n no responde con su propio `422` ante un JSON roto, y el workflow devuelve `400 DATOS_INVALIDOS`. El Caddy compartido solo hace `reverse_proxy` al alias `mira-web:80`. **Depende de:** T3, T4 y T6. **Cierre:** URL pública funcional, POST al webhook correcto y editor solo por acceso privado.

### T8 — Aceptación · P4
Ejecutar en práctica aislada y registrar por caso: **HTTP, resultado observado, efecto en la base y número o enlace de evidencia**. Usar UUID nuevos salvo donde se pide reintentar. **Depende de:** T4–T7. **Cierre:** once casos demostrados y al menos un alta desde el formulario publicado.

| Caso | Qué demuestra |
|---|---|
| P01/P02 | 4 frente a 5 bolsas sin obstrucción: `201` NORMAL/24 h frente a ALTA/12 h. Conservar P02 para P09/P10. |
| P03/P04 | Voluminoso con y sin obstrucción: `201` URGENTE/4 h frente a PROGRAMADA/48 h. |
| P05 | Omisión sin obstrucción: `201` NORMAL/24 h. Verificar también la cola en cada alta. |
| P06/P07 | Surquillo sin sector y Miraflores con M03 inactivo: `422`, motivos distintos, ninguna fila de reporte. Para P07 usar omisión sin obstrucción. |
| P08 | POST directo al webhook con 0 bolsas: `400`, ninguna fila; la prueba no debe quedar bloqueada en el navegador. |
| P09/P10 | Repetir P02 intacto: `200`, duplicado. Cambiar a 6 bolsas con el mismo UUID: `409`. No cambia la fila, el código ni el plazo de P02. |
| P11 | Omisión válida sin obstrucción: fallo antes de guardar → `503`; restaurar y repetir el mismo UUID → `201`, una fila final. |

### T9 — Tablero de Grafana y monitoreo operativo · P5
Usar un intervalo explícito común. Contar **nuevos reportes por prioridad** desde PostgreSQL; calcular **100 × intentos 5xx / intentos** desde las ejecuciones de n8n del workflow con HTTP registrado, incluido P11. Excluir pruebas ajenas; con cero intentos mostrar «Sin datos». **Depende de:** T5 y T8. **Cierre:** reconciliar ambos resultados con filas y ejecuciones identificables.

Alerta propuesta para la demostración, no política municipal: al menos un `5xx` en los últimos 15 minutos activa revisión por el responsable técnico. Primera acción: localizar la ejecución y verificar la conexión a PostgreSQL.

Incorporar Grafana al stack de la práctica en esta tarea, con acceso privado. Habilitar para el docente un acceso autenticado de solo visualización, sin permisos para modificar tableros, fuentes de datos ni configuración, y verificar efectivamente esas restricciones. Usar además una cuenta SQL independiente de solo lectura sobre las vistas del tablero:

- **Panel 1 — Reportes nuevos por prioridad:** consultar las filas persistidas. El reintento duplicado de P09 no debe aumentar el total.
- **Panel 2 — Tasa de errores técnicos:** después de recuperar la conexión, preparar un resumen de las ejecuciones de n8n del intervalo. Mostrar el periodo y la hora de actualización; es evidencia de la prueba, no una señal en vivo durante la caída. En P11 deben contarse ambos intentos (`503` y `201`), pero solo el primero aumenta el numerador.

**Verificación del tablero:** comprobar con la cuenta del docente que puede ver los paneles pero no modificarlos, guardar una captura con ambos paneles y contrastar los totales con sus fuentes. La inspección inicial del servidor mostró 4,6 GiB de memoria disponible y swap sin uso; repetir la medición con Grafana, n8n y PostgreSQL activos durante P01–P11. Si el tablero afecta al servidor compartido, conservar la consulta SQL y el historial de n8n como evidencia de contingencia.

### T10 — Respaldo y reproducción · apoya P3 y P6
Entregar SQL para crear y probar la base, el JSON revisado y las instrucciones de configuración. El dump es complementario. **Depende de:** T2–T5. **Cierre:** en entorno limpio, crear o restaurar la base, importar el workflow, configurar credenciales locales y demostrar un alta. Arrancar contenedores no demuestra restauración.

### T11 — Entregables y sustentación · P6
Preparar el Word individual con la plantilla, diagrama, reparto de reglas, esquema, pruebas, monitoreo y capturas numeradas de los componentes realmente usados. Reunir en Drive informe, fuente del formulario, JSON, SQL, instrucciones y video. Incluir URL pública. **Depende de:** T8–T10. **Cierre:** verificar lectura para el docente y que las evidencias no expongan secretos. En el video (5–8 minutos sugeridos), mostrar alta, prioridad por obstrucción, duplicado, rechazo o fallo y monitoreo; señalar fila o ejecución en cada caso.
