/* demo-banner.js
   Muestra un cartel cuando la app corre como demo web (backend/demo.py).
   Script clásico (no módulo), igual que update-banner.js.
*/

(function () {
  document.addEventListener("DOMContentLoaded", async () => {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) return;
      const status = await res.json();
      if (!status.demo) return;

      const banner = document.getElementById("demo-banner");
      if (!banner) return;
      banner.textContent =
        "Demo con datos de ejemplo. Podés probar todo: los datos se reinician solos cada tanto.";
      banner.classList.add("visible");
    } catch (err) {
      console.debug("No se pudo consultar el modo demo:", err);
    }
  });
})();
