/* ============================================
 * 投资日历 PWA Service Worker
 * 策略：安装时预缓存核心资源；运行时缓存页面资源；
 *       网络优先（保证每日更新的内容始终最新），离线时回退缓存。
 * 每次 index.html 更新时，通过版本号触发新 SW 并刷新缓存。
 * ============================================ */
var CACHE_VERSION = 'investor-calendar-v2';
var CACHE_NAME = CACHE_VERSION;

var PRECACHE_URLS = [
  './',
  './index.html',
  './manifest.json',
  './logo.png',
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

/* 请求：网络优先，失败回退缓存；日历订阅文件(calendar.ics)同样处理 */
self.addEventListener('fetch', function(event){
  var req = event.request;
  // 仅处理 GET，且只处理同源请求
  if(req.method !== 'GET'){ return; }
  var url = new URL(req.url);
  if(url.origin !== location.origin){ return; }

  event.respondWith(
    fetch(req).then(function(resp){
      // 成功则更新缓存（页面/静态资源）
      if(resp && resp.status === 200){
        var copy = resp.clone();
        caches.open(CACHE_NAME).then(function(cache){
          cache.put(req, copy);
        });
      }
      return resp;
    }).catch(function(){
      // 离线时回退缓存
      return caches.match(req).then(function(cached){
        // 页面导航回退到 index.html
        if(cached){ return cached; }
        if(req.mode === 'navigate'){
          return caches.match('./index.html');
        }
        return undefined;
      });
    })
  );
});
