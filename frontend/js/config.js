import { $, apiUrlInput, apiFetch } from './api.js';
import { cargarTipos } from './productos.js';
import { esc, hoyISO } from './utils.js';

// ---------- Tipos de prenda ----------

/**
 * Carga y muestra los tipos de prenda configurados.
 *
 * Cada tipo permite editar su nombre y prefijo o eliminarlo.
 *
 * @returns {Promise<void>}
 */
export async function cargarTiposConfig() {
  if (!apiUrlInput.value) return;
  const res = await apiFetch('/api/tipos');
  const data = await res.json();

  $('#listaTipos').innerHTML = data.length ? data.map(t => `
    <div class="tipo-row">
      <input value="${esc(t.nombre)}" onchange="editarTipo('${t.id}', 'nombre', this.value)" />
      <input class="prefijo-input" value="${esc(t.prefijo)}" maxlength="4" onchange="editarTipo('${t.id}', 'prefijo', this.value)" />
      <button type="button" class="btn danger small" onclick="borrarTipo('${t.id}')">🗑</button>
    </div>`).join('') : '<div class="empty">No hay tipos de prenda cargados</div>';
}


/**
 * Actualiza un campo de un tipo de prenda y refresca los listados asociados.
 *
 * @param {number|string} id - Identificador del tipo de prenda.
 * @param {string} campo - Campo que se desea modificar.
 * @param {string} valor - Nuevo valor del campo.
 * @returns {Promise<void>}
 */
export async function editarTipo(id, campo, valor) {
  if (!valor) return;
  await apiFetch(`/api/tipos/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ [campo]: valor })
  });
  cargarTiposConfig();
  cargarTipos(); // refresca el select del modal de productos
}


/**
 * Elimina un tipo de prenda y actualiza los listados de configuración y productos.
 *
 * Los productos que utilizaban el tipo quedan sin tipo asignado.
 *
 * @param {number|string} id - Identificador del tipo de prenda.
 * @returns {Promise<void>}
 */
export async function borrarTipo(id) {
  if (!confirm('¿Borrar este tipo de prenda? Los productos que lo usaban quedarán sin tipo asignado.')) return;
  await apiFetch(`/api/tipos/${id}`, { method: 'DELETE' });
  cargarTiposConfig();
  cargarTipos();
}


/**
 * Inicializa el formulario para crear un nuevo tipo de prenda.
 *
 * Valida que se hayan ingresado nombre y prefijo y envía los datos
 * al backend. Si la creación es exitosa, limpia el formulario y
 * actualiza los listados de tipos.
 *
 * @returns {void}
 */
// ---------- Restaurar respaldo ----------


/**
 * Reemplaza la base local por la del archivo de respaldo elegido.
 *
 * Pide confirmación (reemplaza todos los datos) y, si sale bien, recarga
 * la página para mostrar los datos restaurados.
 *
 * @returns {Promise<void>}
 */
export async function restaurarDesdeArchivo() {
  const input = $('#archivoRestaurar');
  const msg = $('#msgRestaurar');
  const archivo = input.files[0];

  if (!archivo) {
    msg.className = 'msg error';
    msg.textContent = 'Elegí primero el archivo de respaldo.';
    return;
  }
  if (!confirm(
    `¿Restaurar el respaldo "${archivo.name}"?\n\n` +
    'Se van a REEMPLAZAR todos los datos actuales (productos, ventas, cambios) ' +
    'por los del respaldo. Antes se guarda una copia de los datos actuales.'
  )) return;

  const boton = $('#btnRestaurar');
  boton.disabled = true;
  msg.className = 'msg';
  msg.textContent = '⏳ Restaurando...';

  try {
    const datos = new FormData();
    datos.append('archivo', archivo);
    const res = await apiFetch('/api/backup/restaurar', { method: 'POST', body: datos });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || 'No se pudo restaurar el respaldo.');

    msg.className = 'msg ok';
    msg.textContent = '✓ Respaldo restaurado. Recargando...';
    setTimeout(() => location.reload(), 1500);
  } catch (err) {
    msg.className = 'msg error';
    msg.textContent = '✗ ' + err.message;
    boton.disabled = false;
  }
}


// ---------- Exportar a Excel (CSV) ----------


/**
 * Completa el rango de exportación con el mes en curso.
 */
export function initExportar() {
  const hoy = hoyISO();
  $('#exportarDesde').value = hoy.slice(0, 8) + '01';
  $('#exportarHasta').value = hoy;
}


/**
 * Descarga el CSV de ventas del rango elegido.
 */
export function exportarVentasCSV() {
  const desde = $('#exportarDesde').value;
  const hasta = $('#exportarHasta').value;
  const msg = $('#msgExportar');

  if (!desde || !hasta) {
    msg.className = 'msg error';
    msg.textContent = 'Elegí las dos fechas.';
    return;
  }
  if (desde > hasta) {
    msg.className = 'msg error';
    msg.textContent = 'La fecha "Desde" es posterior a "Hasta".';
    return;
  }
  msg.textContent = '';
  window.location.href = `/api/exportar/ventas.csv?desde=${desde}&hasta=${hasta}`;
}


/**
 * Descarga el CSV con el stock actual.
 */
export function exportarStockCSV() {
  $('#msgExportar').textContent = '';
  window.location.href = '/api/exportar/stock.csv';
}


// ---------- Aviso de stock bajo ----------


/**
 * Carga en el formulario el umbral de stock bajo configurado.
 *
 * @returns {Promise<void>}
 */
export async function cargarUmbralStockBajo() {
  const res = await apiFetch('/api/configuracion');
  if (!res.ok) return;
  const data = await res.json();
  $('#umbralStockBajo').value = data.stock_bajo_umbral;
}


/**
 * Inicializa el formulario del umbral de stock bajo.
 *
 * @param {Function} onGuardado - Se llama después de guardar (para refrescar el dashboard).
 */
export function initFormStockBajo(onGuardado) {
  $('#formStockBajo').addEventListener('submit', async (e) => {
    e.preventDefault();
    const umbral = parseInt($('#umbralStockBajo').value, 10);
    const msg = $('#msgStockBajo');

    const res = await apiFetch('/api/configuracion', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stock_bajo_umbral: umbral })
    });

    if (res.ok) {
      msg.className = 'msg ok';
      msg.textContent = 'Guardado ✅';
      if (onGuardado) onGuardado();
    } else {
      const err = await res.json();
      msg.className = 'msg error';
      msg.textContent = err.error || 'No se pudo guardar';
    }
  });
}


export function initFormTipo() {
  $('#formTipo').addEventListener('submit', async (e) => {
    e.preventDefault();
    const nombre = $('#tipoNombre').value.trim();
    const prefijo = $('#tipoPrefijo').value.trim();
    if (!nombre || !prefijo) return;

    const res = await apiFetch('/api/tipos', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nombre, prefijo })
    });

    if (res.ok) {
      $('#msgTipo').className = 'msg ok';
      $('#msgTipo').textContent = 'Tipo agregado ✅';
      e.target.reset();
      cargarTiposConfig();
      cargarTipos();
    } else {
      const err = await res.json();
      $('#msgTipo').className = 'msg error';
      $('#msgTipo').textContent = err.error || 'No se pudo agregar (¿nombre o prefijo repetido?)';
    }
  });
}


// ---------- Respaldo en Supabase ----------


/**
 * Solicita al backend la creación de un respaldo de la base de datos
 * y muestra el resultado de la operación en la interfaz.
 *
 * Durante el proceso deshabilita el botón de respaldo para evitar
 * solicitudes simultáneas y muestra el estado actual de la operación.
 *
 * @returns {Promise<void>}
 */
export async function subirBackupSupabase() {
  const msg = document.getElementById('msgBackupDrive');
  const boton = document.getElementById('btnBackupDrive');

  if (!msg) {
    console.error('No se encontró #msgBackupDrive');
    return;
  }

  if (boton) {
    boton.disabled = true;
  }

  msg.className = 'msg';
  msg.textContent = '⏳ Preparando respaldo...';

  try {
    await new Promise(resolve => setTimeout(resolve, 300));

    msg.textContent = '☁️ Subiendo respaldo a Supabase...';

    const res = await apiFetch('/api/backup/supabase', {
      method: 'POST'
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(
        data.message ||
        data.error ||
        'No se pudo realizar el respaldo.'
      );
    }

    msg.className = 'msg ok';
    msg.textContent =
      '✓ ¡Respaldo realizado correctamente! ' +
      (data.archivo ? `(${data.archivo})` : '');

  } catch (err) {
    console.error('Error en backup:', err);

    msg.className = 'msg error';
    msg.textContent =
      '✗ ' +
      (err.message ||
        'No se pudo completar el respaldo.');

  } finally {
    if (boton) {
      boton.disabled = false;
    }
  }
}