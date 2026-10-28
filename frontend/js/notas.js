import { $, apiFetch } from './api.js';
import { esc, parseFechaUTC, formatoFechaHora } from './utils.js';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

let notas = [];
let etiquetas = [];
// Filtro de etiqueta activo ('' = todas).
let etiquetaFiltro = '';


/**
 * Separa un texto "a, b, #c" en una lista de etiquetas.
 *
 * @param {string} texto - Etiquetas separadas por coma.
 * @returns {string[]} Etiquetas (el backend las limpia y saca repetidas).
 */
function parsearEtiquetas(texto) {
  return texto.split(',').map(e => e.trim()).filter(Boolean);
}


/**
 * Carga las notas (según los filtros) y las etiquetas en uso.
 *
 * @returns {Promise<void>}
 */
export async function cargarNotas() {
  const params = new URLSearchParams();
  if (etiquetaFiltro) params.set('etiqueta', etiquetaFiltro);
  const q = $('#buscarNotas').value.trim();
  if (q) params.set('q', q);
  if ($('#ocultarHechas').checked) params.set('ocultar_hechas', '1');

  const [resNotas, resEtiquetas] = await Promise.all([
    apiFetch('/api/notas?' + params.toString()),
    apiFetch('/api/notas/etiquetas'),
  ]);
  if (!resNotas.ok || !resEtiquetas.ok) return;
  notas = await resNotas.json();
  etiquetas = await resEtiquetas.json();

  // Si la etiqueta filtrada ya no existe (se borró su última nota), volver a "Todas".
  if (etiquetaFiltro && !etiquetas.some(e => e.nombre.toLowerCase() === etiquetaFiltro.toLowerCase())) {
    etiquetaFiltro = '';
    return cargarNotas();
  }

  renderEtiquetas();
  renderNotas(q);
}


function renderEtiquetas() {
  const chip = (valor, texto, cantidad) => `
    <button type="button" class="chip ${valor.toLowerCase() === etiquetaFiltro.toLowerCase() ? 'active' : ''}"
      data-etiqueta="${esc(valor)}" ${cantidad !== undefined ? `title="${cantidad} nota(s) pendiente(s)"` : ''}>
      ${texto}${cantidad !== undefined ? `<span class="chip-cantidad">${cantidad}</span>` : ''}
    </button>`;

  $('#filtrosEtiquetas').innerHTML = etiquetas.length
    ? chip('', 'Todas') + etiquetas.map(e => chip(e.nombre, `#${esc(e.nombre)}`, e.pendientes)).join('')
    : '';

  // Sugerencias para el campo de etiquetas al escribir una nota.
  $('#sugerenciasEtiquetas').innerHTML = etiquetas.map(e => `<option value="${esc(e.nombre)}"></option>`).join('');
}


function renderNotas(busqueda) {
  const hayFiltros = etiquetaFiltro || busqueda || $('#ocultarHechas').checked;

  $('#listaNotas').innerHTML = notas.length
    ? notas.map(n => `
      <div class="nota ${n.hecha ? 'hecha' : ''}" id="nota-${n.id}">
        <input type="checkbox" ${n.hecha ? 'checked' : ''} onchange="toggleNota(${n.id}, this.checked)"
          title="${n.hecha ? 'Marcar como pendiente' : 'Marcar como hecha'}" />
        <div class="nota-cuerpo">
          <div class="nota-texto">${esc(n.texto)}</div>
          <div>
            ${n.etiquetas.map(e => `<button type="button" class="etiqueta" data-etiqueta="${esc(e)}"
              title="Ver las notas con esta etiqueta">#${esc(e)}</button>`).join('')}
          </div>
          <div class="nota-fecha">${formatoFechaHora(parseFechaUTC(n.fecha))}</div>
        </div>
        <div class="row-actions">
          <button class="btn icon small" onclick="editarNota(${n.id})" title="Editar">✏️</button>
          <button class="btn danger small" onclick="borrarNota(${n.id})" title="Borrar">🗑</button>
        </div>
      </div>`).join('')
    : `<div class="empty">${hayFiltros ? 'No hay notas con ese filtro.' : 'Todavía no hay notas. Escribí la primera arriba.'}</div>`;
}


export async function toggleNota(id, hecha) {
  await apiFetch(`/api/notas/${id}`, {
    method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify({ hecha })
  });
  cargarNotas();
}


/**
 * Reemplaza el texto de la nota por campos editables (texto y etiquetas).
 *
 * @param {number} id - ID de la nota.
 */
export function editarNota(id) {
  const nota = notas.find(n => n.id === id);
  if (!nota) return;
  const cuerpo = document.querySelector(`#nota-${id} .nota-cuerpo`);
  cuerpo.innerHTML = `
    <div class="nota-edicion">
      <textarea rows="3" maxlength="2000" id="editarNota-${id}">${esc(nota.texto)}</textarea>
      <input id="editarEtiquetas-${id}" list="sugerenciasEtiquetas" autocomplete="off"
        placeholder="Etiquetas separadas por coma" value="${esc(nota.etiquetas.join(', '))}" />
      <div class="row-actions">
        <button class="btn small" onclick="guardarEdicionNota(${id})">Guardar</button>
        <button class="btn secondary small" onclick="cancelarEdicionNota()">Cancelar</button>
      </div>
    </div>`;
  const campo = $(`#editarNota-${id}`);
  campo.focus();
  campo.setSelectionRange(campo.value.length, campo.value.length);
}


export async function guardarEdicionNota(id) {
  const texto = $(`#editarNota-${id}`).value;
  if (!texto.trim()) { alert('La nota no puede quedar vacía'); return; }
  const res = await apiFetch(`/api/notas/${id}`, {
    method: 'PATCH', headers: JSON_HEADERS,
    body: JSON.stringify({ texto, etiquetas: parsearEtiquetas($(`#editarEtiquetas-${id}`).value) })
  });
  if (!res.ok) { alert('No se pudo guardar la nota'); return; }
  cargarNotas();
}


export function cancelarEdicionNota() {
  renderNotas($('#buscarNotas').value.trim());
}


export async function borrarNota(id) {
  if (!confirm('¿Borrar esta nota?')) return;
  await apiFetch(`/api/notas/${id}`, { method: 'DELETE' });
  cargarNotas();
}


function filtrarPorEtiqueta(nombre) {
  etiquetaFiltro = nombre;
  cargarNotas();
}


/**
 * Inicializa el formulario de nota nueva y los filtros.
 */
export function initNotas() {
  const form = $('#formNuevaNota');
  const textoNota = $('#textoNuevaNota');
  const etiquetasNota = $('#etiquetasNuevaNota');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const texto = textoNota.value.trim();
    if (!texto) { textoNota.focus(); return; }

    // Si se está filtrando por una etiqueta y no se escribió ninguna,
    // la nota nueva se crea con esa etiqueta (así aparece en la lista).
    let lista = parsearEtiquetas(etiquetasNota.value);
    if (!lista.length && etiquetaFiltro) lista = [etiquetaFiltro];

    const res = await apiFetch('/api/notas', {
      method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ texto, etiquetas: lista })
    });
    if (!res.ok) { alert('No se pudo guardar la nota'); return; }
    textoNota.value = '';
    etiquetasNota.value = '';
    textoNota.focus();
    cargarNotas();
  });

  // Enter guarda; Shift+Enter hace un salto de línea.
  textoNota.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  // Filtro por etiqueta: los chips de arriba y las etiquetas de cada nota.
  $('#filtrosEtiquetas').addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (chip) filtrarPorEtiqueta(chip.dataset.etiqueta);
  });
  $('#listaNotas').addEventListener('click', (e) => {
    const etiqueta = e.target.closest('.etiqueta');
    if (etiqueta) filtrarPorEtiqueta(etiqueta.dataset.etiqueta);
  });

  let debounce;
  $('#buscarNotas').addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(cargarNotas, 250);
  });
  $('#ocultarHechas').addEventListener('change', cargarNotas);
}
