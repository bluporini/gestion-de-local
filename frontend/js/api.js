/**
 * Busca el primer elemento del documento que coincide con un selector CSS.
 *
 * @param {string} s - Selector CSS.
 * @returns {Element|null} Elemento encontrado o null si no existe.
 */
export const $ = s => document.querySelector(s);


// El backend sirve el frontend, así que la API está siempre en el mismo
// origen (sin depender de host/puerto fijos ni de CORS).
export const apiUrlInput = {
  value: window.location.origin
};


/**
 * Construye la URL completa de un endpoint de la API.
 *
 * Elimina las barras finales de la URL base para evitar duplicarlas
 * al concatenarla con la ruta del endpoint.
 *
 * @param {string} path - Ruta del endpoint de la API.
 * @returns {string} URL completa del endpoint.
 */
export function api(path) {
  return apiUrlInput.value.replace(/\/$/, '') + path;
}


/**
 * Realiza una petición HTTP a la API configurada.
 *
 * Construye la URL a partir de la dirección base almacenada
 * en apiUrlInput y delega la petición en fetch.
 *
 * @param {string} path - Ruta del endpoint de la API.
 * @param {RequestInit} [options={}] - Opciones de la petición HTTP.
 * @returns {Promise<Response>} Respuesta obtenida del servidor.
 */
export async function apiFetch(path, options = {}) {
  const res = await fetch(api(path), options);
  return res;
}