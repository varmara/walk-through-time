// Walk Through Time: keeps what the map has loaded on the phone, so coming back (or walking back down a street)
// loads almost nothing, and the parts already seen still work with no signal.
//
//   files whose address carries ?v= (card files, map tiles, the page's own scripts and styles): their address
//     changes whenever they do, so a kept copy is always right: served from the phone, fetched only once
//   everything else from this site (the index, the pages): fetched fresh, the kept copy used only when offline
//   other sites (fonts, base maps, photos): left to the browser
// Map and ground tiles are kept apart from the rest (TILES, at most MAX_TILES, the oldest dropped first): a few
// thousand of them in one store made looking up a card's file there slow on a phone.
// When a page has loaded a newer build, it tells this worker (postMessage {build, v}), which drops older copies.
const KEEP = 'wtt-2', TILES = 'wtt-tiles-1', MAX_TILES = 3000;
const isTile = url => /\/data\/[^/]+\/(tiles|ground)\//.test(url.pathname);
let puts = 0;

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k !== KEEP && k !== TILES) await caches.delete(k);
  await self.clients.claim();
})()));

self.addEventListener('fetch', e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  if (url.searchParams.has('v')) e.respondWith(kept(req));
  else e.respondWith(fresh(req));
});

async function kept(req){
  const tile = isTile(new URL(req.url));
  const cache = await caches.open(tile ? TILES : KEEP);
  const hit = await cache.match(req);
  if (hit) return hit;
  const r = await fetch(req);
  if (r.ok) {
    cache.put(req, r.clone()).catch(() => {});
    if (tile && ++puts % 200 === 0) trim(cache);
  }
  return r;
}

async function trim(cache){         // the oldest tiles first (a store lists them in the order they were put)
  const ks = await cache.keys();
  for (const k of ks.slice(0, Math.max(0, ks.length - MAX_TILES))) await cache.delete(k);
}

async function fresh(req){
  const cache = await caches.open(KEEP);
  try {
    const r = await fetch(req);
    if (r.ok) cache.put(req, r.clone());
    return r;
  } catch (err) {
    const hit = await cache.match(req, { ignoreSearch: true });
    if (hit) return hit;
    throw err;
  }
}

// drop copies from older builds: data files with another ?v= than the build the page has loaded, and the page's
// scripts and styles from an earlier version of their content (pipeline/pages.py)
self.addEventListener('message', e => {
  const { build, v } = e.data || {};
  if (!build) return;
  e.waitUntil((async () => {
    for (const name of [KEEP, TILES]) {
      const cache = await caches.open(name);
      for (const req of await cache.keys()) {
        const u = new URL(req.url), rv = u.searchParams.get('v');
        if (!rv) continue;
        const isData = u.pathname.includes('/data/');
        if ((isData && rv !== String(build)) || (!isData && v && rv !== String(v))) await cache.delete(req);
      }
    }
  })());
});
