/* v2.11 service worker: displays the tracker's Web Push notifications.
   Registered from the web UI; the server sends RFC 8291-encrypted
   messages that the browser decrypts and hands to this worker. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; }
  catch (x) { try { d = { body: e.data ? e.data.text() : '' }; } catch (y) {} }
  e.waitUntil(self.registration.showNotification(
    d.title || 'Food storage alert',
    { body: d.body || '', tag: d.tag || 'food-alert',
      icon: d.icon, badge: d.badge, data: { url: d.url || '/' } }));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: 'window',
                                      includeUncontrolled: true }).then(cs => {
    for (const c of cs) { if ('focus' in c) return c.focus(); }
    return self.clients.openWindow(
      (e.notification.data && e.notification.data.url) || '/');
  }));
});
