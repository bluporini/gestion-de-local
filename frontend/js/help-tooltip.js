/* help-tooltip.js
   Muestra el texto de data-help de los .help-icon en un cartel que se
   ubica según el espacio disponible: arriba del ícono si entra, si no
   abajo, y corrido hacia adentro si se saldría por los costados.
   Script clásico (no módulo), igual que update-banner.js.
*/

(function () {
  const MARGEN = 8;      // distancia mínima a los bordes de la ventana
  const SEPARACION = 6;  // distancia entre el ícono y el cartel

  let cartel = null;

  function obtenerCartel() {
    if (!cartel) {
      cartel = document.createElement("div");
      cartel.id = "help-tooltip";
      cartel.setAttribute("role", "tooltip");
      document.body.appendChild(cartel);
    }
    return cartel;
  }

  function mostrar(icono) {
    const texto = icono.dataset.help;
    if (!texto) return;

    const c = obtenerCartel();
    c.textContent = texto;
    c.classList.add("visible");

    const r = icono.getBoundingClientRect();
    const ancho = c.offsetWidth;
    const alto = c.offsetHeight;

    // Arriba si entra; si no, abajo.
    let top = r.top - alto - SEPARACION;
    if (top < MARGEN) top = r.bottom + SEPARACION;
    top = Math.min(top, window.innerHeight - alto - MARGEN);

    // Centrado sobre el ícono, pero sin salirse por los costados.
    let left = r.left + r.width / 2 - ancho / 2;
    left = Math.max(MARGEN, Math.min(left, window.innerWidth - ancho - MARGEN));

    c.style.top = `${Math.max(MARGEN, top)}px`;
    c.style.left = `${left}px`;
  }

  function ocultar() {
    if (cartel) cartel.classList.remove("visible");
  }

  document.addEventListener("mouseover", (e) => {
    const icono = e.target.closest && e.target.closest(".help-icon");
    if (icono) mostrar(icono);
  });
  document.addEventListener("mouseout", (e) => {
    if (e.target.closest && e.target.closest(".help-icon")) ocultar();
  });
  // Con fixed, si se scrollea el cartel quedaría flotando lejos del ícono.
  window.addEventListener("scroll", ocultar, true);
  window.addEventListener("resize", ocultar);
})();
