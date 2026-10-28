import { $, apiFetch } from './api.js';
import { money, esc } from './utils.js';


/**
 * Formatea un monto en forma corta para que entre arriba de una barra
 * (ej: $1,2 M o $850 mil).
 *
 * @param {number} n - Monto.
 * @returns {string} Monto abreviado.
 */
function montoCorto(n) {
  const abs = Math.abs(n);
  const signo = n < 0 ? '−' : '';
  if (abs >= 1_000_000) return `${signo}$${(abs / 1_000_000).toLocaleString('es-AR', { maximumFractionDigits: 1 })} M`;
  if (abs >= 1_000) return `${signo}$${Math.round(abs / 1_000).toLocaleString('es-AR')} mil`;
  return `${signo}$${Math.round(abs).toLocaleString('es-AR')}`;
}


/**
 * Dibuja un gráfico de barras (HTML/CSS, sin librerías) con un valor por mes.
 *
 * @param {string} id - ID del contenedor del gráfico.
 * @param {Array<Object>} meses - Datos de /api/estadisticas/mensual.
 * @param {string} campo - Campo a graficar ('ingresos', 'ganancia' o 'ventas').
 * @param {Function} corto - Formato corto del valor (arriba de la barra).
 * @param {Function} largo - Formato completo del valor (al pasar el mouse).
 */
function renderGrafico(id, meses, campo, corto, largo) {
  const maximo = Math.max(...meses.map(m => m[campo]), 0);
  const ultimo = meses.length - 1;

  const columnas = meses.map((m, i) => {
    const valor = m[campo];
    // Las barras negativas (un mes con más devoluciones en cambios que
    // ventas) se muestran en 0, con el valor igual a la vista.
    const alto = maximo > 0 ? Math.max(valor, 0) / maximo * 100 : 0;
    const clases = ['columna', i === ultimo ? 'actual' : '', valor === 0 ? 'vacia' : ''].join(' ');
    return `
      <div class="${clases}" title="${esc(m.etiqueta)}: ${esc(largo(valor))}">
        <span class="valor">${valor ? esc(corto(valor)) : ''}</span>
        <div class="barra" style="height:${alto}%"></div>
      </div>`;
  }).join('');

  const etiquetas = meses.map(m => `<span>${esc(m.etiqueta)}</span>`).join('');

  $('#' + id).innerHTML = `
    <div class="grafico">${columnas}</div>
    <div class="grafico-etiquetas">${etiquetas}</div>`;
}


/**
 * Dibuja un gráfico de doble barra por mes: ventas en el local y virtuales.
 *
 * @param {string} id - ID del contenedor del gráfico.
 * @param {Array<Object>} meses - Datos de /api/estadisticas/mensual.
 * @param {Function} cantidad - Formato completo de una cantidad de ventas.
 */
function renderGraficoCanal(id, meses, cantidad) {
  const maximo = Math.max(...meses.flatMap(m => [m.ventas_local, m.ventas_virtual]), 0);
  const barra = (valor, clase) => `
    <div class="sub">
      <span class="valor">${valor ? valor.toLocaleString('es-AR') : ''}</span>
      <div class="barra ${clase} ${valor === 0 ? 'vacia' : ''}" style="height:${maximo > 0 ? valor / maximo * 100 : 0}%"></div>
    </div>`;

  const columnas = meses.map(m => `
    <div class="columna" title="${esc(m.etiqueta)}: ${esc(cantidad(m.ventas_local))} en el local · ${esc(cantidad(m.ventas_virtual))} virtuales">
      <div class="par">${barra(m.ventas_local, 'local')}${barra(m.ventas_virtual, 'virtual')}</div>
    </div>`).join('');

  const etiquetas = meses.map(m => `<span>${esc(m.etiqueta)}</span>`).join('');

  $('#' + id).innerHTML = `
    <div class="grafico doble">${columnas}</div>
    <div class="grafico-etiquetas">${etiquetas}</div>`;
}


/**
 * Carga y dibuja las estadísticas de los últimos 12 meses.
 *
 * @returns {Promise<void>}
 */
export async function cargarEstadisticas() {
  const res = await apiFetch('/api/estadisticas/mensual');
  if (!res.ok) return;
  const { meses } = await res.json();

  const cantidad = n => `${n.toLocaleString('es-AR')} venta${n === 1 ? '' : 's'}`;
  renderGrafico('graficoIngresos', meses, 'ingresos', montoCorto, money);
  renderGrafico('graficoGanancia', meses, 'ganancia', montoCorto, money);
  renderGrafico('graficoVentas', meses, 'ventas', n => n.toLocaleString('es-AR'), cantidad);
  renderGraficoCanal('graficoCanal', meses, cantidad);

  const suma = campo => meses.reduce((total, m) => total + m[campo], 0);
  const promedio = campo => suma(campo) / meses.length;

  $('#totalIngresos').textContent =
    `Total 12 meses: ${money(suma('ingresos'))} · Promedio mensual: ${money(promedio('ingresos'))}`;
  $('#totalGanancia').textContent =
    `Total 12 meses: ${money(suma('ganancia'))} · Promedio mensual: ${money(promedio('ganancia'))}`;
  $('#totalVentas').textContent =
    `Total 12 meses: ${cantidad(suma('ventas'))} · Promedio mensual: ${Math.round(promedio('ventas')).toLocaleString('es-AR')}`;

  const total = suma('ventas');
  const porcentaje = n => total ? ` (${Math.round(n / total * 100)}%)` : '';
  $('#totalCanal').textContent =
    `Total 12 meses: Local ${cantidad(suma('ventas_local'))}${porcentaje(suma('ventas_local'))} · ` +
    `Virtual ${cantidad(suma('ventas_virtual'))}${porcentaje(suma('ventas_virtual'))}`;
}
