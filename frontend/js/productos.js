import { $, apiUrlInput, apiFetch } from './api.js';
import { money, esc, renderPaginacion } from './utils.js';

export let productosCache = [];
export let variantesIndex = []; // lista plana para el buscador de venta: { variante_id, texto, precio, stock }
let paginaProductos = 1;
let terminoBusquedaProductos = '';

let productosSinStockCache = [];
let paginaProductosSinStock = 1;
let terminoBusquedaSinStock = '';


/**
 * Carga y muestra los productos con stock mediante paginación.
 *
 * Permite filtrar los productos por término de búsqueda y muestra
 * sus variantes, precios y niveles de stock.
 *
 * @param {number} [page=1] - Número de página que se desea cargar.
 * @returns {Promise<void>}
 */
export async function cargarProductos(page = 1) {
  if (!apiUrlInput.value) return;

  paginaProductos = page;

  const params = new URLSearchParams({
    page,
    page_size: 10,
    con_stock: '1'
  });

  if (terminoBusquedaProductos) {
    params.set('q', terminoBusquedaProductos);
  }

  const res = await apiFetch(`/api/productos?${params.toString()}`);
  const { data, total, page_size } = await res.json();

  productosCache = data;

  $('#tablaProductos').innerHTML = data.length
    ? data.map(p => `
        <tr>
          <td>${esc(p.codigo)}</td>

          <td>${esc(p.nombre)}</td>

          <td>
            ${p.tipos_prenda ? esc(p.tipos_prenda.nombre) : '—'}
          </td>

          <td>${p.stock_actual ?? 0}</td>

          <td>
            ${(p.variantes_producto || []).length ? `
              <table class="variantes-mini">
                <thead>
                  <tr>
                    <th>Talle/Color</th>
                    <th>Pack</th>
                    <th>Código</th>
                    <th>Precio</th>
                    <th>Stock</th>
                  </tr>
                </thead>
                <tbody>
                  ${p.variantes_producto.map(v => `
                    <tr>
                      <td>${esc(v.talle) || '—'}/${esc(v.color) || '—'}</td>
                      <td>x${v.cantidad_por_unidad ?? 1}</td>
                      <td>${esc(v.codigo) || '—'}</td>
                      <td>${money(v.precio_venta)}</td>
                      <td>${v.stock_actual ?? 0}</td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            ` : '—'}
          </td>

          <td>
            <div class="row-actions">
              <button
                class="btn icon small"
                onclick="editarProducto('${p.id}')">
                ✏️
              </button>

              <button
                class="btn danger small"
                onclick="borrarProducto('${p.id}')">
                🗑
              </button>
            </div>
          </td>
        </tr>
      `).join('')
    : `
      <tr>
        <td colspan="9" class="empty">
          No hay productos que coincidan
        </td>
      </tr>
    `;

  renderPaginacion(
    'paginacionProductos',
    page,
    page_size,
    total,
    'cargarProductos'
  );
}


/**
 * Actualiza el término de búsqueda de productos y recarga la primera página.
 *
 * @param {string} texto - Texto ingresado en el buscador.
 */
export function buscarProductosLista(texto) {
  terminoBusquedaProductos = (texto || '').trim();
  cargarProductos(1);
}


/**
 * Carga y muestra los productos sin stock mediante paginación.
 *
 * Utiliza el endpoint de productos con el filtro `con_stock=0`.
 *
 * @param {number} [page=1] - Número de página que se desea cargar.
 * @returns {Promise<void>}
 */
export async function cargarProductosSinStock(page = 1) {
  if (!apiUrlInput.value) return;
  paginaProductosSinStock = page;

  const params = new URLSearchParams({ page, page_size: 10, con_stock: '0' });
  if (terminoBusquedaSinStock) params.set('q', terminoBusquedaSinStock);

  const res = await apiFetch(`/api/productos?${params.toString()}`);
  const { data, total, page_size } = await res.json();
  productosSinStockCache = data;

  $('#tablaProductosSinStock').innerHTML = data.length ? data.map(p => `
    <tr>
      <td>${esc(p.codigo)}</td>
      <td>${esc(p.nombre)}</td>
      <td>${p.tipos_prenda ? esc(p.tipos_prenda.nombre) : '—'}</td>
      <td>
        ${(p.variantes_producto || []).length ? `
          <table class="variantes-mini">
            <thead><tr><th>Talle/Color</th><th>Código</th><th>Precio</th></tr></thead>
            <tbody>
              ${p.variantes_producto.map(v => `
                 <tr><td>${esc(v.talle) || '—'}/${esc(v.color) || '—'}</td><td>${esc(v.codigo) || '—'}</td><td>${money(v.precio_venta)}</td></tr>
              `).join('')}
            </tbody>
          </table>
        ` : '—'}
      </td>
      <td>
        <div class="row-actions">
          <button class="btn icon small" onclick="editarProducto('${p.id}')">✏️ Editar</button>
          <button class="btn danger small" onclick="borrarProducto('${p.id}')">🗑 Borrar</button>
        </div>
      </td>
    </tr>`).join('') : '<tr><td colspan="5" class="empty">No hay productos sin stock</td></tr>';

  renderPaginacion('paginacionProductosSinStock', page, page_size, total, 'cargarProductosSinStock');
}


/**
 * Actualiza el término de búsqueda de productos sin stock
 * y recarga la primera página.
 *
 * @param {string} texto - Texto ingresado en el buscador.
 */
export function buscarProductosSinStock(texto) {
  terminoBusquedaSinStock = (texto || '').trim();
  cargarProductosSinStock(1);
}


/**
 * Muestra u oculta el panel de productos sin stock.
 *
 * Al abrirlo, carga la primera página de productos sin stock.
 */
export function toggleProductosSinStock() {
  const cont = $('#panelSinStock');
  const abrir = !cont.classList.contains('active');
  cont.classList.toggle('active');
  $('#btnToggleSinStock').textContent = abrir ? '▲ Ocultar productos sin stock' : '▼ Ver productos sin stock';
  if (abrir) cargarProductosSinStock(1);
}


/**
 * Carga el catálogo completo de variantes utilizado por el buscador
 * de productos del modal de venta.
 *
 * A diferencia de la lista paginada de productos, este índice contiene
 * todas las variantes disponibles en una estructura plana para facilitar
 * la búsqueda en el frontend.
 *
 * @returns {Promise<void>}
 */
export async function cargarIndiceBusqueda() {
  // Catálogo completo (liviano) para el buscador del modal de venta, independiente de la paginación
  if (!apiUrlInput.value) return;
  const res = await apiFetch('/api/productos/buscar');
  const data = await res.json();
  variantesIndex = [];
  data.forEach(p => (p.variantes_producto || []).forEach(v => {
    variantesIndex.push({
      variante_id: v.id,
      texto: `${p.nombre} — ${v.codigo} (${v.talle || ''}/${v.color || ''})`,
      sub: `Stock disponible: ${v.stock} · ${money(v.precio_venta)}`,
      precio: v.precio_venta,
      stock: v.stock
    });
  }));
}


/**
 * Carga los tipos de prenda disponibles y actualiza el selector
 * utilizado en el formulario de productos.
 *
 * @returns {Promise<void>}
 */
export async function cargarTipos() {
  if (!apiUrlInput.value) return;
  const res = await apiFetch('/api/tipos');
  const data = await res.json();
  $('#selectTipo').innerHTML = data.map(t => `<option value="${t.id}">${esc(t.nombre)} (${esc(t.prefijo)})</option>`).join('');
}


/**
 * Elimina un producto y todas sus variantes después de solicitar
 * confirmación al usuario.
 *
 * @param {number|string} id - Identificador del producto.
 * @param {Function} refrescarTodo - Función utilizada para actualizar la interfaz.
 * @returns {Promise<void>}
 */
export async function borrarProducto(id, refrescarTodo) {
  if (!confirm('¿Borrar este producto y todas sus variantes? Esta acción no se puede deshacer.')) return;
  await apiFetch(`/api/productos/${id}`, { method: 'DELETE' });
  refrescarTodo();
}


/**
 * Elimina una variante de producto después de solicitar confirmación.
 *
 * @param {number|string} id - Identificador de la variante.
 * @param {Function} refrescarTodo - Función utilizada para actualizar la interfaz.
 * @returns {Promise<void>}
 */
export async function borrarVariante(id, refrescarTodo) {
  if (!confirm('¿Borrar esta variante (talle/color)?')) return;
  await apiFetch(`/api/productos/variantes/${id}`, { method: 'DELETE' });
  refrescarTodo();
}


/**
 * Abre el modal de edición de un producto y carga sus datos actuales.
 *
 * Busca el producto tanto en la caché de productos con stock como
 * en la caché de productos sin stock.
 *
 * @param {number|string} id - Identificador del producto.
 */
export function editarProducto(id) {
  const p =
    productosCache.find(x => String(x.id) === String(id)) ||
    productosSinStockCache.find(x => String(x.id) === String(id));

  if (!p) return;

  $('#tituloModalProducto').textContent = 'Editar producto';
  $('#productoIdEdit').value = p.id;

  const form = $('#formProducto');

  form.nombre.value = p.nombre;
  form.tipo_id.value = p.tipo_id || '';

  renderVariantesEdicion(p.variantes_producto || []);

  $('#msgProducto').textContent = '';
  $('#modalProducto').classList.add('active');
}


/**
 * Abre el modal para crear un nuevo producto.
 *
 * Reinicia el formulario y agrega inicialmente una fila para cargar
 * una variante.
 */
export function abrirModalProducto() {
  $('#tituloModalProducto').textContent = 'Nuevo producto';
  $('#productoIdEdit').value = '';
  $('#formProducto').reset();
  $('#variantesList').innerHTML = '';
  agregarFilaVariante();
  $('#msgProducto').textContent = '';
  $('#modalProducto').classList.add('active');
}

// ---------- Variantes: alta (producto nuevo) vs edición (producto existente) ----------


/**
 * Agrega una fila de variante al formulario.
 *
 * La fila generada depende de si se está creando un producto nuevo
 * o agregando una variante a un producto existente.
 */
export function agregarFilaVariante() {
  const productoId = $('#productoIdEdit').value;
  const cont = $('#variantesList');

  if (productoId) {
    cont.appendChild(crearFilaVarianteNueva());
  } else {
    cont.appendChild(crearFilaVarianteCreacion());
  }
}


/**
 * Crea una fila de formulario para una variante de un producto nuevo.
 *
 * @returns {HTMLDivElement} Elemento DOM correspondiente a la fila.
 */
function crearFilaVarianteCreacion() {
  const row = document.createElement('div');
  row.className = 'variante-row';

  row.innerHTML = `
    <div class="variante-campo">
      <label>Talle</label>
      <input placeholder="Ej: M, 42, Único" class="v-talle" />
    </div>

    <div class="variante-campo">
      <label>Color</label>
      <input placeholder="Ej: Negro" class="v-color" />
    </div>

    <div class="variante-campo">
      <label>Cant. por pack</label>
      <input type="number" min="1" class="v-cantidad-por-unidad" value="1" />
    </div>

    <div class="variante-campo">
      <label>Costo</label>
      <input type="number" min="0" step="0.01" class="v-costo" placeholder="0" />
    </div>

    <div class="variante-campo">
      <label>% Ganancia</label>
      <input type="number" min="0" step="0.01" class="v-porcentaje" placeholder="30" />
    </div>

    <div class="variante-campo">
      <label>Precio venta</label>
      <input type="number" min="0" step="0.01" class="v-precio" placeholder="Auto" />
    </div>

    <div class="variante-campo">
      <label>Stock inicial</label>
      <input type="number" min="0" class="v-stock" value="0" />
    </div>

    <div class="variante-campo">
      <label>Código</label>
      <input placeholder="Auto" class="v-codigo" />
    </div>

    <div class="variante-row-actions">
      <button type="button" class="btn danger small" onclick="this.closest('.variante-row').remove()">
        ✕ Quitar
      </button>
    </div>
  `;

  return row;
}


/**
 * Renderiza las variantes existentes dentro del formulario de edición.
 *
 * @param {Array<Object>} variantes - Lista de variantes del producto.
 */
function renderVariantesEdicion(variantes) {
  const cont = $('#variantesList');
  cont.innerHTML = '';

  variantes.forEach(v => {
    cont.appendChild(crearFilaVarianteExistente(v));
  });
}


/**
 * Crea una fila de formulario para una variante existente.
 *
 * Incluye sus datos actuales y acciones para guardar o eliminar la variante.
 *
 * @param {Object} v - Datos de la variante.
 * @returns {HTMLDivElement} Elemento DOM correspondiente a la fila.
 */
function crearFilaVarianteExistente(v) {
  const row = document.createElement('div');
  row.className = 'variante-row';
  row.dataset.varianteId = v.id;

  row.innerHTML = `
    <div class="variante-campo">
      <label>Talle</label>
      <input placeholder="Ej: M, 42, Único" class="v-talle" value="${esc(v.talle)}" />
    </div>

    <div class="variante-campo">
      <label>Color</label>
      <input placeholder="Ej: Negro" class="v-color" value="${esc(v.color)}" />
    </div>

    <div class="variante-campo">
      <label>Cant. por pack</label>
      <input type="number" min="1" class="v-cantidad-por-unidad" value="${v.cantidad_por_unidad ?? 1}" />
    </div>

    <div class="variante-campo">
      <label>Costo</label>
      <input type="number" min="0" step="0.01" class="v-costo" value="${v.precio_costo ?? 0}" />
    </div>

    <div class="variante-campo">
      <label>% Ganancia</label>
      <input type="number" min="0" step="0.01" class="v-porcentaje" value="${v.porcentaje_ganancia ?? 30}" />
    </div>

    <div class="variante-campo">
      <label>Precio venta</label>
      <input type="number" min="0" step="0.01" class="v-precio" value="${v.precio_venta ?? 0}" />
    </div>

    <div class="variante-campo">
      <label>Stock actual</label>
      <input type="number" min="0" class="v-stock-actual" value="${v.stock_actual ?? 0}" data-original="${v.stock_actual ?? 0}" />
    </div>

    <div class="variante-campo">
      <label>Código</label>
      <input placeholder="Código" class="v-codigo" value="${esc(v.codigo)}" />
    </div>

    <div class="variante-row-actions">
      <button type="button" class="btn small" onclick="guardarVarianteExistente(this)">💾 Guardar</button>
      <button type="button" class="btn danger small" onclick="borrarVarianteDesdeModal(this)">🗑 Borrar</button>
    </div>
  `;

  return row;
}


/**
 * Crea una fila de formulario para agregar una nueva variante
 * a un producto existente.
 *
 * @returns {HTMLDivElement} Elemento DOM correspondiente a la fila.
 */
function crearFilaVarianteNueva() {
  const row = document.createElement('div');
  row.className = 'variante-row';

  row.innerHTML = `
    <div class="variante-campo">
      <label>Talle</label>
      <input placeholder="Ej: M, 42, Único" class="v-talle" />
    </div>

    <div class="variante-campo">
      <label>Color</label>
      <input placeholder="Ej: Negro" class="v-color" />
    </div>

    <div class="variante-campo">
      <label>Cant. por pack</label>
      <input type="number" min="1" class="v-cantidad-por-unidad" value="1" />
    </div>

    <div class="variante-campo">
      <label>Costo</label>
      <input type="number" min="0" step="0.01" class="v-costo" placeholder="0" />
    </div>

    <div class="variante-campo">
      <label>% Gcia.</label>
      <input type="number" min="0" step="0.01" class="v-porcentaje" placeholder="30" />
    </div>

    <div class="variante-campo">
      <label>Precio venta</label>
      <input type="number" min="0" step="0.01" class="v-precio" placeholder="Auto" />
    </div>

    <div class="variante-campo">
      <label>Cantidad</label>
      <input type="number" min="0" class="v-stock" value="0" />
    </div>

    <div class="variante-campo">
      <label>Código</label>
      <input placeholder="Auto" class="v-codigo" />
    </div>

    <div class="variante-row-actions">
      <button type="button" class="btn small" onclick="guardarVarianteNueva(this)">💾 Guardar</button>
      <button type="button" class="btn danger small" onclick="this.closest('.variante-row').remove()">✕ Quitar</button>
    </div>
  `;

  return row;
}


/**
 * Actualiza una variante existente.
 *
 * Guarda los datos descriptivos y comerciales de la variante y,
 * si se modificó el stock, calcula la diferencia respecto del stock
 * original y registra el ajuste mediante el endpoint correspondiente.
 *
 * El precio de venta manual solo se envía cuando se proporciona
 * un valor positivo.
 *
 * @param {HTMLButtonElement} btn - Botón desde el que se inició la operación.
 * @param {Function} [refrescarTodo] - Función opcional para actualizar la interfaz.
 * @returns {Promise<void>}
 */
export async function guardarVarianteExistente(btn, refrescarTodo) {
  const row = btn.closest('.variante-row');
  const varianteId = row.dataset.varianteId;

  const body = {
    talle: row.querySelector('.v-talle')?.value || null,
    color: row.querySelector('.v-color')?.value || null,
    codigo: row.querySelector('.v-codigo')?.value || null,
    cantidad_por_unidad:
      parseInt(
        row.querySelector('.v-cantidad-por-unidad')?.value
      ) || 1,
    precio_costo:
      parseFloat(row.querySelector('.v-costo')?.value) || 0,
    porcentaje_ganancia:
      parseFloat(row.querySelector('.v-porcentaje')?.value) || 30
  };

  const inputPrecio = row.querySelector('.v-precio');
  const precioManual = parseFloat(inputPrecio?.value);
  if (!isNaN(precioManual) && precioManual > 0) {
    body.precio_venta = precioManual;
  }


  const inputStock = row.querySelector('.v-stock-actual');

  const nuevoStock = parseInt(inputStock.value);
  const stockOriginal = parseInt(inputStock.dataset.original);

  const delta =
    (isNaN(nuevoStock) ? stockOriginal : nuevoStock) -
    stockOriginal;

  // Guardar datos de la variante
  const res = await apiFetch(
    `/api/productos/variantes/${varianteId}`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    }
  );

  // Actualizar stock si corresponde
  let resStock = { ok: true };

  if (delta !== 0) {
    resStock = await apiFetch(
      `/api/productos/variantes/${varianteId}/stock`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          cantidad: delta,
          motivo: 'Ajuste manual desde edición de producto'
        })
      }
    );
  }

  if (!res.ok || !resStock.ok) {
    $('#msgProducto').className = 'msg error';
    $('#msgProducto').textContent =
      'No se pudo actualizar la variante';
    return;
  }

  // El backend devuelve la variante actualizada
  const varianteActualizada = await res.json();

  // Actualizamos el data-original del stock
  inputStock.dataset.original =
    varianteActualizada.stock_actual;

  // Mostramos los valores realmente guardados
  row.querySelector('.v-talle').value =
    varianteActualizada.talle || '';

  row.querySelector('.v-color').value =
    varianteActualizada.color || '';

  row.querySelector('.v-cantidad-por-unidad').value =
    varianteActualizada.cantidad_por_unidad ?? 1;

  inputStock.value =
    varianteActualizada.stock_actual ?? 0;

  row.querySelector('.v-codigo').value =
    varianteActualizada.codigo || '';

  row.querySelector('.v-costo').value =
    varianteActualizada.precio_costo ?? 0;

  row.querySelector('.v-porcentaje').value =
    varianteActualizada.porcentaje_ganancia ?? 30;

  inputPrecio.value =
    varianteActualizada.precio_venta ?? 0;

  $('#msgProducto').className = 'msg ok';
  $('#msgProducto').textContent =
    'Variante actualizada ✅';

  // Actualizar la tabla principal
  if (refrescarTodo) {
    await refrescarTodo();
  }
}


/**
 * Agrega una nueva variante a un producto existente.
 *
 * Obtiene los datos de la fila del formulario, los envía al backend
 * y reemplaza la fila de edición por una fila que representa la
 * variante ya creada.
 *
 * @param {HTMLButtonElement} btn - Botón desde el que se inició la operación.
 * @param {Function} [refrescarTodo] - Función opcional para actualizar la interfaz.
 * @returns {Promise<void>}
 */
export async function guardarVarianteNueva(btn, refrescarTodo) {
  const row = btn.closest('.variante-row');
  const productoId = $('#productoIdEdit').value;

  if (!productoId) return;

  const body = {
    talle: row.querySelector('.v-talle').value || null,
    color: row.querySelector('.v-color').value || null,
    codigo: row.querySelector('.v-codigo').value || null,

    cantidad_por_unidad:
      parseInt(
        row.querySelector('.v-cantidad-por-unidad').value
      ) || 1,

    precio_costo:
      parseFloat(row.querySelector('.v-costo')?.value) || undefined,

    porcentaje_ganancia:
      parseFloat(row.querySelector('.v-porcentaje')?.value) || undefined,

    precio_venta:
      parseFloat(row.querySelector('.v-precio')?.value) || undefined,

    stock:
      parseInt(
        row.querySelector('.v-stock').value
      ) || 0
  };

  const res = await apiFetch(
    `/api/productos/${productoId}/variantes`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    }
  );

  if (res.ok) {
    const varianteCreada = await res.json();

    $('#msgProducto').className = 'msg ok';
    $('#msgProducto').textContent =
      'Variante agregada ✅';

    // Reemplazamos la fila "nueva" por una fila de variante "existente",
    // usando directamente lo que devolvió el backend — sin depender
    // de que la tabla/caché ya se haya actualizado.
    const filaExistente = crearFilaVarianteExistente(varianteCreada);
    row.replaceWith(filaExistente);

    // Refresca la tabla y el dashboard en segundo plano, sin bloquear el modal.
    if (refrescarTodo) refrescarTodo();

  } else {
    const err = await res.json().catch(() => ({}));

    $('#msgProducto').className = 'msg error';
    $('#msgProducto').textContent =
      err.error || 'No se pudo agregar la variante';
  }
}


/**
 * Elimina una variante desde el modal de edición.
 *
 * Solicita confirmación, elimina la variante mediante la API y,
 * si la operación es exitosa, quita su fila del formulario.
 *
 * @param {HTMLButtonElement} btn - Botón desde el que se inició la operación.
 * @param {Function} [refrescarTodo] - Función opcional para actualizar la interfaz.
 * @returns {Promise<void>}
 */
export async function borrarVarianteDesdeModal(btn, refrescarTodo) {
  const row = btn.closest('.variante-row');
  const varianteId = row.dataset.varianteId;

  if (!confirm('¿Borrar esta variante (talle/color)?')) {
    return;
  }

  const res = await apiFetch(
    `/api/productos/variantes/${varianteId}`,
    {
      method: 'DELETE'
    }
  );

  if (res.ok) {
    row.remove();
  }

  if (refrescarTodo) refrescarTodo();
}


/**
 * Inicializa el formulario de productos.
 *
 * Configura el envío del formulario para crear un producto nuevo
 * o actualizar uno existente. Al crear un producto, recopila además
 * las variantes cargadas en el formulario y las envía junto con
 * los datos principales del producto.
 *
 * @param {Function} onGuardado - Función ejecutada después de guardar correctamente.
 */
export function initFormProducto(onGuardado) {
  $('#formProducto').addEventListener('submit', async (e) => {
    e.preventDefault();

    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd.entries());

    // IMPORTANTE:
    // El producto NO tiene costo, porcentaje_ganancia ni precio.
    // Esa información pertenece a cada variante.

    const productoId = body.producto_id;
    delete body.producto_id;

    let res;

    if (productoId) {

      res = await apiFetch(
        `/api/productos/${productoId}`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(body)
        }
      );

    } else {

      body.variantes = Array.from(
        document.querySelectorAll('#variantesList .variante-row')
      ).map(row => ({
        talle: row.querySelector('.v-talle')?.value || null,
        color: row.querySelector('.v-color')?.value || null,

        cantidad_por_unidad:
          parseInt(
            row.querySelector('.v-cantidad-por-unidad')?.value
          ) || 1,

        precio_costo:
          parseFloat(row.querySelector('.v-costo')?.value) || undefined,

        porcentaje_ganancia:
          parseFloat(row.querySelector('.v-porcentaje')?.value) || undefined,

        precio_venta:
          parseFloat(row.querySelector('.v-precio')?.value) || undefined,

        stock:
          parseInt(row.querySelector('.v-stock')?.value) || 0,

        codigo:
          row.querySelector('.v-codigo')?.value || null,
      })).filter(v =>
        v.talle ||
        v.color ||
        v.stock ||
        v.cantidad_por_unidad
      );

      res = await apiFetch(
        '/api/productos',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(body)
        }
      );
    }

    if (res.ok) {

      $('#msgProducto').className = 'msg ok';

      $('#msgProducto').textContent =
        'Guardado ✅';

      onGuardado();

      setTimeout(
        () => cerrarModalProducto(),
        700
      );

    } else {

      const err = await res.json();

      $('#msgProducto').className = 'msg error';

      $('#msgProducto').textContent =
        err.error || 'Error al guardar';
    }
  });
}


/**
 * Cierra el modal de edición/creación de productos.
 */
function cerrarModalProducto() {
  $('#modalProducto').classList.remove('active');
}