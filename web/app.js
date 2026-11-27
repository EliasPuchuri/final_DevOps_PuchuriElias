(() => {
  'use strict';

  const ENDPOINT = '/webhook/reportes';
  const TIMEOUT_MS = 15000;
  const ID_KEY = 'mira.requestId';
  const NOTICE_KEY = 'mira.avisoVisto';

  const $ = (id) => document.getElementById(id);
  const form = $('reporte');
  const resultado = $('resultado');
  const enviar = $('enviar');

  const fields = {
    distrito: $('distrito'),
    sector: $('sector'),
    categoria: $('categoria'),
    bolsas: $('bolsas'),
    referencia: $('referencia'),
    descripcion: $('descripcion'),
  };

  // ---- Session storage helpers: cleared by the browser when the tab is closed ----
  function readSession(key) {
    try { return sessionStorage.getItem(key); } catch (e) { return null; }
  }
  function writeSession(key, value) {
    try { sessionStorage.setItem(key, value); } catch (e) { /* storage unavailable */ }
  }

  // ---- Academic notice (modal shown once per browser session) ----
  function setupNotice() {
    const dialog = $('aviso');
    if (readSession(NOTICE_KEY) === '1') return;
    // Closing the notice in any way (button or Esc) counts as seen for this browser session.
    dialog.addEventListener('close', () => {
      writeSession(NOTICE_KEY, '1');
      fields.distrito.focus();
    });
    $('aviso-ok').addEventListener('click', () => dialog.close());
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
  }

  // ---- Request identifier: one per submission, reused on retry ----
  let requestId = loadRequestId();
  let lastPayload = null;

  function uuid() {
    if (window.crypto && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    const b = crypto.getRandomValues(new Uint8Array(16));
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
    return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
  }
  function loadRequestId() {
    const saved = readSession(ID_KEY);
    return saved || storeRequestId(uuid());
  }
  function storeRequestId(id) {
    writeSession(ID_KEY, id);
    return id;
  }
  function showRequestId() { $('request-id').textContent = requestId; }

  // ---- Validation (mirrors the server rules; the server remains the authority) ----
  const selectedObstruccion = () => {
    const r = form.querySelector('input[name="obstruccion"]:checked');
    return r ? r.value === 'true' : null;
  };

  function validate() {
    const errors = {};
    const distrito = fields.distrito.value;
    const categoria = fields.categoria.value;
    const referencia = fields.referencia.value.trim();
    const descripcion = fields.descripcion.value.trim();

    if (!distrito) errors.distrito = 'Elige un distrito.';
    if (distrito === 'MIRAFLORES' && !fields.sector.value) errors.sector = 'Elige un sector de Miraflores.';
    if (!categoria) errors.categoria = 'Elige el tipo de problema.';
    if (categoria === 'ACUMULACION') {
      const n = Number(fields.bolsas.value);
      if (fields.bolsas.value === '' || !Number.isInteger(n) || n < 1 || n > 50) {
        errors.bolsas = 'Escribe cuántas bolsas hay: un número entero de 1 a 50.';
      }
    }
    if (referencia.length < 5 || referencia.length > 120) {
      errors.referencia = 'La referencia debe tener entre 5 y 120 caracteres.';
    }
    if (descripcion.length < 15 || descripcion.length > 200) {
      errors.descripcion = 'La descripción debe tener entre 15 y 200 caracteres.';
    }
    if (selectedObstruccion() === null) errors.obstruccion = 'Indica si los residuos bloquean el paso.';
    return errors;
  }

  function paintErrors(errors) {
    ['distrito', 'sector', 'categoria', 'bolsas', 'referencia', 'descripcion', 'obstruccion'].forEach((name) => {
      const p = $(`err-${name}`);
      const control = fields[name];
      const msg = errors[name];
      p.hidden = !msg;
      p.textContent = msg || '';
      if (control) {
        control.classList.toggle('invalid', Boolean(msg));
        control.setAttribute('aria-invalid', msg ? 'true' : 'false');
      }
    });
    const first = Object.keys(errors)[0];
    if (first) (fields[first] || form.querySelector('input[name="obstruccion"]')).focus();
  }

  function buildPayload() {
    const payload = {
      request_id: requestId,
      distrito: fields.distrito.value,
      categoria: fields.categoria.value,
      referencia: fields.referencia.value.trim(),
      descripcion: fields.descripcion.value.trim(),
      obstruccion: selectedObstruccion(),
    };
    if (payload.distrito === 'MIRAFLORES') payload.sector = fields.sector.value;
    if (payload.categoria === 'ACUMULACION') payload.bolsas = Number(fields.bolsas.value);
    return payload;
  }

  // ---- Result rendering (textContent only: server text is never interpreted as HTML) ----
  const PRIORIDAD = { URGENTE: 'Urgente', ALTA: 'Alta', PROGRAMADA: 'Programada', NORMAL: 'Normal' };
  const COLA = {
    COORDINACION_OPERATIVA: 'Coordinación operativa',
    RECOJO_ESPECIAL: 'Recojo especial',
    LIMPIEZA_PUBLICA: 'Limpieza pública',
  };
  const ESTADO = { REGISTRADO: 'Registrado' };

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function showResult(kind, title, nodes) {
    resultado.className = `result ${kind}`;
    resultado.replaceChildren(el('h2', title), ...nodes);
    resultado.hidden = false;
    resultado.focus();
  }

  function retryButton() {
    const b = el('button', 'Reintentar el mismo envío');
    b.type = 'button';
    b.addEventListener('click', () => send(lastPayload));
    return b;
  }

  function renderSuccess(data) {
    const dup = data.duplicado === true;
    const dl = el('dl', undefined, 'datos');
    const add = (label, value) => dl.append(el('dt', label), value);

    add('Código de seguimiento', el('dd', String(data.codigo_publico)));
    add('Estado', el('dd', ESTADO[data.estado] || String(data.estado)));
    const prio = el('dd');
    prio.append(el('span', PRIORIDAD[data.prioridad] || String(data.prioridad), `badge ${String(data.prioridad).toLowerCase()}`));
    add('Prioridad', prio);
    add('Equipo asignado', el('dd', COLA[data.cola] || String(data.cola)));
    add('Primera revisión antes de', el('dd', `${data.fecha_limite} (hora de Lima)`));
    add('Plazo', el('dd', `${data.plazo_horas} horas desde el registro`));

    const note = dup
      ? 'Este envío ya estaba registrado. Te mostramos el reporte original; no se creó otro.'
      : 'Si envías este mismo formulario otra vez, verás este mismo reporte. Para crear uno distinto, usa «Empezar de nuevo».';
    showResult(dup ? 'dup' : 'ok', dup ? 'Este reporte ya estaba registrado' : 'Tu reporte fue registrado', [
      dl, el('p', note, 'help'),
    ]);
  }

  const ERROR_TITLE = {
    400: 'Revisa los datos',
    409: 'Este envío ya existe con otros datos',
    422: 'No pudimos registrar este reporte',
    503: 'No pudimos confirmar tu reporte',
  };

  function renderError(status, data) {
    const nodes = [el('p', (data && data.mensaje) || 'No se pudo procesar el envío.')];
    if (data && Array.isArray(data.detalle) && data.detalle.length) {
      const ul = el('ul');
      data.detalle.forEach((d) => ul.append(el('li', d)));
      nodes.push(ul);
    }
    nodes.push(el('p', `Código: ${(data && data.codigo) || `HTTP ${status}`}`, 'help'));
    if (status === 503) {
      nodes.push(el('p', 'Puedes reintentar: se usará el mismo identificador, así que no se duplicará.'));
      nodes.push(retryButton());
    }
    showResult('fail', ERROR_TITLE[status] || 'No se registró el reporte', nodes);
  }

  function renderNetworkError() {
    showResult('fail', 'Sin conexión con el servicio', [
      el('p', 'No recibimos respuesta, así que tu reporte no se confirmó. Puedes reintentar con el mismo identificador.'),
      retryButton(),
    ]);
  }

  // ---- Sending ----
  async function send(payload) {
    lastPayload = payload;
    enviar.disabled = true;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    try {
      const res = await fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      });
      let data = null;
      try { data = await res.json(); } catch (e) { /* non-JSON body */ }
      if ((res.status === 200 || res.status === 201) && data) renderSuccess(data);
      else renderError(res.status, data);
    } catch (e) {
      renderNetworkError();
    } finally {
      clearTimeout(timer);
      enviar.disabled = false;
    }
  }

  // ---- Wiring ----
  function syncConditionalFields() {
    const miraflores = fields.distrito.value === 'MIRAFLORES';
    $('campo-sector').hidden = !miraflores;
    if (!miraflores) fields.sector.value = '';
    const acumulacion = fields.categoria.value === 'ACUMULACION';
    $('campo-bolsas').hidden = !acumulacion;
    if (!acumulacion) fields.bolsas.value = '';
  }

  function updateCounters() {
    $('contador-referencia').textContent = `${fields.referencia.value.trim().length} / 120`;
    $('contador-descripcion').textContent = `${fields.descripcion.value.trim().length} / 200`;
  }

  function resetForm() {
    form.reset();
    syncConditionalFields();
    updateCounters();
    paintErrors({});
    resultado.hidden = true;
    lastPayload = null;
    requestId = storeRequestId(uuid());
    showRequestId();
    fields.distrito.focus();
  }

  fields.distrito.addEventListener('change', syncConditionalFields);
  fields.categoria.addEventListener('change', syncConditionalFields);
  fields.referencia.addEventListener('input', updateCounters);
  fields.descripcion.addEventListener('input', updateCounters);
  $('nuevo').addEventListener('click', resetForm);

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const errors = validate();
    paintErrors(errors);
    if (Object.keys(errors).length > 0) return;
    send(buildPayload());
  });

  syncConditionalFields();
  updateCounters();
  showRequestId();
  setupNotice();
})();
