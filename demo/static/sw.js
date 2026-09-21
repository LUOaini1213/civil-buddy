/* Civil Buddy 工作台的 service worker：把壳（页面、脚本、样式、图标）留一份在本机，
   断网时还能打开上一次的界面；/api/ 永远走网络，不缓存。
   策略是 network-first：有网就拿最新的（服务端已经 no-cache + 按文件 mtime 盖版本），没网才用缓存。 */
const CACHE = "cb-shell-v1";
const SHELL = ["/", "/static/manifest.webmanifest", "/static/icons/cb-icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL).catch(() => {})).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  const isShell = req.mode === "navigate" || url.pathname.startsWith("/static/");
  if (!isShell) return;
  event.respondWith(
    fetch(req).then((res) => {
      if (res && res.ok) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
      }
      return res;
    }).catch(async () => {
      const cached = await caches.match(req, { ignoreSearch: url.pathname.startsWith("/static/") });
      if (cached) return cached;
      if (req.mode === "navigate") return caches.match("/");
      return Response.error();
    })
  );
});
