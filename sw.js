/* ============================================
 * 投资日历 PWA Service Worker
 * 策略：导航网络优先 + 静态缓存优先
 *   - 页面/document：Network-First（2s超时回退缓存）→ 打开即最新内容
 *   - 静态资源(logo/icon等)：缓存优先 + 后台更新 → 秒开
 *   - 带时间戳参数的轮询请求：直连网络、不缓存 → 保证版本检测准确
 *   - 离线：所有请求回退缓存
 * 版本号：每次 index.html 更新时递增 CACHE_VERSION 触发新 SW。
 * ============================================ */
var CACHE_VERSION = 'investor-calendar-v5';
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
/* 请求处理 */
self.addEventListener('fetch', function(event){
  var req = event.request;
  // 仅处理 GET 同源请求
  if(req.method !== 'GET'){ return; }
  var url = new URL(req.url);
  if(url.origin !== location.origin){ return; }

  // 带查询参数的请求（版本轮询/穿透缓存）：直连网络，不缓存
  if(url.search && url.search.indexOf('v=') >= 0){
    event.respondWith(fetch(req).catch(function(){ return caches.match('./index.html'); }));
    return;
  }

  // 页面导航：网络优先（2秒超时回退缓存）→ 打开即最新内容
  if(req.mode === 'navigate' || req.destination === 'document'){
    event.respondWith(
      new Promise(function(resolve){
        var settled = false;
        var timer = setTimeout(function(){
          if(settled){ return; }
          settled = true;
          caches.match(req).then(function(cached){
            if(cached){ resolve(cached); }
            else { caches.match('./index.html').then(resolve); }
          });
        }, 2000);
        fetch(req).then(function(resp){
          if(settled){ return; }
          settled = true;
          clearTimeout(timer);
          if(resp && resp.status === 200){
            var copy = resp.clone();
            caches.open(CACHE_NAME).then(function(cache){ cache.put(req, copy); });
            resolve(resp);
          } else {
            caches.match(req).then(function(cached){
              if(cached){ resolve(cached); }
              else { resolve(resp); }
            });
          }
        }).catch(function(){
          if(settled){ return; }
          settled = true;
          clearTimeout(timer);
          caches.match(req).then(function(cached){
            if(cached){ resolve(cached); }
            else { caches.match('./index.html').then(resolve); }
          });
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
