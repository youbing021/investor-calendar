/* ============================================
 * 投资日历 PWA Service Worker
 * 策略：缓存优先 + 后台静默更新（Stale-While-Revalidate）
 *    - 打开 PWA 立即返回缓存页面 → 秒开，无白屏
 *    - 同时后台请求网络，拿到新内容后更新缓存
 *    - 每日更新的事件，下次打开自动呈现最新版
 * 每次 index.html 更新时，通过版本号触发新 SW 并刷新缓存。
 * ============================================ */
var CACHE_VERSION = 'investor-calendar-v4';
var CACHE_NAME = CACHE_VERSION;

var PRECACHE_URLS = [
  './',
  './index.html',
  './manifest.json',
  './logo.png',
  './logo.webp',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-512.png',
  './apple-touch-icon.png'
];

/* 安装：预缓存核心资源 */
self.addEventListener('install', function(event){
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache){
      return cache.addAll(PRECACHE_URLS);
    }).then(function(){
      return self.skipWaiting();
    })
  );
});

/* 激活：清理旧缓存 */
self.addEventListener('activate', function(event){
  event.waitUntil(
    caches.keys().then(function(keys){
      return Promise.all(
        keys.filter(function(k){ return k !== CACHE_NAME; })
            .map(function(k){ return caches.delete(k); })
      );
    }).then(function(){
      return self.clients.claim();
    })
  );
});

/* 请求：缓存优先 + 后台更新（Stale-While-Revalidate）
 *  - 有缓存：立即返回缓存（秒开），同时后台 fetch 更新缓存
 *  - 无缓存：直接 fetch 并缓存
 *  - 离线：返回缓存 */
self.addEventListener('fetch', function(event){
  var req = event.request;
  // 仅处理 GET，且只处理同源请求
  if(req.method !== 'GET'){ return; }
  var url = new URL(req.url);
  if(url.origin !== location.origin){ return; }

  // 跳过不需要缓存的请求（如分享/数据上报等）
  if(req.mode === 'navigate' || req.destination === 'document' ||
     req.destination === 'style' || req.destination === 'script' ||
     req.destination === 'image' || req.destination === 'font' ||
     url.pathname.indexOf('calendar.ics') >= 0){

    event.respondWith(
      caches.match(req).then(function(cached){
        // 后台静默更新（不阻塞渲染）
        var networkPromise = fetch(req).then(function(resp){
          if(resp && resp.status === 200){
            var copy = resp.clone();
            caches.open(CACHE_NAME).then(function(cache){
              cache.put(req, copy);
            });
          }
          return resp;
        }).catch(function(){
          return undefined;
        });

        // 有缓存：立即返回，同时触发后台更新
        if(cached){ return cached; }
        // 无缓存：等网络返回
        return networkPromise.then(function(resp){
          if(resp){ return resp; }
          // 离线且无缓存：导航回退 index.html
          if(req.mode === 'navigate'){
            return caches.match('./index.html');
          }
          return new Response('', {status: 408, statusText: 'Request Timeout'});
        });
      })
    );
  }
});