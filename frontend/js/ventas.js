import { $, apiUrlInput, apiFetch } from './api.js';
import { money, esc, desformatearMiles, attachFormateoMiles, renderPaginacion, detallePago, parseFechaUTC, formatoFechaHora } from './utils.js';
import { variantesIndex, cargarIndiceBusqueda } from './productos.js';

let paginaVentas = 1;
export let carrito = [];


/**
 * Carga y muestra las ventas registradas de forma paginada.
 *
 * Permite filtrar las ventas por fecha y muestra información del cliente,
 * productos, forma de pago, total, ganancia y estado de cada venta.
 *
 * @param {number} [page=1] - Número de página que se desea cargar.
 * @returns {Promise<void>}
 */
export async function cargarVentas(page = 1) {
  if (!apiUrlInput.value) return;
  paginaVentas = page;
  const fecha = $('#fechaVentas').value;
  const params = new URLSearchParams({ page, page_size: 20 });
  if (fecha) params.set('fecha', fecha);

  const res = await apiFetch('/api/ventas?' + params.toString());
  const { data, total, page_size } = await res.json();

  $('#tablaVentas').innerHTML = data.length ? data.map(v => `
    <tr>
      <td>${formatoFechaHora(parseFechaUTC(v.fecha))}</td>
      <td>${esc(v.codigo) || '—'}</td>
      <td>${esc(v.cliente) || '—'}</td>
      <td>${(v.venta_items || []).map(i => `${i.cantidad}× ${esc(i.variantes_producto?.productos?.nombre)} (${esc(i.variantes_producto?.codigo)})`).join('<br>')}</td>
      <td>${detallePago(v)}</td>
      <td>${money(v.total)}</td>
      <td>${money(v.ganancia)}</td>
      <td>
        <span class="badge ${esc(v.estado)}">${esc(v.estado)}</span>
        ${v.tiene_cambio ? '<span class="badge cambio">Cambio</span>' : ''}
      </td>
      <td>
        <div class="row-actions">
          <button class="btn icon small" onclick="abrirEditarVenta('${v.id}', ${esc(JSON.stringify(v.cliente || ''))}, ${esc(JSON.stringify(v.metodo_pago || ''))})">✏️</button>
          <button class="btn danger small" onclick="borrarVenta('${v.id}')">🗑</button>
          ${v.estado === 'realizada' ? `<button class="btn danger small" onclick="marcarDevolucion('${v.id}')">Devolución</button>` : ''}
        </div>
      </td>
    </tr>`).join('') : '<tr><td colspan="8" class="empty">No hay ventas para este filtro</td></tr>';

  renderPaginacion('paginacionVentas', page, page_size, total, 'cargarVentas');
}

export function limpiarFiltroFechaVentas() {
  $('#fechaVentas').value = '';
  cargarVentas(1);
}



/**
 * Marca una venta como devolución.
 *
 * El backend se encarga de revertir los efectos de la venta,
 * incluyendo la reposición del stock y el ajuste de los ingresos.
 *
 * @param {number|string} ventaId - Identificador de la venta.
 * @param {Function} refrescarTodo - Función utilizada para actualizar la interfaz.
 * @returns {Promise<void>}
 */
export async function marcarDevolucion(ventaId, refrescarTodo) {
  if (!confirm('¿Marcar esta venta como devolución? Se repondrá el stock y se descontará de los ingresos.')) return;
  const res = await apiFetch(`/api/ventas/${ventaId}/devolucion`, { method: 'POST' });
  if (res.ok) { refrescarTodo(); }
  else alert('No se pudo procesar la devolución');
}


/**
 * Elimina una venta.
 *
 * Si la venta estaba realizada, el backend repone el stock correspondiente.
 *
 * @param {number|string} ventaId - Identificador de la venta.
 * @param {Function} refrescarTodo - Función utilizada para actualizar la interfaz.
 * @returns {Promise<void>}
 */
export async function borrarVenta(ventaId, refrescarTodo) {
  if (!confirm('¿Borrar esta venta definitivamente? Si estaba realizada, se repone el stock.')) return;
  const res = await apiFetch(`/api/ventas/${ventaId}`, { method: 'DELETE' });
  if (res.ok) { refrescarTodo(); }
  else alert('No se pudo borrar la venta');
}


/**
 * Abre el modal para editar una venta y carga sus datos actuales.
 *
 * @param {number|string} id - Identificador de la venta.
 * @param {string} cliente - Nombre del cliente.
 * @param {string} metodo - Método de pago utilizado en la venta.
 */
export function abrirEditarVenta(id, cliente, metodo) {
  $('#ventaIdEdit').value = id;
  $('#editCliente').value = cliente || '';
  $('#editMetodoPago').value = metodo;
  $('#msgEditarVenta').textContent = '';
  $('#modalEditarVenta').classList.add('active');
}


/**
 * Guarda los cambios realizados sobre una venta.
 *
 * Actualiza el cliente y el método de pago y luego refresca
 * la lista de ventas y el dashboard.
 *
 * @param {Function} refrescarDashboard - Función utilizada para actualizar el dashboard.
 * @returns {Promise<void>}
 */
export async function guardarEdicionVenta(refrescarDashboard) {
  const id = $('#ventaIdEdit').value;
  const body = { cliente: $('#editCliente').value, metodo_pago: $('#editMetodoPago').value };
  const res = await apiFetch(`/api/ventas/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  });
  if (res.ok) {
    cargarVentas();
    refrescarDashboard();
    setTimeout(() => $('#modalEditarVenta').classList.remove('active'), 300);
  } else {
    $('#msgEditarVenta').className = 'msg error';
    $('#msgEditarVenta').textContent = 'No se pudo guardar';
  }
}

// ---- Modal venta / carrito / buscador ----


/**
 * Abre y reinicia el modal de creación de una venta.
 *
 * Vacía el carrito, limpia los campos del formulario, establece efectivo
 * como método de pago predeterminado y carga el índice de búsqueda de productos.
 */
export function abrirModalVenta() {
  carrito = [];
  renderCarrito();
  $('#inputCliente').value = '';
  $('#buscadorProducto').value = '';
  $('#varianteSeleccionada').value = '';
  $('#msgVenta').textContent = '';
  $('#selectMetodoPago').value = 'efectivo';
  $('#inputMontoPagado').value = '';
  $('#modalVenta').classList.add('active');
  onCambioMetodoPago();
  cargarIndiceBusqueda();
}


/**
 * Actualiza la sección de pago del formulario según el método seleccionado.
 *
 * Muestra los campos correspondientes a efectivo o tarjeta y recalcula
 * el vuelto cuando se selecciona efectivo.
 */
export function onCambioMetodoPago() {
  const metodo = $('#selectMetodoPago').value;
  $('#pagoEfectivo').style.display = metodo === 'efectivo' ? 'block' : 'none';
  $('#pagoTarjeta').style.display = (metodo === 'tarjeta_credito' || metodo === 'tarjeta_debito') ? 'block' : 'none';
  if (metodo === 'efectivo') calcularVuelto();
}

function totalActualCarrito() {
  return carrito.reduce((a, c) => a + c.precio * c.cantidad, 0);
}


/**
 * Calcula y muestra el vuelto correspondiente al pago en efectivo.
 *
 * Si el monto pagado es menor al total, muestra cuánto dinero falta.
 */
export function calcularVuelto() {
  const total = totalActualCarrito();
  const pagado = desformatearMiles($('#inputMontoPagado').value) || 0;
  const vuelto = pagado - total;
  const el = $('#vueltoTexto');
  el.textContent = `Vuelto: ${money(Math.max(vuelto, 0))}`;
  el.className = 'vuelto' + (vuelto < 0 ? ' negativo' : '');
  if (vuelto < 0) el.textContent = `Falta: ${money(Math.abs(vuelto))}`;
}


/**
 * Inicializa el buscador de productos del formulario de venta.
 *
 * Filtra las variantes disponibles a medida que el usuario escribe,
 * muestra hasta ocho coincidencias y permite seleccionar una variante.
 *
 * También activa el formateo con puntos de miles del monto pagado en
 * efectivo (se hace acá, y no en abrirModalVenta, porque esta función
 * se llama una sola vez al iniciar la app, evitando así acumular
 * listeners repetidos en el input cada vez que se abre el modal).
 */
export function initBuscadorProducto() {
  attachFormateoMiles($('#inputMontoPagado'), calcularVuelto);

  const buscadorInput = $('#buscadorProducto');
  const buscadorResultados = $('#buscadorResultados');

  buscadorInput.addEventListener('input', () => {
    const q = buscadorInput.value.trim().toLowerCase();
    $('#varianteSeleccionada').value = '';
    if (!q) { buscadorResultados.classList.remove('active'); return; }

    const coincidencias = variantesIndex.filter(v => v.texto.toLowerCase().includes(q)).slice(0, 8);
    if (!coincidencias.length) {
      buscadorResultados.innerHTML = '<div class="buscador-item">Sin resultados</div>';
    } else {
      buscadorResultados.innerHTML = coincidencias.map(v => `
      <div class="buscador-item" data-id="${v.variante_id}">
        ${esc(v.texto)}<div class="sub">${esc(v.sub)}</div>
      </div>`).join('');
    }
    buscadorResultados.classList.add('active');
  });

  buscadorResultados.addEventListener('click', (e) => {
    const item = e.target.closest('.buscador-item');
    if (!item || !item.dataset.id) return;
    const v = variantesIndex.find(x => String(x.variante_id) === item.dataset.id);
    if (!v) return;
    buscadorInput.value = v.texto;
    $('#varianteSeleccionada').value = v.variante_id;
    buscadorResultados.classList.remove('active');
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.buscador-wrap')) buscadorResultados.classList.remove('active');
  });
}


/**
 * Agrega al carrito la variante seleccionada en el buscador.
 *
 * La cantidad se obtiene del campo correspondiente. Luego actualiza
 * la representación visual del carrito y limpia la búsqueda.
 */
export function agregarAlCarrito() {
  const varianteId = $('#varianteSeleccionada').value;
  if (!varianteId) { $('#msgVenta').className = 'msg error'; $('#msgVenta').textContent = 'Elegí un producto de la lista de búsqueda'; return; }

  const v = variantesIndex.find(x => String(x.variante_id) === varianteId);
  const cantidad = parseInt($('#inputCantidad').value) || 1;

  carrito.push({ variante_id: v.variante_id, nombre: v.texto, precio: v.precio, cantidad });
  renderCarrito();

  $('#buscadorProducto').value = '';
  $('#varianteSeleccionada').value = '';
  $('#msgVenta').textContent = '';
}


/**
 * Elimina del carrito el producto ubicado en la posición indicada.
 *
 * @param {number} idx - Índice del producto dentro del carrito.
 */
export function quitarDelCarrito(idx) {
  carrito.splice(idx, 1);
  renderCarrito();
}


/**
 * Actualiza la representación visual del carrito y su total.
 *
 * También recalcula el vuelto cuando el método de pago seleccionado
 * es efectivo.
 */
export function renderCarrito() {
  const cont = $('#carrito');
  if (!carrito.length) {
    cont.innerHTML = '<div class="empty">Carrito vacío. Buscá y agregá productos arriba.</div>';
  } else {
    cont.innerHTML = carrito.map((c, i) => `
      <div class="carrito-item">
        <span>${c.cantidad}× ${esc(c.nombre)}</span>
        <span>${money(c.precio * c.cantidad)} <button class="btn danger small" onclick="quitarDelCarrito(${i})">×</button></span>
      </div>`).join('');
  }
  const total = totalActualCarrito();
  $('#totalCarrito').value = money(total);
  if ($('#selectMetodoPago').value === 'efectivo') calcularVuelto();
}


/**
 * Confirma y registra una nueva venta.
 *
 * Valida que el carrito no esté vacío y, para pagos en efectivo,
 * que el monto abonado cubra el total. Para pagos con tarjeta
 * incorpora además el tipo de tarjeta seleccionado.
 *
 * @param {Function} refrescarTodo - Función utilizada para actualizar la interfaz después de registrar la venta.
 * @returns {Promise<void>}
 */
export async function confirmarVenta(refrescarTodo) {
  if (!carrito.length) { $('#msgVenta').className = 'msg error'; $('#msgVenta').textContent = 'Agregá al menos un producto'; return; }

  const metodo = $('#selectMetodoPago').value;
  const body = {
    cliente: $('#inputCliente').value || null,
    metodo_pago: metodo,
    items: carrito.map(c => ({ variante_id: c.variante_id, cantidad: c.cantidad }))
  };

  if (metodo === 'efectivo') {
    const pagado = desformatearMiles($('#inputMontoPagado').value);
    if (isNaN(pagado) || pagado < totalActualCarrito()) {
      $('#msgVenta').className = 'msg error';
      $('#msgVenta').textContent = 'Ingresá un monto pagado válido (debe cubrir el total)';
      return;
    }
    body.monto_pagado = pagado;
  }

  if (metodo === 'tarjeta_credito' || metodo === 'tarjeta_debito') {
    body.tipo_tarjeta = $('#selectTipoTarjeta').value;
  }

  const res = await apiFetch('/api/ventas', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  });

  if (res.ok) {
    $('#msgVenta').className = 'msg ok';
    $('#msgVenta').textContent = 'Venta registrada ✅';
    refrescarTodo();
    setTimeout(() => $('#modalVenta').classList.remove('active'), 700);
  } else {
    const err = await res.json();
    $('#msgVenta').className = 'msg error';
    $('#msgVenta').textContent = err.error || 'Error al registrar la venta';
  }
}