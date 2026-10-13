import { $, apiUrlInput, apiFetch } from './api.js';
import { money, esc, hoyISO, detallePago, parseFechaUTC, formatoFechaHora } from './utils.js';
import { generarLineasCambios } from './cambios.js';

const NOMBRES_METODO_PAGO = {
  efectivo: 'Efectivo',
  tarjeta_debito: 'Tarjeta débito',
  tarjeta_credito: 'Tarjeta crédito',
  transferencia: 'Transferencia',
  otro: 'Otro'
};

export async function cargarDashboard() {
  if (!apiUrlInput.value) return;
  const res = await apiFetch('/api/dashboard/resumen');
  if (!res.ok) return;
  const d = await res.json();

  $('#statVentasHoy').textContent = d.ventas_hoy;
  $('#statVentasSemana').textContent = d.ventas_semana;
  $('#statVentasMes').textContent = d.ventas_mes;
  $('#statIngresosHoy').textContent = money(d.ingresos_hoy);
  $('#statIngresosSemana').textContent = money(d.ingresos_semana);
  $('#statIngresosMes').textContent = money(d.ingresos_mes);
  $('#statGananciaSemana').textContent = money(d.ganancia_semana);
  $('#statGananciaMes').textContent = money(d.ganancia_mes);

  $('#tablaStockBajo').innerHTML = d.productos_stock_bajo.length
    ? d.productos_stock_bajo.map(p => `
        <tr>
          <td>${esc(p.producto_nombre)}</td><td>${esc(p.codigo)}</td><td>${esc(p.talle)} ${esc(p.color)}</td>
          <td><span class="badge bajo">${p.stock_actual}</span></td>
        </tr>`).join('')
    : '<tr><td colspan="4" class="empty">Todo el stock está en niveles normales ✅</td></tr>';

  cargarHistorialDia();
}

export async function cargarHistorialDia() {
  if (!apiUrlInput.value) return;
  const fecha = $('#fechaHistorial').value || hoyISO();
  const res = await apiFetch(`/api/ventas?fecha=${fecha}&page_size=100`);
  const { data } = await res.json();

  $('#tablaHistorialDia').innerHTML = data.length ? data.map(v => `
    <tr>
      <td>${parseFechaUTC(v.fecha).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', hour12: false })}</td>
      <td>${esc(v.codigo) || '—'}</td>
      <td>${esc(v.cliente) || '—'}</td>
      <td>${(v.venta_items || []).map(i => `${i.cantidad}× ${esc(i.variantes_producto?.productos?.nombre)}`).join('<br>')}</td>
      <td>${detallePago(v)}</td>
      <td>${money(v.total)}</td>
      <td>${money(v.ganancia)}</td>
      <td>
        <span class="badge ${esc(v.estado)}">${esc(v.estado)}</span>
        ${v.tiene_cambio ? '<span class="badge cambio">Cambio</span>' : ''}
      </td>
    </tr>`).join('') : '<tr><td colspan="7" class="empty">No hay ventas ese día</td></tr>';
}

function generarTextoResumenCaja(fecha, ventas, cambios) {
  const fechaFormateada = new Date(fecha + 'T00:00:00').toLocaleDateString('es-AR');
  const realizadas = ventas.filter(v => v.estado === 'realizada');

  const lineasVentas = ventas.map(v => {
    const productos = (v.venta_items || [])
      .map(i => `${i.cantidad}x ${i.variantes_producto?.productos?.nombre || ''}`)
      .join(', ') || '—';
    const metodo = NOMBRES_METODO_PAGO[v.metodo_pago] || v.metodo_pago;
    const tag = v.estado === 'devolucion' ? ' (DEVOLUCIÓN)' : '';
    return `${v.codigo || '—'} - ${productos} - ${metodo} - ${money(v.total)}${tag}`;
  });

  const totalesPorMetodo = {};
  let totalGeneral = 0;
  realizadas.forEach(v => {
    totalGeneral += v.total;
    totalesPorMetodo[v.metodo_pago] = (totalesPorMetodo[v.metodo_pago] || 0) + v.total;
  });

  const lineasTotales = Object.entries(totalesPorMetodo).map(([metodo, monto]) => {
    const etiqueta = `Total en ${NOMBRES_METODO_PAGO[metodo] || metodo}`.padEnd(30, ' ');
    return `${etiqueta}= ${money(monto)}`;
  });

  const lineasCambios = generarLineasCambios(cambios);
  const totalesCambiosPorMetodo = {};
  let totalCambios = 0;

  cambios.forEach(c => {
    const monto = c.monto_diferencia || 0;
    const metodo = c.metodo_pago;

    totalCambios += monto;

    totalesCambiosPorMetodo[metodo] =
      (totalesCambiosPorMetodo[metodo] || 0) + monto;
  });
  const lineasTotalesCambios = Object.entries(totalesCambiosPorMetodo).map(([metodo, monto]) => {
    const etiqueta = `Cambios en ${NOMBRES_METODO_PAGO[metodo] || metodo}`.padEnd(30, ' ');
    return `${etiqueta}= ${money(monto)}`;
  });

  const totalGeneralFinal = totalGeneral + totalCambios;

  return [
    'Resumen de caja',
    `Fecha: ${fechaFormateada}`,
    '',
    'Ventas',
    '----',
    ...(lineasVentas.length ? lineasVentas : ['Sin ventas registradas']),
    '----',
    `${'Total'.padEnd(30, ' ')}= ${money(totalGeneral)}`,
    ...lineasTotales,
    '',
    'Cambios',
    '----',
    ...(cambios.length ? lineasTotalesCambios : ['Sin cambios registrados']),
    '----',
    '',
    `${'Total general'.padEnd(30, ' ')}= ${money(totalGeneralFinal)}`,

  ].join('\n');
}

export async function abrirResumenCaja() {
  if (!apiUrlInput.value) return;
  const fecha = $('#fechaHistorial').value || hoyISO();
  const res = await apiFetch(`/api/ventas?fecha=${fecha}&page_size=200`);
  const { data } = await res.json();
  const [resVentas, resCambios] = await Promise.all([
    apiFetch(`/api/ventas?fecha=${fecha}&page_size=200`),
    apiFetch(`/api/cambios?fecha=${fecha}&page_size=200`)
  ]);
  const { data: ventas } = await resVentas.json();
  const { data: cambios } = await resCambios.json();

  $('#textoResumenCaja').value = generarTextoResumenCaja(fecha, ventas, cambios);
  $('#msgResumenCaja').textContent = '';
  $('#modalResumenCaja').classList.add('active');
}

export async function copiarResumenCaja() {
  const texto = $('#textoResumenCaja').value;
  try {
    await navigator.clipboard.writeText(texto);
    $('#msgResumenCaja').className = 'msg ok';
    $('#msgResumenCaja').textContent = 'Copiado al portapapeles ✅';
  } catch (e) {
    $('#msgResumenCaja').className = 'msg error';
    $('#msgResumenCaja').textContent = 'No se pudo copiar (probá seleccionar el texto manualmente)';
  }
}

export function exportarResumenCajaPDF() {
  const texto = $('#textoResumenCaja').value;
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();

  doc.setFont('courier', 'normal');
  doc.setFontSize(10);
  const lineas = doc.splitTextToSize(texto, 180);
  doc.text(lineas, 14, 16);

  const fecha = $('#fechaHistorial').value || hoyISO();
  doc.save(`resumen-caja-${fecha}.pdf`);
}

function probarPDF() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();

  doc.text('Hola mundo', 20, 20);

  doc.save('prueba.pdf');
}