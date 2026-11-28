// Офлайн-режим и уведомления ДермаКвеста. При обновлении игры меняйте номер версии в CACHE.
const CACHE = 'dermaquest-v23';
const FILES = ['./', './index.html', './manifest.webmanifest', './icons/icon-180.png', './icons/icon-192.png', './icons/icon-512.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  // Запросы к серверу рейтинга и другим сайтам не кэшируем.
  if (new URL(req.url).origin !== self.location.origin) return;
  // Страница игры: сначала сеть, чтобы обновления приходили сразу; без сети берём из кэша.
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req)
      .then(r => { const cp = r.clone(); caches.open(CACHE).then(c => c.put('./index.html', cp)); return r; })
      .catch(() => caches.match('./index.html')));
    return;
  }
  e.respondWith(caches.match(req).then(r => r || fetch(req).then(resp => {
    const cp = resp.clone(); caches.open(CACHE).then(c => c.put(req, cp)); return resp;
  })));
});

self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = { body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || 'ДермаКвест', {
    body: d.body || '', tag: d.tag || 'dq', icon: './icons/icon-192.png', badge: './icons/icon-192.png', data: { url: './' }
  }));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
    for (const c of list) { if ('focus' in c) return c.focus(); }
    return self.clients.openWindow('./');
  }));
});
