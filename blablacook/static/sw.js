/* Service worker de BlablaCook : rend l’application installable et utilisable hors connexion pour son interface.
   - /api/* : jamais mis en cache (données personnelles, état des réservations toujours à jour) ;
   - page d’accueil : réseau d’abord, copie en cache en secours hors connexion ;
   - /static/* : cache d’abord, puis mise à jour en arrière-plan (« stale-while-revalidate »).
   Changer VERSION invalide l’ancien cache. */
const VERSION = "blablacook-v3";
const SHELL = ["./", "static/app.css", "static/common.js", "static/maps.js", "static/meals.js", "static/account.js",
  "static/app.js", "static/icon.svg", "static/icons/icon-192.png", "static/images/table.webp"];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(VERSION).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== location.origin) return;
  const base = new URL("./", self.registration.scope).pathname;
  const path = url.pathname.startsWith(base) ? url.pathname.slice(base.length) : url.pathname;
  if (path.startsWith("api/")) return;                       // toujours le réseau
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).then(response => {
      const copy = response.clone();
      caches.open(VERSION).then(cache => cache.put("./", copy));
      return response;
    }).catch(() => caches.match("./")));
    return;
  }
  if (path.startsWith("static/")) {
    event.respondWith(caches.open(VERSION).then(cache => cache.match(request).then(hit => {
      const update = fetch(request).then(response => {
        if (response.ok) cache.put(request, response.clone());
        return response;
      }).catch(() => hit);
      return hit || update;
    })));
  }
});
