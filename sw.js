/* ============================================
 * 投资日历 PWA Service Worker v8
 * 策略（回归稳定版）：
 *   - 页面/document：网络优先（3s超时回退缓存）→ 打开即最新，最可靠
 *   - 激活时：清理旧缓存 + 用无 query 的 fetch 刷新 index.html 缓存
 *     （不做导航 cachebust，避免 CDN 307 重定向在真实浏览器 SW 下引发导航失败）
 *   - 静态资源：缓存优先 + 后台更新 → 秒开
 *   - 带 ?v= 的轮询请求：直连网络、绝不回退旧缓存 → 版本检测准确
 *   - index.html 内置版本自检（立即+15分钟+可见性变化自动 reload）负责最终同步
 * 版本号：每次部署递增 CACHE_VERSION 强制浏览器更新 SW。
 * ============================================ */
var CACHE_VERSION = 'investor-calendar-v8';
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
/* 激活：清理旧缓存，并用无 query 请求刷新 index.html 缓存为最新版（保证回退的一定是最新版） */
self.addEventListener('activate', function(event){
  event.waitUntil(
    caches.keys().then(function(keys){
      return Promise.all(
        keys.filter(function(k){ return k !== CACHE_NAME; })
            .map(function(k){ return caches.delete(k); })
      );
    }).then(function(){
      return fetch('./index.html', {cache: 'no-store'}).then(function(resp){
        if(resp && resp.status === 200){
          return caches.open(CACHE_NAME).then(function(cache){
            return cache.put('./index.html', resp.clone())
              .then(function(){ return cache.put('./', resp); });
          });
        }
      }).catch(function(){ /* 离线则保留预缓存版本 */ });
    }).then(function(){
      return self.clients.claim();
    })
  );
});
/* 请求处理 */
self.addEventListener('fetch', function(event){
  var req = event.request;
  if(req.method !== 'GET'){ return; }
  var url;
  try { url = new URL(req.url); } catch(e){ return; }
  if(url.origin !== location.origin){ return; }
  // 带 ?v= 的版本轮询请求：直连网络，不缓存，不回退旧缓存（保证版本检测准确）
  if(url.search && url.search.indexOf('v=') >= 0){
    event.respondWith(fetch(req, {cache: 'no-store'})
      .catch(function(){ return caches.match('./index.html'); }));
    return;
  }
  // 页面导航：网络优先（3秒超时回退缓存）→ 最可靠，打开即最新
  if(req.mode === 'navigate' || req.destination === 'document'){
    event.respondWith(
      new Promise(function(resolve){
        var settled = false;
        var timer = setTimeout(function(){
          if(settled){ return; }
          settled = true;
          caches.match('./index.html').then(resolve);
        }, 3000);
        fetch(req, {cache: 'no-store'}).then(function(resp){
          if(settled){ return; }
          settled = true;
          clearTimeout(timer);
          if(resp && resp.status === 200){
            var copy = resp.clone();
            caches.open(CACHE_NAME).then(function(cache){
              cache.put('./index.html', copy).then(function(){
                return cache.put('./', resp.clone());
              });
            });
            resolve(resp);
          } else {
            caches.match('./index.html').then(resolve);
          }
        }).catch(function(){
          if(settled){ return; }
          settled = true;
          clearTimeout(timer);
          caches.match('./index.html').then(resolve);
        });
      })
    );
    return;
  }
  // 静态资源（style/script/image/font等）：缓存优先 + 后台更新
  if(req.destination === 'style' || req.destination === 'script' ||
     req.destination === 'image' || req.destination === 'font' ||
     url.pathname.indexOf('calendar.ics') >= 0){
    event.respondWith(
      caches.match(req).then(function(cached){
        var networkPromise = fetch(req).then(function(resp){
          if(resp && resp.status === 200){
            var copy = resp.clone();
            caches.open(CACHE_NAME).then(function(cache){ cache.put(req, copy); });
          }
          return resp;
        }).catch(function(){ return undefined; });
        if(cached){ return cached; }
        return networkPromise.then(function(resp){
          if(resp){ return resp; }
          if(url.pathname.indexOf('calendar.ics') >= 0){
            return caches.match('./index.html');
          }
          return new Response('', {status: 408, statusText: 'Request Timeout'});
        });
      })
    );
  }
});
