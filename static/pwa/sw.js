const CACHE_NAME = 'electricbill-pwa-v2';
const STATIC_ASSETS = [
    '/pwa/',
    '/pwa/dashboard.html',
    '/pwa/data.html',
    '/static/pwa/css/style.css',
    '/static/pwa/js/api.js',
    '/static/pwa/js/utils.js',
    '/static/pwa/js/login.js',
    '/static/pwa/js/dashboard.js',
    '/static/pwa/js/data.js',
    '/static/pwa/manifest.json',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Don't cache API calls
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/mark_as_paid') || url.pathname.startsWith('/cancel_mark_as_paid')) {
        event.respondWith(
            fetch(event.request).catch(() =>
                new Response(JSON.stringify({ success: false, message: 'Offline' }), {
                    headers: { 'Content-Type': 'application/json' },
                })
            )
        );
        return;
    }

    // Network-first for static assets (always get fresh code, fallback to cache if offline)
    event.respondWith(
        fetch(event.request).then((res) => {
            if (res.ok) {
                const resClone = res.clone();
                caches.open(CACHE_NAME).then((cache) => cache.put(event.request, resClone));
            }
            return res;
        }).catch(() => caches.match(event.request))
    );
});
