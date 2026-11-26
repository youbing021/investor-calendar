#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成手机极简版 lite.html：今日 + 未来 7 天事件静态直出，无 fetch、无动画、无外部数据。
用法： python3 gen_lite.py index.html lite.html [天数=7]
数据源：index.html 中的 var EVENTS 块（desc 已外置，这里只要 time/title/cat/source）
"""
import json, subprocess, sys, datetime, re

def load_events(src):
    h = open(src, encoding='utf-8').read()
    i = h.index('var EVENTS')
    j = h.index('{', i)
    d = 0
    for k in range(j, len(h)):
        if h[k] == '{':
            d += 1
        elif h[k] == '}':
            d -= 1
            if d == 0:
                end = k + 1
                break
    open('/tmp/_ev_dump.js', 'w').write('module.exports=' + h[j:end] + ';')
    out = subprocess.check_output(['node', '-e',
        "process.stdout.write(JSON.stringify(require('/tmp/_ev_dump.js')))"]).decode('utf-8')
    return json.loads(out)

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0e1218;color:#e6edf7;font:16px/1.55 -apple-system,"PingFang SC",sans-serif;padding:14px 14px 40px}
h1{font-size:19px;font-weight:600;margin-bottom:2px}
.sub{font-size:12px;color:#7f8ea3;margin-bottom:14px}
.day{margin-top:18px}
.day h2{font-size:14px;color:#9fb2c9;font-weight:600;border-left:3px solid #e8543f;padding-left:8px;margin-bottom:8px}
.item{padding:9px 0;border-bottom:1px solid #1c2531}
.item .t{font-size:11px;color:#7f8ea3;letter-spacing:.5px}
.item .n{font-size:15px;margin-top:2px}
.cat{display:inline-block;font-size:11px;color:#8fb4ff;background:#16233a;border-radius:4px;padding:1px 6px;margin-left:6px}
.src{font-size:11px;color:#65748a;margin-top:3px}
.none{color:#65748a;font-size:14px;padding:6px 0}
a.full{display:block;margin-top:22px;text-align:center;color:#8fb4ff;font-size:13px;text-decoration:none}
"""

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
    out = sys.argv[2] if len(sys.argv) > 2 else 'lite.html'
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    ev = load_events(src)
    today = datetime.date.today()
    order = [today + datetime.timedelta(days=i) for i in range(0, days + 1)]

    parts = []
    total = 0
    for d in order:
        iso = d.isoformat()
        items = ev.get(iso, [])
        items = sorted(items, key=lambda x: (0 if x.get('key') else 1, x.get('time') or '99:99'))
        total += len(items)
        label = f"{d.month}/{d.day}"
        if d == today:
            label += ' · 今天'
        elif d == today + datetime.timedelta(days=1):
            label += ' · 明天'
        parts.append(f'<div class="day"><h2>{label}（{len(items)}项）</h2>')
        if not items:
            parts.append('<div class="none">暂无收录事件</div>')
        for it in items:
            t = (it.get('time') or '').strip()
            if t and t not in ('00:00', '全天'):
                tm = f'<span class="t">{t}</span><br>'
            else:
                tm = '<span class="t">全天</span><br>'
            cat = f'<span class="cat">{it["cat"]}</span>' if it.get('cat') else ''
            src = f'<div class="src">来源：{it["source"]}</div>' if it.get('source') else ''
            parts.append(f'<div class="item">{tm}<div class="n">{it["title"]}{cat}</div>{src}</div>')
        parts.append('</div>')

    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>投资日历 · 手机简版</title>
<style>{CSS}</style></head>
<body>
<h1>投资日历 · 手机简版</h1>
<div class="sub">{today.month}/{today.day} 更新 · 今日起 {days+1} 天 共 {total} 项 · 不荐股</div>
{''.join(parts)}
<a class="full" href="./">打开完整版（事件详情）</a>
</body></html>"""
    open(out, 'w', encoding='utf-8').write(html)
    print(f'{out} 生成完成：{total} 项，{len(html.encode())} 字节')

if __name__ == '__main__':
    main()
