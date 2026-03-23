const CACHE_NAME = 'tpl-capture-v1';
const ASSETS = [
  '/ideas/',
  '/ideas/index.html',
  '/ideas/manifest.json',
  '/ideas/icon-192.png',
  '/ideas/icon-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // Network-first for API calls, cache-first for app shell
  if (e.request.url.includes('/rest/v1/') || e.request.url.includes('/storage/v1/') || e.request.url.includes('/api/')) {
    return;
  }

  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
