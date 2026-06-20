// TokenLine Service Worker v2 — forces fresh content
var CACHE = "tokenline-v2";
self.addEventListener("install", function(e) {
  // Clear old caches
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(keys.filter(function(k) { return k !== CACHE; }).map(function(k) { return caches.delete(k); }));
    }).then(function() { return self.skipWaiting(); })
  );
});
self.addEventListener("activate", function(e) {
  e.waitUntil(self.clients.claim());
});
self.addEventListener("fetch", function(e) {
  // Network-first for HTML, cache for static assets
  if (e.request.destination === "document" || e.request.url.match(/\.html$/)) {
    e.respondWith(fetch(e.request).catch(function() { return caches.match(e.request); }));
  } else {
    e.respondWith(caches.match(e.request).then(function(r) { return r || fetch(e.request); }));
  }
});
