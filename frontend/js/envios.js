import { $, apiFetch } from './api.js';
import { money, esc, hoyISO, desformatearMiles, attachFormateoMiles } from './utils.js';

const ESTADOS = {
  por_preparar: { texto: '📋 Por preparar', siguiente: 'despachado', accion: '🚚 Marcar despachado' },
  despachado: { texto: '🚚 Despachado', siguiente: 'entregado', accion: '✅ Marcar entregado' },
  entregado: { texto: '✅ Entregado' },
  problema: { texto: '⚠️ Devuelto / Problema', siguiente: 'resuelto', accion: '✔ Resuelto' },
  resuelto: { texto: '✔ Resuelto' },
};

const JSON_HEADERS = { 'Content-Type': 'application/json' };

// Los envíos cerrados (entregados y resueltos) se muestran de a tandas: la
// lista crece con el tiempo.
const TANDA_CERRADOS = 30;
// Estados cerrados: van al desplegable, no a la lista de envíos en curso.
const CERRADOS = ['entregado', 'resuelto'];
// Un envío con problema cuya fecha de envío tiene más de estos días pasa a
// su propio desplegable, para no quedar para siempre entre los en curso.
const DIAS_PROBLEMA_VIEJO = 30;

let envios = [];
let filtroEstado = '';
let cerradosVisibles = TANDA_CERRADOS;
// Si los desplegables están abiertos (se mantiene al recargar la lista).
let cerradosAbierto = false;
let problemasViejosAbierto = false;
let envioEditandoId = null;
// Venta elegida en el buscador del formulario: { id, codigo, cliente } o null.
let ventaVinculada = null;


/**
 * 'YYYY-MM-DD' -> 'DD/MM/YYYY'.
 */
/**
 * Fecha (YYYY-MM-DD) de hace `dias` días, según la fecha local de la PC.
 */
function haceDias(dias) {
  const fecha = new Date();
  fecha.setDate(fecha.getDate() - dias);
  const mes = String(fecha.getMonth() + 1).padStart(2, '0');
  const dia = String(fecha.getDate()).padStart(2, '0');
  return `${fecha.getFullYear()}-${mes}-${dia}`;
}


function fechaCorta(iso) {
  if (!iso) return '';
  const [anio, mes, dia] = iso.split('-');
  return `${dia}/${mes}/${anio}`;
}


/**
 * Carga los envíos según el filtro de estado y la búsqueda, y los muestra.
 *
 * @returns {Promise<void>}
 */
export async function cargarEnvios() {
  const params = new URLSearchParams();
  if (filtroEstado) params.set('estado', filtroEstado);
  const q = $('#buscarEnvios').value.trim();
  if (q) params.set('q', q);

  const res = await apiFetch('/api/envios?' + params.toString());
  if (!res.ok) return;
  envios = await res.json();
  renderLista(q);
}


/**
 * Arma la lista: los envíos en curso arriba y los cerrados (entregados y
 * resueltos) en un
 * desplegable (cerrado salvo que se esté buscando), de a tandas.
 *
 * @param {string} busqueda - Texto buscado ('' si no hay búsqueda).
 */
function renderLista(busqueda) {
  const cont = $('#listaEnvios');

  if (!envios.length) {
    cont.innerHTML = `<div class="empty">${filtroEstado || busqueda
      ? 'No hay envíos con ese filtro.'
      : 'Todavía no hay envíos. Cargá el primero con "+ Nuevo envío".'}</div>`;
    return;
  }

  const limiteProblema = haceDias(DIAS_PROBLEMA_VIEJO);
  const esProblemaViejo = e => e.estado === 'problema' && e.fecha < limiteProblema;
  const cerrados = envios.filter(e => CERRADOS.includes(e.estado));
  // Con el filtro "Problema" se ven todos juntos, sin separar los viejos.
  const problemasViejos = filtroEstado === 'problema' ? [] : envios.filter(esProblemaViejo);
  const enCurso = envios.filter(e => !CERRADOS.includes(e.estado) && !problemasViejos.includes(e));

  const tandaCerrados = () => {
    const visibles = cerrados.slice(0, cerradosVisibles);
    const faltan = cerrados.length - visibles.length;
    return `
      <div class="envios-lista">${visibles.map(renderEnvio).join('')}</div>
      ${faltan > 0 ? `
        <div class="ver-mas">
          <button type="button" class="btn secondary" onclick="mostrarMasCerrados()">
            Mostrar ${Math.min(faltan, TANDA_CERRADOS)} más (quedan ${faltan})
          </button>
        </div>` : ''}`;
  };

  // Filtros "Entregados" o "Resueltos": se ven directo, sin desplegable.
  if (CERRADOS.includes(filtroEstado)) {
    cont.innerHTML = tandaCerrados();
    return;
  }

  // Los desplegables se abren solos si hay resultados de una búsqueda adentro.
  const abiertoCerrados = cerradosAbierto || (busqueda && cerrados.length > 0);
  const abiertoProblemas = problemasViejosAbierto || (busqueda && problemasViejos.length > 0);
  cont.innerHTML = `
    ${enCurso.length
      ? `<div class="envios-lista">${enCurso.map(renderEnvio).join('')}</div>`
      : (filtroEstado ? '' : '<div class="empty">No hay envíos en curso. 🎉</div>')}
    ${problemasViejos.length ? `
      <details class="envios-desplegable envios-problemas-viejos" ${abiertoProblemas ? 'open' : ''}>
        <summary>⚠️ Problemas de hace más de ${DIAS_PROBLEMA_VIEJO} días (${problemasViejos.length})</summary>
        <div class="envios-lista">${problemasViejos.map(renderEnvio).join('')}</div>
      </details>` : ''}
    ${cerrados.length ? `
      <details class="envios-desplegable envios-cerrados" ${abiertoCerrados ? 'open' : ''}>
        <summary>✅ Entregados y resueltos (${cerrados.length})</summary>
        ${tandaCerrados()}
      </details>` : ''}`;

  const cerradosEl = cont.querySelector('.envios-cerrados');
  if (cerradosEl) {
    cerradosEl.addEventListener('toggle', () => { cerradosAbierto = cerradosEl.open; });
  }
  const problemasEl = cont.querySelector('.envios-problemas-viejos');
  if (problemasEl) {
    problemasEl.addEventListener('toggle', () => { problemasViejosAbierto = problemasEl.open; });
  }
}


export function mostrarMasCerrados() {
  cerradosVisibles += TANDA_CERRADOS;
  renderLista($('#buscarEnvios').value.trim());
}


function renderEnvio(e) {
  const estado = ESTADOS[e.estado] || { texto: e.estado };
  const direccion = [e.direccion, e.localidad, e.provincia, e.codigo_postal && `CP ${e.codigo_postal}`]
    .filter(Boolean).map(esc).join(', ');

  return `
    <div class="envio-card">
      <div class="envio-cabecera">
        <span class="badge ${esc(e.estado)}">${esc(estado.texto)}</span>
        <span>${fechaCorta(e.fecha)}</span>
      </div>
      <div class="envio-destinatario">${esc(e.destinatario)}</div>
      ${direccion ? `<div>📍 ${direccion}</div>` : ''}
      ${e.telefono ? `<div>📞 ${esc(e.telefono)}</div>` : ''}
      <div>🚚 ${esc(e.empresa)}</div>
      ${e.numero_seguimiento ? `
        <div class="envio-seguimiento">
          🔎 ${esc(e.numero_seguimiento)}
          <button class="btn secondary small" onclick="copiarSeguimiento(${e.id})" title="Copiar número">📋</button>
        </div>` : ''}
      <div>💲 ${money(e.costo)} · paga ${e.paga === 'local' ? 'el local' : 'el cliente'}</div>
      ${e.venta_codigo ? `<div>🧾 Venta ${esc(e.venta_codigo)}${e.venta_cliente ? ` · ${esc(e.venta_cliente)}` : ''}</div>` : ''}
      ${e.observaciones ? `<div style="white-space:pre-wrap">📝 ${esc(e.observaciones)}</div>` : ''}
      <div class="envio-acciones">
        <div class="envio-acciones-estado">
          ${estado.siguiente ? `<button class="btn small" onclick="avanzarEnvio(${e.id}, '${estado.siguiente}')">${estado.accion}</button>` : ''}
          ${e.estado !== 'problema' && !CERRADOS.includes(e.estado)
            ? `<button class="btn secondary small" onclick="avanzarEnvio(${e.id}, 'problema')">⚠️ Problema</button>` : ''}
        </div>
        <div class="row-actions">
          <button class="btn icon small" onclick="abrirModalEnvio(${e.id})" title="Editar">✏️</button>
          <button class="btn danger small" onclick="borrarEnvio(${e.id})" title="Borrar">🗑</button>
        </div>
      </div>
    </div>`;
}


export async function avanzarEnvio(id, estado) {
  const res = await apiFetch(`/api/envios/${id}`, {
    method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify({ estado })
  });
  if (!res.ok) { alert('No se pudo actualizar el envío'); return; }
  cargarEnvios();
}


export async function borrarEnvio(id) {
  const envio = envios.find(e => e.id === id);
  if (!confirm(`¿Borrar el envío a ${envio ? envio.destinatario : 'este destinatario'}?`)) return;
  await apiFetch(`/api/envios/${id}`, { method: 'DELETE' });
  cargarEnvios();
}


export async function copiarSeguimiento(id) {
  const envio = envios.find(e => e.id === id);
  if (!envio || !envio.numero_seguimiento) return;
  try {
    await navigator.clipboard.writeText(envio.numero_seguimiento);
  } catch {
    prompt('Copiá el número de seguimiento:', envio.numero_seguimiento);
  }
}


// ---------- Formulario ----------


function mostrarVentaVinculada() {
  $('#ventaVinculadaEnvio').innerHTML = ventaVinculada
    ? `🧾 Venta <strong>${esc(ventaVinculada.codigo)}</strong>${ventaVinculada.cliente ? ` · ${esc(ventaVinculada.cliente)}` : ''}
       <button type="button" class="btn secondary small" onclick="quitarVentaEnvio()">Quitar</button>`
    : '';
}


export function quitarVentaEnvio() {
  ventaVinculada = null;
  mostrarVentaVinculada();
}


/**
 * Abre el formulario de envío: vacío para uno nuevo, o con los datos del
 * envío indicado para editarlo.
 *
 * @param {number} [id] - ID del envío a editar.
 */
export function abrirModalEnvio(id) {
  const envio = id ? envios.find(e => e.id === id) : null;
  envioEditandoId = envio ? envio.id : null;

  $('#formEnvio').reset();
  $('#tituloModalEnvio').textContent = envio ? 'Editar envío' : 'Nuevo envío';
  $('#msgEnvio').textContent = '';
  $('#buscadorVentaEnvio').value = '';
  $('#resultadosVentaEnvio').classList.remove('active');

  $('#envioFecha').value = envio ? envio.fecha : hoyISO();
  $('#envioEmpresa').value = envio ? envio.empresa : '';
  $('#envioSeguimiento').value = envio?.numero_seguimiento || '';
  $('#envioEstado').value = envio ? envio.estado : 'por_preparar';
  $('#envioDestinatario').value = envio ? envio.destinatario : '';
  $('#envioTelefono').value = envio?.telefono || '';
  $('#envioDireccion').value = envio?.direccion || '';
  $('#envioLocalidad').value = envio?.localidad || '';
  $('#envioProvincia').value = envio?.provincia || '';
  $('#envioCP').value = envio?.codigo_postal || '';
  $('#envioCosto').value = envio?.costo ? Math.round(envio.costo).toLocaleString('es-AR') : '';
  $('#envioPaga').value = envio ? envio.paga : 'cliente';
  $('#envioObservaciones').value = envio?.observaciones || '';

  ventaVinculada = envio && envio.venta_id
    ? { id: envio.venta_id, codigo: envio.venta_codigo, cliente: envio.venta_cliente }
    : null;
  mostrarVentaVinculada();

  $('#modalEnvio').classList.add('active');
}


async function guardarEnvio(e) {
  e.preventDefault();
  const msg = $('#msgEnvio');
  const costo = desformatearMiles($('#envioCosto').value);

  const body = {
    fecha: $('#envioFecha').value,
    empresa: $('#envioEmpresa').value,
    numero_seguimiento: $('#envioSeguimiento').value,
    estado: $('#envioEstado').value,
    destinatario: $('#envioDestinatario').value,
    telefono: $('#envioTelefono').value,
    direccion: $('#envioDireccion').value,
    localidad: $('#envioLocalidad').value,
    provincia: $('#envioProvincia').value,
    codigo_postal: $('#envioCP').value,
    costo: Number.isNaN(costo) ? 0 : costo,
    paga: $('#envioPaga').value,
    observaciones: $('#envioObservaciones').value,
    venta_id: ventaVinculada ? ventaVinculada.id : null,
  };

  const res = await apiFetch(envioEditandoId ? `/api/envios/${envioEditandoId}` : '/api/envios', {
    method: envioEditandoId ? 'PATCH' : 'POST', headers: JSON_HEADERS, body: JSON.stringify(body)
  });

  if (!res.ok) {
    const err = await res.json();
    msg.className = 'msg error';
    msg.textContent = err.error || 'No se pudo guardar el envío';
    return;
  }

  $('#modalEnvio').classList.remove('active');
  cargarEnvios();
}


/**
 * Inicializa filtros, búsqueda y formulario de envíos.
 */
export function initEnvios() {
  // Filtros por estado.
  $('#filtrosEnvio').addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    document.querySelectorAll('#filtrosEnvio .chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    filtroEstado = chip.dataset.estado;
    cerradosVisibles = TANDA_CERRADOS;
    cargarEnvios();
  });

  // Búsqueda.
  let debounceLista;
  $('#buscarEnvios').addEventListener('input', () => {
    clearTimeout(debounceLista);
    debounceLista = setTimeout(() => {
      cerradosVisibles = TANDA_CERRADOS;
      cargarEnvios();
    }, 300);
  });

  $('#formEnvio').addEventListener('submit', guardarEnvio);
  attachFormateoMiles($('#envioCosto'));

  // Buscador de venta para vincular.
  const input = $('#buscadorVentaEnvio');
  const resultados = $('#resultadosVentaEnvio');
  let encontradas = [];
  let debounceVenta;

  input.addEventListener('input', () => {
    clearTimeout(debounceVenta);
    const q = input.value.trim();
    if (!q) { resultados.classList.remove('active'); return; }

    debounceVenta = setTimeout(async () => {
      const res = await apiFetch(`/api/ventas/buscar?q=${encodeURIComponent(q)}`);
      encontradas = res.ok ? await res.json() : [];
      resultados.innerHTML = encontradas.length
        ? encontradas.map(v => `
          <div class="buscador-item" data-id="${v.id}">
            ${esc(v.codigo) || '—'} — ${esc(v.cliente) || 'Sin cliente'}
            <div class="sub">${money(v.total)} · ${(v.venta_items || []).length} ítem(s)</div>
          </div>`).join('')
        : '<div class="buscador-item">Sin resultados</div>';
      resultados.classList.add('active');
    }, 300);
  });

  resultados.addEventListener('click', (e) => {
    const item = e.target.closest('.buscador-item');
    if (!item || !item.dataset.id) return;
    const venta = encontradas.find(v => String(v.id) === item.dataset.id);
    if (!venta) return;

    ventaVinculada = { id: venta.id, codigo: venta.codigo, cliente: venta.cliente };
    mostrarVentaVinculada();
    input.value = '';
    resultados.classList.remove('active');

    // Si el destinatario está vacío, completarlo con el cliente de la venta.
    if (!$('#envioDestinatario').value.trim() && venta.cliente) {
      $('#envioDestinatario').value = venta.cliente;
    }
  });
}
