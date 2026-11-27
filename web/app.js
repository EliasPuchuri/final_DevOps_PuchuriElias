(() => {
  'use strict';

  const ENDPOINT = '/webhook/reportes';
  const TIMEOUT_MS = 15000;
  const STORAGE_KEY = 'mira.requestId';

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

  // The identifier belongs to one submission and is kept so a retry reuses it.
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
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) return saved;
    } catch (e) { /* storage unavailable: keep the id in memory only */ }
    return storeRequestId(uuid());
  }

  function storeRequestId(id) {
    try { sessionStorage.setItem(STORAGE_KEY, id); } catch (e) { /* ignore */ }
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

    if (!distrito) errors.distrito = 'Selecciona un distrito.';
    if (distrito === 'MIRAFLORES' && !fields.sector.value) errors.sector = 'Selecciona un sector.';
    if (!categoria) errors.categoria = 'Selecciona una categoría.';
    if (categoria === 'ACUMULACION') {
      const n = Number(fields.bolsas.value);
      if (fields.bolsas.value === '' || !Number.isInteger(n) || n < 1 || n > 50) {
        errors.bolsas = 'Indica un número entero de bolsas entre 1 y 50.';
      }
    }
    if (referencia.length < 5 || referencia.length > 120) {
      errors.referencia = 'La referencia debe tener entre 5 y 120 caracteres.';
    }
    if (descripcion.length < 15 || descripcion.length > 200) {
      errors.descripcion = 'La descripción debe tener entre 15 y 200 caracteres.';
    }
    if (selectedObstruccion() === null) errors.obstruccion = 'Indica si los residuos impiden el paso peatonal.';
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
    if (first) {
      const target = fields[first] || form.querySelector('input[name="obstruccion"]');
      target.focus();
    }
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

  function renderSuccess(status, data) {
    const dup = data.duplicado === true;
    const rows = [
      ['Código del reporte', data.codigo_publico],
      ['Estado', data.estado],
      ['Prioridad', data.prioridad],
      ['Cola asignada', data.cola],
      ['Plazo de primera revisión', `${data.plazo_horas} horas`],
      ['Fecha límite (hora de Lima)', data.fecha_limite],
      ['¿Duplicado?', dup ? 'Sí' : 'No'],
    ];
    const dl = el('dl', undefined, 'datos');
    rows.forEach(([k, v]) => { dl.append(el('dt', k), el('dd', String(v))); });
    const note = dup
      ? 'Este envío ya estaba registrado: se muestra el reporte original, sin crear otro.'
      : 'Si vuelves a enviar este mismo formulario sin cambios, obtendrás el mismo reporte (duplicado). Para crear otro, usa «Nuevo reporte».';
    showResult(dup ? 'dup' : 'ok', dup ? 'Reporte ya registrado' : 'Reporte registrado', [
      el('p', data.mensaje || ''), dl, el('p', note, 'hint'),
    ]);
  }

  function renderError(status, data) {
    const code = data && data.codigo ? data.codigo : `HTTP ${status}`;
    const nodes = [el('p', (data && data.mensaje) || 'No se pudo procesar el envío.')];
    if (data && Array.isArray(data.detalle) && data.detalle.length) {
      const ul = el('ul');
      data.detalle.forEach((d) => ul.append(el('li', d)));
      nodes.push(ul);
    }
    nodes.push(el('p', `Código: ${code}`, 'hint'));
    if (status === 503) {
      nodes.push(el('p', 'Tu reporte no se confirmó. Puedes reintentar: se usará el mismo identificador, por lo que no se duplicará.'));
      nodes.push(retryButton());
    }
    showResult('fail', 'No se registró el reporte', nodes);
  }

  function renderNetworkError() {
    showResult('fail', 'No se pudo contactar al servicio', [
      el('p', 'No recibimos respuesta. Tu reporte no se confirmó. Puedes reintentar con el mismo identificador.'),
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
      if ((res.status === 200 || res.status === 201) && data) renderSuccess(res.status, data);
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

  function updateCounter() {
    $('contador').textContent = `${fields.descripcion.value.trim().length} / 200`;
  }

  function resetForm() {
    form.reset();
    syncConditionalFields();
    updateCounter();
    paintErrors({});
    resultado.hidden = true;
    lastPayload = null;
    requestId = storeRequestId(uuid());
    showRequestId();
    fields.distrito.focus();
  }

  fields.distrito.addEventListener('change', syncConditionalFields);
  fields.categoria.addEventListener('change', syncConditionalFields);
  fields.descripcion.addEventListener('input', updateCounter);
  $('nuevo').addEventListener('click', resetForm);

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const errors = validate();
    paintErrors(errors);
    if (Object.keys(errors).length > 0) return;
    send(buildPayload());
  });

  syncConditionalFields();
  updateCounter();
  showRequestId();
})();
