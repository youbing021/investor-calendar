#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_overview.py —— 从 index.html 自动重建两个区块：
  1. "今日更新"区块（section.today-updates）：展示当天每2小时定时更新时新增的事件（含 desc 解读），
     按信息更新时间倒序排列（最新在前）；数据源为 TODAY_UPDATES（由 gen_updates.py 维护），
     只保留当天批次，次日自动重置。
  2. "近期重大市场事件速览"区块（section.event-overview）：只展示从本周一（含）起的事件标题。

用法：
    python3 gen_overview.py [index.html] [out]

说明：
  - TODAY_UPDATES 结构：{ "date":"YYYY-MM-DD", "batches":[ {"ts":"HH:MM","items":[{"date","time","title","cat","desc"}...]} ... ] }
  - 两区块的 h2/intro/foot 说明文字保持不动；今日更新区块不存在时自动在速览区前插入
  - 只动这两个区块，不影响页面其他任何部分
"""
import json
import re
import sys
from datetime import datetime, timedelta

SRC = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
OUT = sys.argv[2] if len(sys.argv) > 2 else SRC

FIELD_RE = {
    'time': r"time:\s*(null|'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\")",
    'title': r"title:\s*'((?:[^'\\]|\\.)*)'",
    'cat': r"cat:\s*'((?:[^'\\]|\\.)*)'",
    'desc': r"desc:\s*'((?:[^'\\]|\\.)*)'",
    'source': r"source:\s*'((?:[^'\\]|\\.)*)'",
}


def unquote(s):
    if s is None:
        return None
    return s.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')


def parse_events(html):
    """从 html 中提取 EVENTS -> { 'YYYY-MM-DD': [{time,title,cat,desc}] }"""
    m = re.search(r'var EVENTS = (\{.*?\});', html, re.S)
    if not m:
        raise SystemExit('未找到 var EVENTS 数据块')
    body = m.group(1)
    events = {}
    keys = [(mm.start(), mm.group(1)) for mm in re.finditer(r"'(\d{4}-\d{2}-\d{2})'\s*:", body)]
    for i, (pos, d) in enumerate(keys):
        end = keys[i + 1][0] if i + 1 < len(keys) else len(body)
        chunk = body[pos:end]
        items = []
        for tm in re.finditer(r"\{\s*(.*?)\s*\}", chunk, re.S):
            raw = tm.group(1)
            f_time = re.search(FIELD_RE['time'], raw)
            f_title = re.search(FIELD_RE['title'], raw)
            if not f_title:
                continue
            if f_time and f_time.group(1) != 'null':
                t = f_time.group(2) or f_time.group(3)
            else:
                t = None
            f_cat = re.search(FIELD_RE['cat'], raw)
            f_desc = re.search(FIELD_RE['desc'], raw)
            f_src = re.search(FIELD_RE['source'], raw)
            items.append({
                'time': unquote(t),
                'title': unquote(f_title.group(1)),
                'cat': unquote(f_cat.group(1)) if f_cat else None,
                'desc': unquote(f_desc.group(1)) if f_desc else None,
                'source': unquote(f_src.group(1)) if f_src else None,
            })
        events[d] = items
    return events


def fmt_date(ymd):
    """YYYY-MM-DD -> M/D，如 2026-09-07 -> 9/7"""
    if not ymd:
        return ''
    d = datetime.strptime(ymd, '%Y-%m-%d')
    return f'{d.month}/{d.day}'


def week_start_key(today=None):
    t = today or datetime.now()
    monday = t - timedelta(days=t.weekday())
    return monday.strftime('%Y-%m-%d')


def esc(s):
    if s is None:
        return ''
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def parse_today_updates(html):
    """解析 TODAY_UPDATES -> {'date':..., 'batches':[...]}，缺省返回空结构"""
    m = re.search(r'const TODAY_UPDATES = (\{.*?\});', html, re.S)
    if not m:
        return {'date': None, 'batches': []}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {'date': None, 'batches': []}


def build_today_section(updates, src_index):
    """按 TODAY_UPDATES 渲染"今日更新"区块，批次按 ts 倒序（最新在前）；来源从 EVENTS 反查"""
    date = updates.get('date') or ''
    batches = sorted(updates.get('batches', []), key=lambda b: b.get('ts', ''), reverse=True)
    parts = []
    for b in batches:
        ts = b.get('ts', '')
        items = b.get('items', [])
        if items:
            lis = []
            for it in items:
                d = it.get('date') or date
                if it.get('time'):
                    head = f'<b>{fmt_date(d)} {esc(it["time"])}</b>'
                else:
                    head = f'<b>{fmt_date(d)}</b>'
                src = it.get('source') or src_index.get((d, it.get('title'))) or ''
                src_html = f'<span class="tu-src"> · 来源 · {esc(src)}</span>' if src else ''
                if it.get('desc'):
                    lis.append(f'<li>{head}{esc(it["title"])}{src_html}\n<div class="tu-desc">{esc(it["desc"])}</div></li>')
                else:
                    lis.append(f'<li>{head}{esc(it["title"])}{src_html}</li>')
            ul = '<ul>\n' + '\n'.join(lis) + '\n</ul>'
        else:
            ul = '<p class="tu-none">本次无新增事件。</p>'
        parts.append(f'<div class="tu-batch">\n<div class="tu-ts">{esc(ts)} 更新</div>\n{ul}\n</div>')
    body = '\n'.join(parts)
    if not body:
        body = '<p class="tu-none">今日暂无更新记录。</p>'
    return (
        '<section class="today-updates" aria-label="更新日志">\n'
        '<div class="tu-card">\n'
        f'<h2>更新日志 · {fmt_date(date)}</h2>\n'
        '<p class="tu-intro">每2小时定时更新的新增市场事件及解读，按更新时间倒序展示，次日自动清空。</p>\n'
        + body + '\n'
        '<p class="tu-foot">更新日志 · 仅保留当天定时更新内容，次日自动切换</p>\n'
        '</div>\n'
        '</section>'
    )


def replace_section(html, cls, new_inner):
    sec_start = html.find(f'<section class="{cls}"')
    if sec_start == -1:
        return html, False
    sec_end = html.find('</section>', sec_start)
    if sec_end == -1:
        raise SystemExit(f'未找到 {cls} 的 section 结束标签')
    sec_end += len('</section>')
    return html[:sec_start] + new_inner + html[sec_end:], True


def build_overview_list(events):
    week_start = week_start_key()
    lis = []
    for date_key in sorted(events.keys()):
        if date_key < week_start:
            continue
        items = sorted(events[date_key], key=lambda x: (x['time'] is None, x['time'] or ''))
        for it in items:
            if it['time']:
                head = f'<b>{fmt_date(date_key)} {esc(it["time"])}</b>'
            else:
                head = f'<b>{fmt_date(date_key)}</b>'
            lis.append(f'<li>{head}{esc(it["title"])}</li>')
    return '\n'.join(lis)


def main():
    html = open(SRC, encoding='utf-8').read()
    events = parse_events(html)
    ws = week_start_key()
    shown = [d for d in events if d >= ws]
    total = sum(len(events[d]) for d in shown)

    # 1) 今日更新区块（来源从 EVENTS 反查）
    updates = parse_today_updates(html)
    src_index = {}
    for dkey, items in events.items():
        for it in items:
            src_index[(dkey, it['title'])] = it.get('source') or ''
    tu = build_today_section(updates, src_index)
    html, found = replace_section(html, 'today-updates', tu)
    if not found:
        anchor = '<section class="event-overview"'
        idx = html.find(anchor)
        if idx == -1:
            raise SystemExit('未找到 <section class="event-overview">，无法插入今日更新区块')
        html = html[:idx] + tu + '\n\n' + html[idx:]

    # 2) 速览区（只替换 ul）
    sec_start = html.find('<section class="event-overview"')
    if sec_start == -1:
        raise SystemExit('未找到 <section class="event-overview">')
    sec_end = html.find('</section>', sec_start)
    if sec_end == -1:
        raise SystemExit('未找到 event-overview 结束标签')
    sec = html[sec_start:sec_end]
    ul_start = sec.find('<ul>')
    ul_end = sec.find('</ul>', ul_start) + len('</ul>')
    if ul_start == -1 or ul_end == -1:
        raise SystemExit('速览区未找到 <ul> 结构')
    new_ul = '<ul>\n' + build_overview_list(events) + '\n</ul>'
    new_sec = sec[:ul_start] + new_ul + sec[ul_end:]
    html = html[:sec_start] + new_sec + html[sec_end:]

    open(OUT, 'w', encoding='utf-8').write(html)
    n_batch = len(updates.get('batches', []))
    print(f'OK: 今日更新 {n_batch} 批（{updates.get("date") or "未设置"}）· 速览区 {total} 条（本周一 {ws} 起，{len(shown)} 个日期） → {OUT}')


if __name__ == '__main__':
    main()
