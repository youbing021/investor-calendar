#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_updates.py —— 维护 index.html 中的 TODAY_UPDATES（今日更新日志）。

每次定时更新后调用，把"本次新增的事件"追加为当天的一个批次：
    python3 gen_updates.py index.html index.html --added '[{"date":"2026-09-08","time":null,"title":"...","cat":"gl","desc":"..."}]'

规则：
  1. TODAY_UPDATES = { "date":"YYYY-MM-DD", "batches":[ {"ts":"HH:MM","items":[...]} ... ] }
  2. 若记录日期不是今天 → 重置为今天的空批次列表（次日自动清空，主页只放当天的更新）
  3. 追加本次批次（ts 取当前时间 HH:MM）；--added 为空数组或不传时也记录批次（渲染为"本次无新增"）
  4. 同批次内按 title 去重
  5. desc 内英文直引号统一使用中文引号
"""
import json
import re
import sys
from datetime import datetime

SRC = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
OUT = sys.argv[2] if len(sys.argv) > 2 else SRC
ADDED = None
if '--added' in sys.argv:
    ADDED = sys.argv[sys.argv.index('--added') + 1]
US_REVIEW = None
if '--us-review' in sys.argv:
    US_REVIEW = sys.argv[sys.argv.index('--us-review') + 1]


def main():
    html = open(SRC, encoding='utf-8').read()
    today = datetime.now().strftime('%Y-%m-%d')
    now_hm = datetime.now().strftime('%H:%M')

    m = re.search(r'const TODAY_UPDATES = (\{.*?\});', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
        except Exception:
            data = {}
    else:
        data = {}

    # 次日重置（同时清空美股复盘置顶）
    if data.get('date') != today:
        data = {'date': today, 'batches': [], 'us_review': None}
    elif 'us_review' not in data:
        data['us_review'] = None

    # 市场复盘置顶内容（仅当日有效：6:00 美股复盘 / 16:00 A股复盘，相互覆盖）
    if US_REVIEW:
        try:
            ur = json.loads(US_REVIEW)
        except Exception as e:
            raise SystemExit(f'--us-review JSON 解析失败: {e}')
        data['us_review'] = {'ts': now_hm, 'label': ur.get('label', '市场复盘'), 'title': ur.get('title', ''), 'desc': ur.get('desc', '')}

    if ADDED:
        try:
            items = json.loads(ADDED)
        except Exception as e:
            raise SystemExit(f'--added JSON 解析失败: {e}')
        # 去重（同批内按 title）
        seen, uniq = set(), []
        for it in items:
            key = it.get('title', '')
            if key in seen:
                continue
            seen.add(key)
            uniq.append({k: it.get(k) for k in ('date', 'time', 'title', 'cat', 'desc')})
        items = uniq
    else:
        items = []

    # 仅显式传 --added 时追加批次；仅 --us-review（复盘）不产生空批次
    if '--added' in sys.argv:
        data['batches'].append({'ts': now_hm, 'items': items})
    # 仅保留最近 12 批（每2小时一天最多12次），防止异常堆积
    data['batches'] = data['batches'][-12:]

    blob = json.dumps(data, ensure_ascii=False, indent=1)
    if m:
        html = html[:m.start()] + f'const TODAY_UPDATES = {blob};' + html[m.end():]
    else:
        anchor = 'var EVENTS = '
        idx = html.find(anchor)
        if idx == -1:
            raise SystemExit('未找到 var EVENTS，无法插入 TODAY_UPDATES')
        html = html[:idx] + f'const TODAY_UPDATES = {blob};\n\n' + html[idx:]

    open(OUT, 'w', encoding='utf-8').write(html)
    print(f'OK: 今日更新已记录批次 {now_hm}（{len(items)} 条新增，累计 {len(data["batches"])} 批，日期 {today}） → {OUT}')


if __name__ == '__main__':
    main()
