/* update-banner.js
   Sumar en index.html, después de tus otros scripts:
     <script src="update-banner.js"></script>

   Requiere un elemento en el <body>, idealmente arriba de todo:
     <div id="update-banner"></div>
*/

(function () {
  const CHECK_INTERVAL_MS = 5 * 60 * 1000; // re-consultar cada 5 min mientras la app queda abierta
  const STATUS_ENDPOINT = "/api/update/status";
  const DISMISS_KEY_PREFIX = "update_dismissed_"; // + versión, para no repetir el aviso de la misma versión

  function createBannerIfMissing() {
    let banner = document.getElementById("update-banner");
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "update-banner";
      document.body.prepend(banner);
    }
    return banner;
  }

  function renderBanner(banner, status) {
    const dismissKey = DISMISS_KEY_PREFIX + status.latest_version;
    if (sessionStorage.getItem(dismissKey)) {
      banner.classList.remove("visible");
      return;
    }

    banner.innerHTML = "";
    const text = document.createElement("span");
    text.textContent = `Hay una nueva versión disponible (${status.latest_version}). Cerrá y volvé a abrir la app para actualizar.`;

    const dismissBtn = document.createElement("button");
    dismissBtn.textContent = "Ocultar";
    dismissBtn.addEventListener("click", () => {
      sessionStorage.setItem(dismissKey, "1");
      banner.classList.remove("visible");
    });

    banner.appendChild(text);
    banner.appendChild(dismissBtn);
    banner.classList.add("visible");
  }

  async function checkUpdateStatus() {
    try {
      const res = await fetch(STATUS_ENDPOINT);
      if (!res.ok) return;
      const status = await res.json();

      const banner = createBannerIfMissing();
      if (status.update_available) {
        renderBanner(banner, status);
      } else {
        banner.classList.remove("visible");
      }
    } catch (err) {
      // Silencioso: si falla la consulta, simplemente no se muestra el banner.
      console.debug("No se pudo consultar el estado de actualización:", err);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    checkUpdateStatus();
    setInterval(checkUpdateStatus, CHECK_INTERVAL_MS);
  });
})();