import { $, apiUrlInput, apiFetch } from './api.js';
import { cargarTipos } from './productos.js';
import { esc } from './utils.js';

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