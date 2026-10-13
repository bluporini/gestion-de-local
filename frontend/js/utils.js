import { $ } from './api.js';


/**
 * Escapa un texto para insertarlo en HTML (contenido o atributo).
 *
 * Usar en todo dato que venga de la base o del usuario antes de meterlo
 * en un template de innerHTML: sin esto, un nombre con comillas o con
 * "<" rompe la pantalla (ej: Body "Clásico" en un value="...").
 *
 * @param {*} v - Valor a escapar (null/undefined se convierten en '').
 * @returns {string} Texto seguro para HTML.
 */
export function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

/**
 * Formatea un valor numérico como importe en pesos argentinos.
 *
 * Los valores no numéricos o nulos se consideran cero.
 *
 * @param {number|string} v - Valor que se desea formatear.
 * @returns {string} Importe formateado según la configuración regional de Argentina.
 */
export function money(v) {
  const n = Number(v) || 0;
  return n.toLocaleString('es-AR', { style: 'currency', currency: 'ARS' });
}


/**
 * Quita los puntos de miles de un valor formateado y lo convierte a número.
 *
 * Uso: para leer el valor "real" de un input al que se le aplicó
 * `attachFormateoMiles`, en vez de usar parseFloat directo sobre
 * el value (que rompería con algo como "10.000").
 *
 * @param {string} v - Valor del input, con puntos de miles (ej: "10.000").
 * @returns {number} Valor numérico sin formatear (ej: 10000). NaN si está vacío.
 */
export function desformatearMiles(v) {
  if (!v) return NaN;
  return parseFloat(String(v).replace(/\./g, ''));
}


/**
 * Le agrega puntos de miles a un input numérico a medida que se escribe.
 *
 * Pensado para inputs de montos de plata (type="text", no type="number",
 * porque el navegador no permite puntos de miles en un input numérico
 * nativo). Solo deja escribir dígitos; el punto se inserta solo.
 * No soporta decimales a propósito: en esta app los montos son enteros
 * (pesos sin centavos).
 *
 * @param {HTMLInputElement} input - El input al que aplicarle el formato.
 * @param {Function} [onInput] - Callback opcional que se ejecuta después
 *   de formatear, útil para recalcular vueltos/totales en el mismo evento.
 */
export function attachFormateoMiles(input, onInput) {
  input.addEventListener('input', () => {
    const soloDigitos = input.value.replace(/\D/g, '');
    input.value = soloDigitos ? Number(soloDigitos).toLocaleString('es-AR') : '';
    if (onInput) onInput();
  });
}


/**
 * Obtiene la fecha actual en formato ISO de calendario (YYYY-MM-DD).
 *
 * @returns {string} Fecha actual en formato YYYY-MM-DD.
 */
export function hoyISO() {
  const hoy = new Date();
  const año = hoy.getFullYear();
  const mes = String(hoy.getMonth() + 1).padStart(2, '0');
  const dia = String(hoy.getDate()).padStart(2, '0');
  return `${año}-${mes}-${dia}`;
}


/**
 * Convierte una fecha proveniente del backend en un objeto Date.
 *
 * SQLite guarda CURRENT_TIMESTAMP en UTC como "YYYY-MM-DD HH:MM:SS"
 * (sin T ni Z), lo cual puede hacer que los navegadores interpreten
 * la fecha de forma inconsistente. La función normaliza el valor
 * a un formato ISO 8601 con UTC explícito.
 *
 * @param {string} fechaStr - Fecha recibida desde el backend.
 * @returns {Date|null} Fecha convertida o null si no se proporcionó un valor.
 */
export function parseFechaUTC(fechaStr) {
  if (!fechaStr) return null;
  const iso = fechaStr.includes('T')
    ? (fechaStr.endsWith('Z') ? fechaStr : fechaStr + 'Z')
    : fechaStr.replace(' ', 'T') + 'Z';
  return new Date(iso);
}


/**
 * Formatea una fecha para mostrarla en la interfaz.
 *
 * Utiliza el formato local de Argentina e incluye fecha y hora
 * hasta los segundos.
 *
 * @param {Date|null} fecha - Fecha que se desea formatear.
 * @returns {string} Fecha y hora formateadas, o "—" si no existe.
 */
export function formatoFechaHora(fecha) {
  if (!fecha) return '—';
  return fecha.toLocaleString('es-AR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false
  });
}


/**
 * Genera los controles de paginación para una lista.
 *
 * Muestra los botones para avanzar o retroceder de página y la
 * cantidad total de páginas y registros. El callback se invoca
 * mediante un atributo onclick generado dinámicamente.
 *
 * @param {string} contenedorId - ID del elemento donde se renderiza la paginación.
 * @param {number} page - Página actualmente seleccionada.
 * @param {number} pageSize - Cantidad de registros por página.
 * @param {number} total - Cantidad total de registros.
 * @param {string} callbackName - Nombre de la función que se ejecutará al cambiar de página.
 */
export function renderPaginacion(contenedorId, page, pageSize, total, callbackName) {
  const cont = $('#' + contenedorId);
  const totalPaginas = Math.max(Math.ceil(total / pageSize), 1);
  if (totalPaginas <= 1) { cont.innerHTML = ''; return; }
  cont.innerHTML = `
    <button ${page <= 1 ? 'disabled' : ''} onclick="(${callbackName})(${page - 1})">‹ Anterior</button>
    <span>Página ${page} de ${totalPaginas} (${total} en total)</span>
    <button ${page >= totalPaginas ? 'disabled' : ''} onclick="(${callbackName})(${page + 1})">Siguiente ›</button>
  `;
}


/**
 * Genera el detalle textual del método de pago de una venta.
 *
 * Para pagos en efectivo agrega el monto abonado y el vuelto.
 * Para pagos con tarjeta agrega el tipo de tarjeta.
 *
 * @param {Object} v - Objeto con los datos de la venta.
 * @returns {string} HTML con la información del método de pago.
 */
export function detallePago(v) {
  const nombres = { efectivo: 'Efectivo', tarjeta_debito: 'Tarjeta débito', tarjeta_credito: 'Tarjeta crédito', transferencia: 'Transferencia', otro: 'Otro' };
  let texto = nombres[v.metodo_pago] || esc(v.metodo_pago);
  if (v.metodo_pago === 'efectivo' && v.monto_pagado != null) {
    texto += `<br><span class="sub" style="color:var(--muted); font-size:.76rem">Pagó ${money(v.monto_pagado)} · Vuelto ${money(v.vuelto)}</span>`;
  }
  if ((v.metodo_pago === 'tarjeta_credito' || v.metodo_pago === 'tarjeta_debito') && v.tipo_tarjeta) {
    texto += `<br><span class="sub" style="color:var(--muted); font-size:.76rem">${esc(v.tipo_tarjeta)}</span>`;
  }
  return texto;
}