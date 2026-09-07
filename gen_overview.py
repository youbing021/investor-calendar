#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_overview.py —— 从 index.html 的 EVENTS 数据自动重建两个区块：
  1. "今日更新"区块（section.today-updates）：只展示当天（今天）日期的事件，含完整 desc 解读，
     每日自动滚动——过了当天即不再显示，主页只放当天的更新。
  2. "近期重大市场事件速览"区块（section.event-overview）：只展示从本周一（含）起的事件标题。

用法：
    python3 gen_overview.py [index.html] [--out index.html]

规则：
  - 解析 index.html 中 var EVENTS 的数据（键 YYYY-MM-DD -> [{time,title,cat,key,desc}...]）
  - 今日更新：提取当天事件（按 time 排序，无 time 排最后），生成 <li><b>M/D [HH:MM]</b>标题 + <div class="tu-desc">描述</div></li>
  - 速览区：只含本周一（含）之后的事件，生成 <li><b>M/D [HH:MM]</b>标题</li>
  - 两个区块的 h2/intro/foot 说明文字保持不动；今日更新区块不存在时自动在速览区前插入

注意：本脚本只动这两个区块，不影响页面其他任何部分。
"""
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
            if f_time:
                t = f_time.group(2) or f_time.group(3) if f_time.group(1) != 'null' else None
            else:
                t = None
            f_cat = re.search(FIELD_RE['cat'], raw)
            f_desc = re.search(FIELD_RE['desc'], raw)
            items.append({
                'time': unquote(t),
                'title': unquote(f_title.group(1)),
                'cat': unquote(f_cat.group(1)) if f_cat else None,
                'desc': unquote(f_desc.group(1)) if f_desc else None,
            })
        events[d] = items
    return events


def fmt_date(ymd):
    """YYYY-MM-DD -> M/D，如 2026-09-07 -> 9/7"""
    d = datetime.strptime(ymd, '%Y-%m-%d')
    return f'{d.month}/{d.day}'


def week_start_key(today=None):
    """返回本周一的 YYYY-MM-DD（含）。以当天所在自然周的周一为起始。"""
    t = today or datetime.now()
    monday = t - timedelta(days=t.weekday())
    return monday.strftime('%Y-%m-%d')


def today_key():
    return datetime.now().strftime('%Y-%m-%d')


def esc(s):
    """HTML 转义，避免 desc 中的特殊字符破坏页面。"""
    if s is None:
        return ''
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def build_today_list(events):
    """生成"今日更新"区块 <li> 列表 HTML（只含当天事件，含 desc）"""
    tk = today_key()
    lis = []
    items = sorted(events.get(tk, []), key=lambda x: (x['time'] is None, x['time'] or ''))
    for it in items:
        if it['time']:
            head = f'<b>{fmt_date(tk)} {esc(it["time"])}</b>'
        else:
            head = f'<b>{fmt_date(tk)}</b>'
        if it.get('desc'):
            lis.append(f'<li>{head}{esc(it["title"])}\n<div class="tu-desc">{esc(it["desc"])}</div></li>')
        else:
            lis.append(f'<li>{head}{esc(it["title"])}</li>')
    if not lis:
        lis.append('<li>今日暂无已确认的公开市场事件安排。</li>')
    return '\n'.join(lis)


def build_overview_list(events):
    """生成速览区 <li> 列表 HTML（只含本周一含之后的事件）"""
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


def replace_section(html, cls, new_inner):
    """按 class 定位 section，替换其内部（整段 section 换成 新 section），返回 (html, 是否找到)"""
    sec_start = html.find(f'<section class="{cls}"')
    if sec_start == -1:
        return html, False
    sec_end = html.find('</section>', sec_start)
    if sec_end == -1:
        raise SystemExit(f'未找到 {cls} 的 section 结束标签')
    sec_end += len('</section>')
    return html[:sec_start] + new_inner + html[sec_end:], True


def main():
    html = open(SRC, encoding='utf-8').read()
    events = parse_events(html)
    tk = today_key()
    ws = week_start_key()
    shown = [d for d in events if d >= ws]
    total = sum(len(events[d]) for d in shown)
    today_n = len(events.get(tk, []))

    # 1) 今日更新区块（整段重建，保证日期/条数最新）
    tu = (
        '<section class="today-updates" aria-label="今日更新">\n'
        '<div class="tu-card">\n'
        f'<h2>今日更新 · {fmt_date(tk)}</h2>\n'
        '<p class="tu-intro">只展示今天影响A股、港股、美股的重要市场事件及解读，每日自动滚动更新。</p>\n'
        '<ul>\n' + build_today_list(events) + '\n</ul>\n'
        '<p class="tu-foot">今日更新 · 仅保留当天内容，次日自动切换</p>\n'
        '</div>\n'
        '</section>'
    )
    html, found = replace_section(html, 'today-updates', tu)
    if not found:
        # 不存在则在速览区前插入
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
    print(f'OK: 今日更新 {today_n} 条（{tk}）· 速览区 {total} 条（本周一 {ws} 起，{len(shown)} 个日期） → {OUT}')


if __name__ == '__main__':
    main()
