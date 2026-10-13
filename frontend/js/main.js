import { $, apiUrlInput } from './api.js';
import {
  cargarDashboard, cargarHistorialDia,
  abrirResumenCaja, copiarResumenCaja, exportarResumenCajaPDF
} from './dashboard.js'
import {
  cargarCambios, limpiarFiltroFechaCambios, borrarCambio,
  abrirModalCambio, cambiarVentaSeleccionada, initBuscadorVentaCambio,
  initBuscadorProductoNuevoCambio, agregarProductoNuevoCambio,
  quitarProductoNuevoCambio, actualizarResumenCambio, onEditarMontoDiferencia,
  corregirCantidadDevolver, confirmarCambio, editarCambio
} from './cambios.js';
import {
  cargarProductos, cargarIndiceBusqueda, cargarTipos,
  borrarProducto, borrarVariante, editarProducto,
  abrirModalProducto, agregarFilaVariante, initFormProducto,
  buscarProductosLista, guardarVarianteExistente, guardarVarianteNueva,
  borrarVarianteDesdeModal, cargarProductosSinStock, buscarProductosSinStock,
  toggleProductosSinStock
} from './productos.js';
import {
  cargarVentas, limpiarFiltroFechaVentas, marcarDevolucion, borrarVenta,
  abrirEditarVenta, guardarEdicionVenta, abrirModalVenta, onCambioMetodoPago,
  calcularVuelto, initBuscadorProducto, agregarAlCarrito, quitarDelCarrito,
  confirmarVenta
} from './ventas.js';
import {
  cargarTiposConfig, editarTipo, borrarTipo,
  initFormTipo, subirBackupSupabase
} from './config.js';
import { hoyISO } from './utils.js';


/**
 * Cierra un modal eliminando su clase de estado activo.
 *
 * @param {string} id - ID del elemento que representa el modal.
 */
function cerrarModal(id) { $('#' + id).classList.remove('active'); }

// ---------- Refrescos combinados ----------


/**
 * Actualiza el panel de productos sin stock si actualmente está visible.
 */
function refrescarPanelSinStockSiAbierto() {
  if ($('#panelSinStock').classList.contains('active')) cargarProductosSinStock();
}


/**
 * Actualiza los datos de la aplicación después de una operación de venta
 * o de cambio/devolución que pueda afectar ventas, stock y caja.
 *
 * Recarga las ventas, productos, índice de búsqueda, dashboard y cambios.
 * También actualiza el panel de productos sin stock si está visible.
 *
 * @returns {Promise<void>}
 */
async function refrescarTrasVenta() {
  await Promise.all([
    cargarVentas(),
    cargarProductos(),
    cargarIndiceBusqueda(),
    cargarDashboard(),
    cargarCambios(),
  ]);
  refrescarPanelSinStockSiAbierto();
}


/**
 * Actualiza los datos relacionados con productos después de una operación
 * de creación, edición o eliminación.
 *
 * Recarga los productos, el índice de búsqueda y el dashboard.
 * También actualiza el panel de productos sin stock si está visible.
 *
 * @returns {Promise<void>}
 */
async function refrescarTrasProducto() {
  await Promise.all([
    cargarProductos(),
    cargarIndiceBusqueda(),
    cargarDashboard(),
  ]);
  refrescarPanelSinStockSiAbierto();
}


/**
 * Carga los datos iniciales de todos los módulos de la aplicación.
 *
 * No realiza la carga si no hay una URL de API configurada.
 */
function cargarTodo() {
  if (!apiUrlInput.value) return;
  cargarDashboard();
  cargarProductos();
  cargarVentas();
  cargarCambios();
  cargarTipos();
  cargarIndiceBusqueda();
  cargarTiposConfig();
}


// ---------- Navegación de pestañas ----------


document.querySelectorAll('nav button[data-tab]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('section').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    $('#' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'dashboard') cargarDashboard();
    if (btn.dataset.tab === 'productos') cargarProductos();
    if (btn.dataset.tab === 'ventas') cargarVentas();
    if (btn.dataset.tab === 'cambios') cargarCambios();
    if (btn.dataset.tab === 'configuracion') { cargarTiposConfig(); }
  });
});

$('#fechaHistorial').value = hoyISO();
$('#fechaHistorial').addEventListener('change', cargarHistorialDia);
$('#fechaVentas').addEventListener('change', () => cargarVentas(1));
$('#fechaCambios').addEventListener('change', () => cargarCambios(1));

let debounceBusquedaProductos;
$('#buscadorProductosLista').addEventListener('input', (e) => {
  clearTimeout(debounceBusquedaProductos);
  const valor = e.target.value;
  debounceBusquedaProductos = setTimeout(() => buscarProductosLista(valor), 300);
});

let debounceBusquedaSinStock;
$('#buscadorProductosSinStock').addEventListener('input', (e) => {
  clearTimeout(debounceBusquedaSinStock);
  const valor = e.target.value;
  debounceBusquedaSinStock = setTimeout(() => buscarProductosSinStock(valor), 300);
});

// ---------- Inicialización de formularios con listeners propios ----------

initFormProducto(refrescarTrasProducto);
initFormTipo();
initBuscadorProducto();
initBuscadorVentaCambio();
initBuscadorProductoNuevoCambio();

// ---------- Exposición a window para los onclick inline del HTML ----------

Object.assign(window, {
  cerrarModal,
  cargarProductos,
  cargarVentas,

  // resumen de caja
  abrirResumenCaja,
  copiarResumenCaja,
  exportarResumenCajaPDF,

  // cambios
  cargarCambios,
  limpiarFiltroFechaCambios,
  borrarCambio: (id) => borrarCambio(id, refrescarTrasVenta),
  abrirModalCambio,
  cambiarVentaSeleccionada,
  editarCambio,
  agregarProductoNuevoCambio,
  quitarProductoNuevoCambio,
  actualizarResumenCambio,
  onEditarMontoDiferencia,
  corregirCantidadDevolver,
  confirmarCambio: () => confirmarCambio(refrescarTrasVenta),

  // productos
  abrirModalProducto,
  agregarFilaVariante,
  editarProducto,
  borrarProducto: (id) => borrarProducto(id, refrescarTrasProducto),
  borrarVariante: (id) => borrarVariante(id, refrescarTrasProducto),
  guardarVarianteExistente: (btn) => guardarVarianteExistente(btn, refrescarTrasProducto),
  guardarVarianteNueva: (btn) => guardarVarianteNueva(btn, refrescarTrasProducto),
  borrarVarianteDesdeModal: (btn) => borrarVarianteDesdeModal(btn, refrescarTrasProducto),
  toggleProductosSinStock,

  // ventas / carrito
  abrirModalVenta,
  onCambioMetodoPago,
  calcularVuelto,
  agregarAlCarrito,
  quitarDelCarrito,
  confirmarVenta: () => confirmarVenta(refrescarTrasVenta),
  limpiarFiltroFechaVentas,
  marcarDevolucion: (id) => marcarDevolucion(id, refrescarTrasVenta),
  borrarVenta: (id) => borrarVenta(id, refrescarTrasVenta),
  abrirEditarVenta,
  guardarEdicionVenta: () => guardarEdicionVenta(cargarDashboard),

  // configuración / tipos
  editarTipo,
  borrarTipo,
  subirBackupSupabase,
});

cargarTodo();