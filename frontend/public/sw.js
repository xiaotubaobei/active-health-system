const CACHE_PREFIX = "active-health-shell";
const CACHE_VERSION = "v2";
const CACHE_NAME = `${CACHE_PREFIX}-${CACHE_VERSION}`;
const SCOPE_URL = new URL("./", self.registration.scope).href;
const SCOPE_PATH = new URL(self.registration.scope).pathname;

const REQUIRED_SHELL_URLS = [
  new URL("offline.html", self.registration.scope).href,
  new URL("manifest.webmanifest", self.registration.scope).href,
  new URL("icons/icon-192.png", self.registration.scope).href,
  new URL("icons/icon-512.png", self.registration.scope).href,
  new URL("icons/apple-touch-icon.png", self.registration.scope).href,
];

function isPrivateRequest(url) {
  const scopedApi = `${SCOPE_PATH.replace(/\/$/, "")}/api/`;
  const scopedUploads = `${SCOPE_PATH.replace(/\/$/, "")}/uploads/`;
  return url.origin === self.location.origin &&
    (url.pathname === "/api" ||
      url.pathname.startsWith("/api/") ||
      url.pathname.startsWith(scopedApi) ||
      url.pathname === "/uploads" ||
      url.pathname.startsWith("/uploads/") ||
      url.pathname.startsWith(scopedUploads));
}

function isVersionedAsset(url) {
  const assetsPath = `${SCOPE_PATH}assets/`.replace(/\/+/g, "/");
  return url.origin === self.location.origin && url.pathname.startsWith(assetsPath);
}

function isRequiredShellAsset(url) {
  return REQUIRED_SHELL_URLS.includes(url.href);
}

function assetUrlsFromHtml(html) {
  const urls = new Set();
  const pattern = /(?:src|href)=["']([^"']+)["']/g;
  for (const match of html.matchAll(pattern)) {
    const url = new URL(match[1], SCOPE_URL);
    if (isVersionedAsset(url) || isRequiredShellAsset(url)) urls.add(url.href);
  }
  return [...urls];
}

async function refreshApplicationShell(response) {
  if (!response?.ok) return;
  const cache = await caches.open(CACHE_NAME);
  const html = await response.clone().text();
  const currentAssets = assetUrlsFromHtml(html);

  await cache.put(SCOPE_URL, response.clone());
  await Promise.allSettled(
    [...REQUIRED_SHELL_URLS, ...currentAssets].map((url) =>
      cache.add(new Request(url, { cache: "reload" })),
    ),
  );

  const currentAssetSet = new Set(currentAssets);
  const cachedRequests = await cache.keys();
  await Promise.all(
    cachedRequests.map((request) => {
      const url = new URL(request.url);
      return isVersionedAsset(url) && !currentAssetSet.has(url.href)
        ? cache.delete(request)
        : Promise.resolve(false);
    }),
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    fetch(SCOPE_URL, { cache: "reload" })
      .then(refreshApplicationShell)
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names
          .filter((name) => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
          .map((name) => caches.delete(name)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Authentication, profiles, sessions, reports, uploads and every mutation
  // always go to the network and are never written to Cache Storage.
  if (request.method !== "GET" || isPrivateRequest(url)) {
    event.respondWith(fetch(request));
    return;
  }

  if (request.mode === "navigate") {
    const networkResponse = fetch(request).then((response) => ({
      response,
      refresh: response.ok
        ? refreshApplicationShell(response.clone())
        : Promise.resolve(),
    }));
    event.respondWith(
      networkResponse
        .then(({ response }) => response)
        .catch(async () =>
          (await caches.match(new URL("offline.html", self.registration.scope).href)) ||
          (await caches.match(SCOPE_URL)) ||
          Response.error(),
        ),
    );
    event.waitUntil(networkResponse.then(({ refresh }) => refresh).catch(() => undefined));
    return;
  }

  if (isVersionedAsset(url) || isRequiredShellAsset(url)) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then(async (response) => {
        if (response.ok) {
          const cache = await caches.open(CACHE_NAME);
          await cache.put(request, response.clone());
        }
        return response;
      })),
    );
  }
});
