#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 index.html 的 EVENTS 数据生成 iCalendar(.ics) 订阅文件。
用法: python3 gen_ics.py <index.html> <输出.ics>
所有时间视为北京时间 (Asia/Shanghai)。
"""
import re
import sys
import html as htmlmod
from datetime import datetime, timedelta

CAL_NAME = "投资日历 · 每日更新市场大事"
PRODID = "-//TouziRili//InvestorCalendar//CN"
TIMEZONE = "Asia/Shanghai"

CATS = {'cn': '国内/政策', 'gl': '海外宏观', 'ai': 'AI/科技', 'ne': '新能源/电池'}


def esc_text(s):
    """RFC 5545 文本转义"""
    return (s.replace('\\', '\\\\')
             .replace(';', '\\;')
             .replace(',', '\\,')
             .replace('\r\n', '\\n')
             .replace('\n', '\\n'))


def esc_param(s):
    """参数值转义（引号包裹）"""
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace(',', '\\,') + '"'


def extract_events(html_src):
    """从 index.html 源码中提取 var EVENTS = {...}; 并解析为 dict[date][list[ev]]"""
    m = re.search(r'var EVENTS = (\{.*?\n\});', html_src, re.S)
    if not m:
        raise RuntimeError('未找到 var EVENTS 定义')
    block = m.group(1)

    events = {}
    # 按日期键切分
    date_re = re.compile(r"'(\d{4}-\d{2}-\d{2})'\s*:\s*\[")
    pos = 0
    dates = list(date_re.finditer(block))
    for i, dm in enumerate(dates):
        date_key = dm.group(1)
        seg_start = dm.end()
        seg_end = dates[i + 1].start() if i + 1 < len(dates) else block.rfind('};')
        seg = block[seg_start:seg_end]
        # 解析该日期下的事件对象数组
        objs = re.findall(r"\{([^{}]*?)\}", seg, re.S)
        lst = []
        for o in objs:
            def field(name, default=None):
                # 字段值统一用单/双引号包裹；time/key 可能为 null/true/false 无引号
                fm = re.search(r"\b" + name + r"\s*:\s*(?:\'([^\']*?)\'|\"([^\"]*?)\"|([^,\s}]+))", o, re.S)
                if not fm:
                    return default
                return (fm.group(1) if fm.group(1) is not None else
                        fm.group(2) if fm.group(2) is not None else fm.group(3))
            time_v = field('time')
            title = field('title')
            cat = field('cat')
            key = field('key')
            desc = field('desc', '')
            if title is None:
                continue
            lst.append({
                'date': date_key,
                'time': time_v if time_v and time_v != 'null' else None,
                'title': htmlmod.unescape(title),
                'cat': cat or 'gl',
                'key': (key == 'true'),
                'desc': htmlmod.unescape(desc),
            })
        events[date_key] = lst
    return events


def build_ics(events, now_dt):
    lines = []
    lines.append('BEGIN:VCALENDAR')
    lines.append('VERSION:2.0')
    lines.append('PRODID:' + PRODID)
    lines.append('CALSCALE:GREGORIAN')
    lines.append('METHOD:PUBLISH')
    lines.append('X-WR-CALNAME:' + esc_text(CAL_NAME))
    lines.append('X-WR-TIMEZONE:' + TIMEZONE)
    lines.append('X-APPLE-CALENDAR-COLOR:#E8A33D')

    uid_seq = 0
    for date_key in sorted(events.keys()):
        for ev in events[date_key]:
            uid_seq += 1
            lines.append('BEGIN:VEVENT')
            lines.append('UID:tzr-' + date_key.replace('-', '') + '-' + str(uid_seq) + '@touzirili.com')
            lines.append('DTSTAMP:' + now_dt.strftime('%Y%m%dT%H%M%SZ'))

            title = ev['title']
            if ev['key']:
                title = '【重点】' + title
            cat_label = CATS.get(ev['cat'], '市场事件')
            summary = title + ' · ' + cat_label

            if ev['time']:
                # 定时事件：按北京时间 TZID 写入，默认时长1小时
                hh, mm = ev['time'].split(':')[:2]
                start = datetime(int(date_key[0:4]), int(date_key[5:7]), int(date_key[8:10]),
                                 int(hh), int(mm))
                end = start + timedelta(hours=1)
                lines.append('DTSTART;TZID=' + TIMEZONE + ':' + start.strftime('%Y%m%dT%H%M%S'))
                lines.append('DTEND;TZID=' + TIMEZONE + ':' + end.strftime('%Y%m%dT%H%M%S'))
            else:
                # 全天事件
                y, mo, d = int(date_key[0:4]), int(date_key[5:7]), int(date_key[8:10])
                end_d = datetime(y, mo, d) + timedelta(days=1)
                lines.append('DTSTART;VALUE=DATE:' + date_key.replace('-', ''))
                lines.append('DTEND;VALUE=DATE:' + end_d.strftime('%Y%m%d'))

            lines.append('SUMMARY:' + esc_text(summary))
            lines.append('CATEGORIES:' + esc_text(cat_label))
            if ev['desc']:
                lines.append('DESCRIPTION:' + esc_text(ev['desc']))
            lines.append('END:VEVENT')
    lines.append('END:VCALENDAR')
    return '\r\n'.join(lines) + '\r\n'


def main():
    if len(sys.argv) < 3:
        print('用法: python3 gen_ics.py <index.html> <输出.ics>', file=sys.stderr)
        sys.exit(1)
    html_path, out_path = sys.argv[1], sys.argv[2]
    with open(html_path, 'r', encoding='utf-8') as f:
        src = f.read()
    events = extract_events(src)
    ics = build_ics(events, datetime.utcnow())
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(ics)
    total = sum(len(v) for v in events.values())
    print(f'OK: 解析 {len(events)} 个日期, 共 {total} 条事件 → {out_path}')


if __name__ == '__main__':
    main()
