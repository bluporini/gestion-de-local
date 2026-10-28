import { $ } from './api.js';
import { esc } from './utils.js';

// Función que guarda la nota abierta en el modal (la define quien lo abre).
let guardarNotaActual = null;


/**
 * Botón "Nota" para las tablas (productos, ventas, cambios).
 * Si ya hay una nota, se resalta y la muestra al pasar el mouse.
 *
 * @param {string} nota - Texto de la nota actual (puede estar vacío).
 * @param {string} onclick - Código del handler inline, ej: "abrirNotaVenta('3')".
 * @returns {string} HTML del botón.
 */
export function botonNota(nota, onclick) {
  const tieneNota = Boolean((nota || '').trim());
  return `
    <button class="btn ${tieneNota ? '' : 'secondary'} small btn-nota"
      title="${tieneNota ? esc(nota) : 'Agregar una nota'}"
      onclick="${onclick}">📝 Nota${tieneNota ? ' •' : ''}</button>`;
}


/**
 * Abre el modal de nota.
 *
 * @param {string} titulo - Título del modal.
 * @param {string} nota - Texto actual de la nota.
 * @param {Function} guardar - Recibe el texto nuevo y devuelve la respuesta
 *   de apiFetch; se llama al tocar "Guardar nota".
 */
export function abrirModalNota(titulo, nota, guardar) {
  guardarNotaActual = guardar;
  $('#tituloNota').textContent = titulo;
  $('#notaTexto').value = nota || '';
  $('#msgNota').textContent = '';
  $('#modalNota').classList.add('active');
  $('#notaTexto').focus();
}


/**
 * Guarda la nota del modal con la función recibida en abrirModalNota().
 *
 * @returns {Promise<void>}
 */
export async function guardarModalNota() {
  if (!guardarNotaActual) return;
  const res = await guardarNotaActual($('#notaTexto').value);

  if (!res.ok) {
    $('#msgNota').className = 'msg error';
    $('#msgNota').textContent = 'No se pudo guardar la nota';
    return;
  }

  $('#msgNota').className = 'msg ok';
  $('#msgNota').textContent = 'Nota guardada ✅';
  setTimeout(() => $('#modalNota').classList.remove('active'), 600);
}
