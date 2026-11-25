/* ============================================
 * 投资日历 PWA Service Worker v15（详情外置版）
 * 策略：
 *   - 页面/document：缓存优先 + 后台静默更新（Stale-While-Revalidate）
 *     → 打开即出内容，不再等待网络；后台拿到新版本后替换缓存
 *   - 静态资源：缓存优先 + 后台更新 → 秒开
 *   - ?v= 轮询请求：直连网络；若是页面全文，顺带刷新页面缓存
 *   - version.txt：直连网络，不缓存（版本检测只拉几十字节）
 * 版本号：每次部署递增 CACHE_VERSION 强制浏览器更新 SW。
 * ============================================ */
var CACHE_VERSION = 'investor-calendar-v16';
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

self.addEventListener('install', function(event){
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache){
      return cache.addAll(PRECACHE_URLS);
    }).then(function(){
      return self.skipWaiting();
    })
  );
});

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

/* 后台刷新页面缓存（不阻塞响应） */
function refreshPageCache(req){
  return fetch(req, {cache: 'no-store'}).then(function(resp){
    if(resp && resp.status === 200){
      var copy = resp.clone();
      var copy2 = resp.clone();
      caches.open(CACHE_NAME).then(function(cache){
        cache.put('./index.html', copy);
        cache.put('./', copy2);
      });
    }
  }).catch(function(){});
}

self.addEventListener('fetch', function(event){
  var req = event.request;
  if(req.method !== 'GET'){ return; }
  var url;
  try { url = new URL(req.url); } catch(e){ return; }
  if(url.origin !== location.origin){ return; }

  // version.txt：只走网络，绝不缓存（版本检测必须准确）
  if(url.pathname.indexOf('version.txt') >= 0){
    event.respondWith(
      fetch(req, {cache: 'no-store'}).catch(function(){
        return new Response('', {status: 204, statusText: 'No Content'});
      })
    );
    return;
  }

  // 带 ?v= 的版本轮询请求：直连网络；若是页面全文则顺手刷新缓存
  if(url.search && url.search.indexOf('v=') >= 0){
    event.respondWith(
      fetch(req, {cache: 'no-store'}).then(function(resp){
        if(resp && resp.status === 200 &&
           (req.destination === 'document' || url.pathname === '/' || url.pathname.indexOf('index.html') >= 0)){
          var copy = resp.clone();
          var copy2 = resp.clone();
          caches.open(CACHE_NAME).then(function(cache){
            cache.put('./index.html', copy);
            cache.put('./', copy2);
          });
        }
        return resp;
      }).catch(function(){ return caches.match('./index.html'); })
    );
    return;
  }

  // 页面导航：网络优先（2.5 秒抢不到就用缓存）→ 新版本一打开就是新的，慢网也不至于一直白屏
  if(req.mode === 'navigate' || req.destination === 'document'){
    var netFetch = fetch(req, {cache: 'no-store'}).then(function(resp){
      if(resp && resp.status === 200){
        var copy = resp.clone();
        var copy2 = resp.clone();
        caches.open(CACHE_NAME).then(function(cache){
          cache.put('./index.html', copy);
          cache.put('./', copy2);
        });
      }
      return resp;
    });
    var timeout = new Promise(function(resolve){
      setTimeout(function(){ resolve(null); }, 2500);
    });
    event.respondWith(
      Promise.race([netFetch, timeout]).then(function(resp){
        if(resp){ return resp; }
        return caches.match('./index.html').then(function(cached){
          if(cached){ return cached; }
          return Promise.race([netFetch, timeout]).then(function(r2){
            return r2 || new Response('<h1>网络不稳定</h1>', {status: 503, headers: {'Content-Type': 'text/html; charset=utf-8'}});
          });
        });
      }).catch(function(){
        return caches.match('./index.html');
      })
    );
    return;
  }

  // 事件详情 data/desc/*.json：缓存优先 + 后台更新（详情点开才用得到，命中缓存即秒出）
  if(url.pathname.indexOf('/data/desc/') >= 0){
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
          return resp || new Response('{}', {status: 200, headers: {'Content-Type': 'application/json; charset=utf-8'}});
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
