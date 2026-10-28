import { $, apiUrlInput, apiFetch } from './api.js';
import { money, esc, desformatearMiles, attachFormateoMiles, renderPaginacion, parseFechaUTC, formatoFechaHora } from './utils.js';
import { variantesIndex } from './productos.js';
import { botonNota, abrirModalNota } from './nota-modal.js';

const NOMBRES_METODO_PAGO = {
    efectivo: 'Efectivo',
    tarjeta_debito: 'Tarjeta débito',
    tarjeta_credito: 'Tarjeta crédito',
    transferencia: 'Transferencia',
    otro: 'Otro'
};

let paginaCambios = 1;
let cambiosCache = [];

// ---------- Listado ----------

/**
 * Abre el modal para ver o editar la nota (observaciones) de un cambio.
 * Usa un endpoint aparte que no rehace el cambio ni toca el stock.
 *
 * @param {number|string} id - Identificador del cambio.
 */
export function abrirNotaCambio(id) {
    const c = cambiosCache.find(x => String(x.id) === String(id));
    if (!c) return;

    abrirModalNota(`Nota del cambio ${c.codigo || ''}`, c.observaciones, async (observaciones) => {
        const res = await apiFetch(`/api/cambios/${c.id}/observaciones`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ observaciones }),
        });
        if (res.ok) cargarCambios(paginaCambios);
        return res;
    });
}

/**
 * Carga y muestra el listado paginado de cambios.
 *
 * Permite filtrar los cambios por fecha y actualiza tanto la tabla como
 * los controles de paginación.
 *
 * @param {number} [page=1] - Número de página que se desea cargar.
 * @returns {Promise<void>}
 */
export async function cargarCambios(page = 1) {
    if (!apiUrlInput.value) return;
    paginaCambios = page;
    const fecha = $('#fechaCambios').value;
    const params = new URLSearchParams({ page, page_size: 20 });
    if (fecha) params.set('fecha', fecha);

    const res = await apiFetch('/api/cambios?' + params.toString());
    const { data, total, page_size } = await res.json();
    cambiosCache = data;

    $('#tablaCambios').innerHTML = data.length ? data.map(c => {
        const devueltos = c.items.filter(i => i.tipo === 'devuelto');
        const nuevos = c.items.filter(i => i.tipo === 'nuevo');

        const listaDevueltos = devueltos.map(i =>
            `${i.cantidad}× ${esc(i.producto_nombre)} (${esc(i.talle) || '—'}/${esc(i.color) || '—'})`
        ).join('<br>') || '—';

        const listaNuevos = nuevos.map(i =>
            `${i.cantidad}× ${esc(i.producto_nombre)} (${esc(i.talle) || '—'}/${esc(i.color) || '—'})`
        ).join('<br>') || '—';

        const signoGanancia = c.ganancia > 0 ? '+' : (c.ganancia < 0 ? '−' : '');
        const claseGanancia = c.ganancia > 0 ? 'monto-positivo' : (c.ganancia < 0 ? 'monto-negativo' : '');
        const gananciaTexto = c.ganancia
            ? `<span class="${claseGanancia}">${signoGanancia}${money(Math.abs(c.ganancia))}</span>`
            : money(0);

        const signoIngreso = c.monto_diferencia > 0 ? '+' : (c.monto_diferencia < 0 ? '−' : '');
        const claseIngreso = c.monto_diferencia > 0 ? 'monto-positivo' : (c.monto_diferencia < 0 ? 'monto-negativo' : '');
        const ingresoTexto = c.monto_diferencia
            ? `<span class="${claseIngreso}">${signoIngreso}${money(Math.abs(c.monto_diferencia))}</span>`
            : 'Sin movimiento';
        const metodoTexto = c.metodo_pago ? (NOMBRES_METODO_PAGO[c.metodo_pago] || esc(c.metodo_pago)) : '—';

        return `
      <tr>
        <td>${formatoFechaHora(parseFechaUTC(c.fecha))}</td>
        <td>${esc(c.codigo) || '—'}</td>
        <td>${esc(c.venta_codigo) || '—'}${c.venta_cliente ? `<br><span class="sub" style="color:var(--muted); font-size:.76rem">${esc(c.venta_cliente)}</span>` : ''}</td>
        <td>${listaDevueltos}</td>
        <td>${listaNuevos}</td>
        <td>${gananciaTexto}</td>
        <td>${ingresoTexto}</td>
        <td>${metodoTexto}</td>
        <td>
          <div class="row-actions">
            <button class="btn icon small" onclick="editarCambio('${c.id}')" title="Editar">✏️</button>
            <button class="btn danger small" onclick="borrarCambio('${c.id}')" title="Borrar">🗑</button>
          </div>
          ${botonNota(c.observaciones, `abrirNotaCambio('${c.id}')`)}
        </td>
      </tr>`;
    }).join('') : '<tr><td colspan="9" class="empty">No hay cambios para este filtro</td></tr>';

    renderPaginacion('paginacionCambios', page, page_size, total, 'cargarCambios');
}


/**
 * Limpia el filtro de fecha y vuelve a cargar el listado desde la primera página.
 *
 * @returns {void}
 */
export function limpiarFiltroFechaCambios() {
    $('#fechaCambios').value = '';
    cargarCambios(1);
}


/**
 * Elimina un cambio y solicita al backend que revierta sus efectos.
 *
 * La eliminación del cambio revierte el stock y los totales asociados
 * a la venta según las reglas implementadas por el backend.
 *
 * @param {number|string} cambioId - Identificador del cambio a eliminar.
 * @param {Function} [refrescarTodo] - Función opcional para actualizar
 *        la interfaz después de eliminar el cambio.
 * @returns {Promise<void>}
 */
export async function borrarCambio(cambioId, refrescarTodo) {
    if (!confirm('¿Borrar este cambio? Se revierte el stock y se descuenta de los totales de la venta.')) return;
    const res = await apiFetch(`/api/cambios/${cambioId}`, { method: 'DELETE' });
    if (res.ok) {
        if (refrescarTodo) refrescarTodo();
    } else {
        alert('No se pudo borrar el cambio');
    }
}

/**
 * Genera una representación textual resumida de los cambios de una venta.
 *
 * Se separan los productos devueltos de los productos nuevos y se muestra
 * la diferencia monetaria junto con el método de pago cuando corresponde.
 *
 * @param {Array<Object>} cambios - Lista de cambios registrados.
 * @returns {string[]} Líneas de texto con el resumen de cada cambio.
 */
export function generarLineasCambios(cambios) {
    if (!cambios.length) return ['Sin cambios registrados'];

    return cambios.map(c => {
        const devueltos = (c.items || []).filter(i => i.tipo === 'devuelto')
            .map(i => `${i.cantidad}x ${i.producto_nombre}`).join(', ') || '—';
        const nuevos = (c.items || []).filter(i => i.tipo === 'nuevo')
            .map(i => `${i.cantidad}x ${i.producto_nombre}`).join(', ') || '—';
        const metodo = c.metodo_pago ? ` (${NOMBRES_METODO_PAGO[c.metodo_pago] || c.metodo_pago})` : '';
        const signo = c.monto_diferencia > 0 ? '+' : (c.monto_diferencia < 0 ? '-' : '');
        const monto = c.monto_diferencia ? `${signo}${money(Math.abs(c.monto_diferencia))}${metodo}` : 'Sin movimiento';

        return `${c.codigo || '—'} - Venta ${c.venta_codigo || '—'} - Devuelto: ${devueltos} - Nuevo: ${nuevos} - ${monto}`;
    });
}

// ---------- Modal: registrar / editar cambio ----------

let ventaSeleccionada = null;
let itemsDisponibles = [];
let itemsNuevos = [];
let cambioEditandoId = null;
// Al editar un cambio, unidades que ese cambio ya había sacado del stock,
// por variante. El backend las repone antes de validar, así que cuentan
// como disponibles para este mismo cambio.
let reservadoPorEsteCambio = {};

/**
 * Abre y reinicia el modal para registrar un nuevo cambio.
 *
 * Restablece la venta seleccionada, los productos devueltos y los productos
 * nuevos antes de mostrar el formulario.
 *
 * @returns {void}
 */
export function abrirModalCambio() {
    ventaSeleccionada = null;
    itemsDisponibles = [];
    itemsNuevos = [];
    cambioEditandoId = null;
    reservadoPorEsteCambio = {};

    $('#buscadorVentaCambio').value = '';
    $('#buscadorResultadosVentaCambio').classList.remove('active');
    $('#pasoBuscarVentaCambio').style.display = 'block';
    $('#detalleCambio').style.display = 'none';
    $('#btnConfirmarCambio').disabled = true;
    $('#btnConfirmarCambio').textContent = 'Confirmar cambio';
    $('#tituloModalCambio').textContent = 'Registrar cambio';
    $('#inputObservacionesCambio').value = '';
    $('#msgCambio').textContent = '';
    $('#msgCambio').className = 'msg';
    delete $('#inputMontoDiferenciaCambio').dataset.editadoManual;

    $('#modalCambio').classList.add('active');
}


/**
 * Restablece la venta seleccionada para permitir elegir otra venta.
 *
 * @returns {void}
 */
export function cambiarVentaSeleccionada() {
    ventaSeleccionada = null;
    itemsDisponibles = [];
    itemsNuevos = [];
    $('#buscadorVentaCambio').value = '';
    $('#pasoBuscarVentaCambio').style.display = 'block';
    $('#detalleCambio').style.display = 'none';
    $('#btnConfirmarCambio').disabled = true;
}

/**
 * Inicializa el buscador de ventas utilizado para registrar o editar cambios.
 *
 * La búsqueda se realiza contra el backend después de 300 ms sin nuevas
 * pulsaciones para evitar enviar una solicitud por cada tecla ingresada.
 *
 * También activa el formateo con puntos de miles del monto de diferencia
 * del cambio (se hace acá, y no en abrirModalCambio, porque esta función
 * se llama una sola vez al iniciar la app).
 *
 * @returns {void}
 */
export function initBuscadorVentaCambio() {
    attachFormateoMiles($('#inputMontoDiferenciaCambio'), onEditarMontoDiferencia);

    const input = $('#buscadorVentaCambio');
    const resultados = $('#buscadorResultadosVentaCambio');
    let debounce;

    input.addEventListener('input', () => {
        clearTimeout(debounce);
        const q = input.value.trim();
        if (!q) { resultados.classList.remove('active'); return; }

        debounce = setTimeout(async () => {
            const res = await apiFetch(`/api/ventas/buscar?q=${encodeURIComponent(q)}`);
            const data = await res.json();

            if (!data.length) {
                resultados.innerHTML = '<div class="buscador-item">Sin resultados</div>';
            } else {
                resultados.innerHTML = data.map(v => `
          <div class="buscador-item" data-id="${v.id}">
            ${esc(v.codigo) || '—'} — ${esc(v.cliente) || 'Sin cliente'}
            <div class="sub">${money(v.total)} · ${(v.venta_items || []).length} ítem(s)</div>
          </div>
        `).join('');
            }
            resultados.classList.add('active');
        }, 300);
    });

    resultados.addEventListener('click', async (e) => {
        const item = e.target.closest('.buscador-item');
        if (!item || !item.dataset.id) return;
        resultados.classList.remove('active');
        await seleccionarVentaCambio(item.dataset.id);
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.buscador-wrap')) resultados.classList.remove('active');
    });
}

async function seleccionarVentaCambio(ventaId) {
    const res = await apiFetch(`/api/cambios/venta/${ventaId}/disponible`);
    if (!res.ok) {
        $('#msgCambio').className = 'msg error';
        $('#msgCambio').textContent = 'No se pudo cargar la venta';
        return;
    }
    const { venta, items } = await res.json();

    ventaSeleccionada = venta;
    itemsDisponibles = items;
    itemsNuevos = [];

    $('#ventaCambioCodigo').textContent = venta.codigo || `Venta #${venta.id}`;
    $('#ventaCambioCliente').textContent = venta.cliente ? `· ${venta.cliente}` : '';

    renderItemsDevolver();
    renderListaNuevos();
    actualizarResumenCambio();

    $('#pasoBuscarVentaCambio').style.display = 'none';
    $('#detalleCambio').style.display = 'block';
    $('#btnConfirmarCambio').disabled = false;
}

/**
 * Renderiza las variantes de la venta que todavía tienen unidades
 * disponibles para devolver.
 *
 * Las variantes sin unidades disponibles no se muestran.
 *
 * @returns {void}
 */
function renderItemsDevolver() {
    const cont = $('#itemsDevolverCambio');
    const conDisponible = itemsDisponibles.filter(i => i.disponible > 0);

    if (!conDisponible.length) {
        cont.innerHTML = '<div class="empty">No quedan ítems disponibles para devolver en esta venta.</div>';
        return;
    }

    cont.innerHTML = conDisponible.map(i => `
    <div class="item-devolver-row">
      <div class="info">
        <strong>${esc(i.producto_nombre)}</strong> — ${esc(i.talle) || '—'}/${esc(i.color) || '—'}
        <div class="disponible">Disponible para devolver: ${i.disponible} · ${money(i.precio_unitario)} c/u</div>
      </div>
      <input
        type="number"
        min="0"
        max="${i.disponible}"
        value="0"
        data-variante-id="${i.variante_id}"
        class="input-devolver-cantidad"
        oninput="corregirCantidadDevolver(this); actualizarResumenCambio()"
      />
    </div>
  `).join('');
}

/**
 * Corrige en el propio input la cantidad a devolver si supera lo
 * disponible, y muestra un aviso breve. El HTML `max` no bloquea lo que
 * se tipea a mano, solo las flechitas del input; sin esto, el número
 * que se ve en pantalla podía no coincidir con el que realmente se
 * usaba para calcular el cambio (que ya se recortaba en
 * cantidadesADevolver()).
 *
 * @param {HTMLInputElement} input - El input de cantidad a devolver.
 * @returns {void}
 */
export function corregirCantidadDevolver(input) {
    const max = parseInt(input.max);
    const valor = parseInt(input.value) || 0;
    if (valor > max) {
        input.value = max;
        $('#msgCambio').className = 'msg error';
        $('#msgCambio').textContent = `Solo hay ${max} unidad(es) disponible(s) para devolver de ese producto`;
    } else if (valor < 0) {
        input.value = 0;
    }
}

/**
 * Obtiene las cantidades de productos seleccionadas para devolución.
 *
 * Las cantidades se normalizan para impedir valores negativos o superiores
 * a la cantidad disponible para devolver.
 *
 * @returns {Array<{variante_id: number, cantidad: number}>}
 *          Variantes seleccionadas y sus cantidades a devolver.
 */
function cantidadesADevolver() {
    return Array.from(document.querySelectorAll('.input-devolver-cantidad'))
        .map(input => ({
            variante_id: parseInt(input.dataset.varianteId),
            cantidad: Math.max(0, Math.min(parseInt(input.value) || 0, parseInt(input.max)))
        }))
        .filter(x => x.cantidad > 0);
}

export function initBuscadorProductoNuevoCambio() {
    const input = $('#buscadorProductoNuevoCambio');
    const resultados = $('#buscadorResultadosNuevoCambio');

    input.addEventListener('input', () => {
        const q = input.value.trim().toLowerCase();
        $('#varianteNuevaSeleccionadaCambio').value = '';
        if (!q) { resultados.classList.remove('active'); return; }

        const coincidencias = variantesIndex.filter(v => v.texto.toLowerCase().includes(q)).slice(0, 8);
        resultados.innerHTML = coincidencias.length
            ? coincidencias.map(v => `
          <div class="buscador-item" data-id="${v.variante_id}">
            ${esc(v.texto)}<div class="sub">${esc(v.sub)}</div>
          </div>`).join('')
            : '<div class="buscador-item">Sin resultados</div>';
        resultados.classList.add('active');
    });

    resultados.addEventListener('click', (e) => {
        const item = e.target.closest('.buscador-item');
        if (!item || !item.dataset.id) return;
        const v = variantesIndex.find(x => String(x.variante_id) === item.dataset.id);
        if (!v) return;
        input.value = v.texto;
        $('#varianteNuevaSeleccionadaCambio').value = v.variante_id;
        resultados.classList.remove('active');
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.buscador-wrap')) resultados.classList.remove('active');
    });
}

export function agregarProductoNuevoCambio() {
    const varianteId = $('#varianteNuevaSeleccionadaCambio').value;
    if (!varianteId) {
        $('#msgCambio').className = 'msg error';
        $('#msgCambio').textContent = 'Elegí un producto de la lista de búsqueda';
        return;
    }

    const v = variantesIndex.find(x => String(x.variante_id) === varianteId);
    const cantidad = parseInt($('#inputCantidadNuevoCambio').value) || 1;
    if (cantidad < 1) {
        $('#msgCambio').className = 'msg error';
        $('#msgCambio').textContent = 'La cantidad tiene que ser al menos 1';
        return;
    }

    // Si la prenda ya está en la lista, se suma a esa línea en vez de agregar otra.
    const existente = itemsNuevos.find(c => c.variante_id === v.variante_id);
    const yaAgregado = existente ? existente.cantidad : 0;
    const disponible = v.stock + (reservadoPorEsteCambio[v.variante_id] || 0);
    if (yaAgregado + cantidad > disponible) {
        $('#msgCambio').className = 'msg error';
        $('#msgCambio').textContent = yaAgregado
            ? `Solo hay ${disponible} unidad(es) disponibles y ya agregaste ${yaAgregado}`
            : `Solo hay ${disponible} unidad(es) disponibles`;
        return;
    }

    if (existente) {
        existente.cantidad += cantidad;
    } else {
        itemsNuevos.push({ variante_id: v.variante_id, texto: v.texto, precio: v.precio, cantidad });
    }
    renderListaNuevos();
    actualizarResumenCambio();

    $('#buscadorProductoNuevoCambio').value = '';
    $('#varianteNuevaSeleccionadaCambio').value = '';
    $('#inputCantidadNuevoCambio').value = 1;
    $('#msgCambio').textContent = '';
}

export function quitarProductoNuevoCambio(idx) {
    itemsNuevos.splice(idx, 1);
    renderListaNuevos();
    actualizarResumenCambio();
}

function renderListaNuevos() {
    const cont = $('#listaNuevosCambio');
    if (!itemsNuevos.length) {
        cont.innerHTML = '<div class="empty">Sin productos nuevos agregados.</div>';
        return;
    }
    cont.innerHTML = itemsNuevos.map((c, i) => `
    <div class="carrito-item">
      <span>${c.cantidad}x ${esc(c.texto)}</span>
      <span>${money(c.precio * c.cantidad)} <button class="btn danger small" onclick="quitarProductoNuevoCambio(${i})">×</button></span>
    </div>`).join('');
}


/**
 * Actualiza el resumen monetario del cambio.
 *
 * Calcula el valor de los productos devueltos y de los productos nuevos,
 * determina la diferencia entre ambos importes y actualiza la interfaz
 * según corresponda:
 *
 * - diferencia positiva: el cliente debe pagar;
 * - diferencia negativa: se devuelve dinero al cliente;
 * - diferencia cero: no existe movimiento de dinero.
 *
 * @returns {void}
 */
export function actualizarResumenCambio() {
    const devolver = cantidadesADevolver();

    const totalDevuelto = devolver.reduce((acc, d) => {
        const info = itemsDisponibles.find(i => i.variante_id === d.variante_id);
        return acc + (info ? info.precio_unitario * d.cantidad : 0);
    }, 0);

    const totalNuevo = itemsNuevos.reduce((acc, i) => acc + i.precio * i.cantidad, 0);
    const diferencia = totalNuevo - totalDevuelto;

    $('#totalDevueltoCambio').textContent = money(totalDevuelto);
    $('#totalNuevoCambio').textContent = money(totalNuevo);

    const bloquePago = $('#pagoDiferenciaCambio');
    const inputMonto = $('#inputMontoDiferenciaCambio');
    const labelTipo = $('#labelTipoMontoCambio');
    const etiqueta = $('#etiquetaDiferenciaCambio');
    const textoMonto = $('#montoDiferenciaTexto');

    if (diferencia === 0) {
        etiqueta.textContent = 'Diferencia';
        textoMonto.textContent = '$0';
        textoMonto.className = '';
        bloquePago.style.display = 'none';
    } else if (diferencia > 0) {
        etiqueta.textContent = 'Cliente debe pagar';
        textoMonto.textContent = money(diferencia);
        textoMonto.className = 'monto-positivo';
        labelTipo.textContent = '(ingresa)';
        bloquePago.style.display = 'grid';
        if (!inputMonto.dataset.editadoManual) inputMonto.value = Math.round(diferencia).toLocaleString('es-AR');
    } else {
        etiqueta.textContent = 'Se le devuelve al cliente';
        textoMonto.textContent = money(Math.abs(diferencia));
        textoMonto.className = 'monto-negativo';
        labelTipo.textContent = '(sale)';
        bloquePago.style.display = 'grid';
        if (!inputMonto.dataset.editadoManual) inputMonto.value = Math.round(Math.abs(diferencia)).toLocaleString('es-AR');
    }

    if (diferencia === 0) {
        delete inputMonto.dataset.editadoManual;
    }
}

export function onEditarMontoDiferencia() {
    $('#inputMontoDiferenciaCambio').dataset.editadoManual = '1';
}


/**
 * Carga un cambio existente y prepara el modal para su edición.
 *
 * Obtiene el cambio y las cantidades disponibles de la venta asociada,
 * reconstruye los productos devueltos y nuevos y carga los datos
 * monetarios y de observaciones en el formulario.
 *
 * @param {number|string} cambioId - Identificador del cambio a editar.
 * @returns {Promise<void>}
 */
export async function editarCambio(cambioId) {
    const res = await apiFetch(`/api/cambios/${cambioId}`);
    if (!res.ok) {
        alert('No se pudo cargar el cambio');
        return;
    }
    const cambio = await res.json();

    cambioEditandoId = cambio.id;
    itemsNuevos = [];

    const resDisp = await apiFetch(`/api/cambios/venta/${cambio.venta_id}/disponible?excluir_cambio_id=${cambio.id}`);
    const { venta, items } = await resDisp.json();

    ventaSeleccionada = venta;
    itemsDisponibles = items;

    $('#ventaCambioCodigo').textContent = venta.codigo || `Venta #${venta.id}`;
    $('#ventaCambioCliente').textContent = venta.cliente ? `· ${venta.cliente}` : '';

    renderItemsDevolver();

    const devueltosDeEsteCambio = cambio.items.filter(i => i.tipo === 'devuelto');
    devueltosDeEsteCambio.forEach(d => {
        const input = document.querySelector(`.input-devolver-cantidad[data-variante-id="${d.variante_id}"]`);
        if (input) input.value = d.cantidad;
    });

    const nuevosDeEsteCambio = cambio.items.filter(i => i.tipo === 'nuevo');
    reservadoPorEsteCambio = {};
    nuevosDeEsteCambio.forEach(i => {
        reservadoPorEsteCambio[i.variante_id] = (reservadoPorEsteCambio[i.variante_id] || 0) + i.cantidad;
    });
    itemsNuevos = nuevosDeEsteCambio.map(i => ({
        variante_id: i.variante_id,
        texto: `${i.producto_nombre} — ${i.var_codigo} (${i.talle || ''}/${i.color || ''})`,
        precio: i.precio_unitario,
        cantidad: i.cantidad
    }));
    renderListaNuevos();

    if (cambio.monto_diferencia) {
        $('#inputMontoDiferenciaCambio').value = Math.round(Math.abs(cambio.monto_diferencia)).toLocaleString('es-AR');
        $('#inputMontoDiferenciaCambio').dataset.editadoManual = '1';
        if (cambio.metodo_pago) $('#selectMetodoPagoCambio').value = cambio.metodo_pago;
    } else {
        delete $('#inputMontoDiferenciaCambio').dataset.editadoManual;
    }
    $('#inputObservacionesCambio').value = cambio.observaciones || '';

    actualizarResumenCambio();

    $('#tituloModalCambio').textContent = `Editar cambio ${cambio.codigo || ''}`;
    $('#btnConfirmarCambio').textContent = 'Guardar cambios';
    $('#pasoBuscarVentaCambio').style.display = 'none';
    $('#detalleCambio').style.display = 'block';
    $('#btnConfirmarCambio').disabled = false;

    $('#modalCambio').classList.add('active');
}


/**
 * Valida y guarda un cambio nuevo o las modificaciones de un cambio existente.
 *
 * Calcula la diferencia entre los productos nuevos y los devueltos y,
 * cuando existe una diferencia monetaria, obtiene el monto y el método
 * de pago correspondientes.
 *
 * La operación se envía al backend mediante POST para un cambio nuevo
 * o PATCH cuando se está editando uno existente.
 *
 * @param {Function} [refrescarTodo] - Función opcional para actualizar
 *        la interfaz después de guardar correctamente.
 * @returns {Promise<void>}
 */
export async function confirmarCambio(refrescarTodo) {
    if (!ventaSeleccionada) return;

    const devolver = cantidadesADevolver();
    const nuevos = itemsNuevos.map(i => ({ variante_id: i.variante_id, cantidad: i.cantidad }));

    if (!devolver.length && !nuevos.length) {
        $('#msgCambio').className = 'msg error';
        $('#msgCambio').textContent = 'Agregá al menos un producto devuelto o nuevo';
        return;
    }

    const totalDevuelto = devolver.reduce((acc, d) => {
        const info = itemsDisponibles.find(i => i.variante_id === d.variante_id);
        return acc + (info ? info.precio_unitario * d.cantidad : 0);
    }, 0);
    const totalNuevo = itemsNuevos.reduce((acc, i) => acc + i.precio * i.cantidad, 0);
    const diferenciaCalculada = totalNuevo - totalDevuelto;

    let montoDiferencia = 0;
    let metodoPago = null;

    if (diferenciaCalculada !== 0) {
        const montoIngresado = desformatearMiles($('#inputMontoDiferenciaCambio').value);
        if (isNaN(montoIngresado) || montoIngresado < 0) {
            $('#msgCambio').className = 'msg error';
            $('#msgCambio').textContent = 'Ingresá un monto válido';
            return;
        }
        montoDiferencia = diferenciaCalculada > 0 ? montoIngresado : -montoIngresado;
        metodoPago = $('#selectMetodoPagoCambio').value;
    }

    const body = {
        venta_id: ventaSeleccionada.id,
        items_devueltos: devolver,
        items_nuevos: nuevos,
        monto_diferencia: montoDiferencia,
        metodo_pago: metodoPago,
        observaciones: $('#inputObservacionesCambio').value || ''
    };

    const url = cambioEditandoId ? `/api/cambios/${cambioEditandoId}` : '/api/cambios';
    const metodo = cambioEditandoId ? 'PATCH' : 'POST';

    const res = await apiFetch(url, {
        method: metodo,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });

    if (res.ok) {
        $('#msgCambio').className = 'msg ok';
        $('#msgCambio').textContent = cambioEditandoId ? 'Cambio actualizado ✅' : 'Cambio registrado ✅';
        if (refrescarTodo) refrescarTodo();
        setTimeout(() => $('#modalCambio').classList.remove('active'), 700);
    } else {
        const err = await res.json().catch(() => ({}));
        $('#msgCambio').className = 'msg error';
        $('#msgCambio').textContent = err.error || (cambioEditandoId ? 'Error al actualizar el cambio' : 'Error al registrar el cambio');
    }
}