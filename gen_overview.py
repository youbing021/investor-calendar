#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_overview.py —— 从 index.html 的 EVENTS 数据自动重建"近期重大市场事件速览"区块。

用法：
    python3 gen_overview.py [index.html] [--out index.html]

规则：
  1. 解析 index.html 中 var EVENTS 的数据（键 YYYY-MM-DD -> [{time,title,cat,key,desc}...]）
  2. 按日期（升序）→ 同日按 time 排序（无 time 的排最后）生成 <li><b>M/D [HH:MM]</b>标题</li>
  3. 有 key 事件（重磅）在标题前保留原文前缀（如【重磅】【休市】【交割日】已在 title 中，直接沿用）
  4. 替换 <section class="event-overview"> 内的 <ul>...</ul>，其余区块（h2、intro、foot）保持不动
  5. 保留 ov-intro 与 ov-foot 说明文字

注意：本脚本只动速览区 <ul>，不影响页面其他任何部分。
"""
import re
import sys
from datetime import datetime

SRC = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
OUT = sys.argv[2] if len(sys.argv) > 2 else SRC


def parse_events(html):
    """从 html 中提取 EVENTS -> { 'YYYY-MM-DD': [{...}] }"""
    m = re.search(r'var EVENTS = (\{.*?\});', html, re.S)
    if not m:
        raise SystemExit('未找到 var EVENTS 数据块')
    body = m.group(1)
    events = {}
    # 按日期键位置切分区间（避免事件对象内 } 嵌套导致正则误判）
    keys = [(mm.start(), mm.group(1)) for mm in re.finditer(r"'(\d{4}-\d{2}-\d{2})'\s*:", body)]
    for i, (pos, d) in enumerate(keys):
        end = keys[i + 1][0] if i + 1 < len(keys) else len(body)
        chunk = body[pos:end]
        items = []
        for tm in re.finditer(r"\{\s*(.*?)\s*\}", chunk, re.S):
            raw = tm.group(1)
            f_time = re.search(r"time:\s*(null|'([^']*)'|\"([^\"]*)\")", raw)
            f_title = re.search(r"title:\s*'([^']*)'", raw)
            if not f_title:
                continue
            t = (f_time.group(2) or f_time.group(3)) if f_time and f_time.group(1) != 'null' else None
            items.append({'time': t, 'title': f_title.group(1)})
        events[d] = items
    return events


def fmt_date(ymd):
    """YYYY-MM-DD -> M/D，如 2026-09-04 -> 9/4"""
    d = datetime.strptime(ymd, '%Y-%m-%d')
    return f'{d.month}/{d.day}'


def build_list(events):
    """生成 <li> 列表 HTML"""
    lis = []
    for date_key in sorted(events.keys()):
        items = sorted(events[date_key], key=lambda x: (x['time'] is None, x['time'] or ''))
        for it in items:
            if it['time']:
                head = f'<b>{fmt_date(date_key)} {it["time"]}</b>'
            else:
                head = f'<b>{fmt_date(date_key)}</b>'
            lis.append(f'<li>{head}{it["title"]}</li>')
    return '\n'.join(lis)


def main():
    html = open(SRC, encoding='utf-8').read()
    events = parse_events(html)
    total = sum(len(v) for v in events.values())
    new_ul = '<ul>\n' + build_list(events) + '\n</ul>'

    # 只替换 event-overview 区块内的 <ul>...</ul>
    sec_start = html.find('<section class="event-overview"')
    if sec_start == -1:
        raise SystemExit('未找到 <section class="event-overview">')
    sec_end = html.find('</section>', sec_start)
    if sec_end == -1:
        raise SystemExit('未找到 section 结束标签')
    sec = html[sec_start:sec_end]
    ul_start = sec.find('<ul>')
    ul_end = sec.find('</ul>', ul_start) + len('</ul>')
    if ul_start == -1 or ul_end == -1:
        raise SystemExit('速览区未找到 <ul> 结构')
    new_sec = sec[:ul_start] + new_ul + sec[ul_end:]
    html = html[:sec_start] + new_sec + html[sec_end:]

    open(OUT, 'w', encoding='utf-8').write(html)
    print(f'OK: 速览区已重建，共 {total} 条事件（{len(events)} 个日期） → {OUT}')


if __name__ == '__main__':
    main()
