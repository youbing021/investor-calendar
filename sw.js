/* ============================================
 * 投资日历 Service Worker v17（卸载版 / 退场脚本）
 * 背景：缓存优先 + skipWaiting + controllerchange 自动刷新那一套，
 *       在 iOS Safari 上会让页面长期停在旧缓存、甚至反复重载，
 *       表现就是“一直打不开、只有 logo 和转圈”。
 * 方案：本版不做任何缓存拦截，只把历史缓存清干净并注销自己，
 *       之后完全交给 HTTP 缓存（页面每次拿最新的，压缩后约 115KB）。
 * ============================================ */
var CACHE_PREFIXES = ['investor-calendar-'];

self.addEventListener('install', function(event){
  self.skipWaiting();
});

self.addEventListener('activate', function(event){
  event.waitUntil(
    caches.keys().then(function(keys){
      return Promise.all(
        keys.filter(function(k){
          return CACHE_PREFIXES.some(function(p){ return k.indexOf(p) === 0; });
        }).map(function(k){ return caches.delete(k); })
      );
    }).then(function(){
      return self.registration.unregister();
    }).then(function(){
      return self.clients.matchAll({type: 'window'});
    }).then(function(list){
      list.forEach(function(client){
        try{ if(client.navigate){ client.navigate(client.url); } }catch(e){}
      });
    }).catch(function(){})
  );
});
