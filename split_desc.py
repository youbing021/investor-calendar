#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
split_desc.py —— 把 index.html 里 EVENTS 的详情文本（desc）外置成按天的小文件。

为什么：desc 占首页体积 8 成以上（约 900KB-1.2MB），
        而列表首屏只需要标题，详情是点开才看的。
做法：
  - 每条事件的 desc 写入 data/desc/<YYYY-MM-DD>.json（键为标题，值为 desc）
  - index.html 内的 EVENTS 只保留 time/title/cat/key/source 等轻量字段
  - 兼容两种写法：JS 单引号对象 与 JSON 双引号对象
  - 幂等：可反复运行；已外置的事件不会重复写入

用法：
  python3 split_desc.py [index.html] [--dry]

配套：
  - index.html 运行时用 descOf()/loadDescs() 按天懒加载；
  - pub_wechat.py 生成公众号稿件时会自动合并这些 JSON。
"""
import json
import os
import re
import sys

ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
SRC = ARGS[0] if ARGS else 'index.html'
DRY = '--dry' in sys.argv
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(SRC)), 'data', 'desc')

DATE_KEY = re.compile(r"'(\d{4}-\d{2}-\d{2})'\s*:")
OBJ_RE = re.compile(r'\{\s*(.*?)\s*\}', re.S)
# desc 字段：单引号或双引号，支持转义
DESC_RE = re.compile(r"""["']?desc["']?\s*:\s*(?:'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")""", re.S)
TITLE_RE = re.compile(r"""["']?title["']?\s*:\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")""", re.S)


def decode(literal):
    """'...' 或 "..." → 真实文本；已是裸文本时直接反转义"""
    lit = literal.strip()
    if lit[:1] in ("'", '"') and lit[-1:] == lit[:1] and len(lit) >= 2:
        if lit[0] == '"':
            try:
                return json.loads(lit)
            except Exception:
                pass
        inner = lit[1:-1]
    else:
        inner = lit
    inner = inner.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')
    inner = inner.replace('\\n', '\n')
    return inner


def parse_events(body):
    keys = [(m.start(), m.group(1)) for m in DATE_KEY.finditer(body)]
    out = {}
    for i, (pos, d) in enumerate(keys):
        end = keys[i + 1][0] if i + 1 < len(keys) else len(body)
        chunk = body[pos:end]
        for tm in OBJ_RE.finditer(chunk):
            raw = tm.group(1)
            mt = TITLE_RE.search(raw)
            if not mt:
                continue
            title = decode(mt.group(1) if mt.group(1) is not None else mt.group(2))
            md = DESC_RE.search(raw)
            desc = decode(md.group(0).split(':', 1)[1].strip()) if md else ''
            out.setdefault(d, []).append({'title': title.strip(), 'desc': desc})
    return out


def strip_desc(raw):
    """从单个事件对象文本里删掉 desc 字段（连同前置/后置逗号），其余字节保持不变"""
    m = DESC_RE.search(raw)
    if not m:
        return raw, ''
    desc = decode(m.group(0).split(':', 1)[1].strip())
    start, end = m.span()
    left = raw.rfind(',', 0, start)
    if left != -1 and not raw[left:start].strip(' '):
        raw = raw[:left] + raw[end:]
    else:
        right = raw.find(',', end)
        if right != -1:
            raw = raw[:start] + raw[right + 1:]
        else:
            raw = raw[:start] + raw[end:]
    raw = re.sub(r',\s*,', ',', raw)
    raw = re.sub(r',\s*$', '', raw)
    return raw.strip(), desc


def main():
    html = open(SRC, encoding='utf-8').read()
    m = re.search(r'var EVENTS = (\{.*?\});', html, re.S)
    if not m:
        raise SystemExit('未找到 var EVENTS')
    body = m.group(1)

    before = parse_events(body)
    total_before = sum(len(v) for v in before.values())

    payloads = {}
    for d, items in before.items():
        mp = {e['title']: e['desc'] for e in items if e['desc']}
        if mp:
            payloads[d] = mp

    # 逐日期重建：只动 chunk 内的事件对象
    keys = [(mm.start(), mm.group(1)) for mm in DATE_KEY.finditer(body)]
    pieces, cursor = [], 0
    for i, (pos, d) in enumerate(keys):
        end = keys[i + 1][0] if i + 1 < len(keys) else len(body)
        pieces.append(body[cursor:pos])
        chunk = body[pos:end]

        def repl(mm):
            inner, _ = strip_desc(mm.group(1))
            return '{' + inner + '}'

        pieces.append(OBJ_RE.sub(repl, chunk))
        cursor = end
    pieces.append(body[cursor:])
    new_body = ''.join(pieces)

    # 校验
    after = parse_events(new_body)
    if sum(len(v) for v in after.values()) != total_before:
        raise SystemExit('校验失败：条数不一致')
    if [e['title'] for v in before.values() for e in v] != [e['title'] for v in after.values() for e in v]:
        raise SystemExit('校验失败：标题序列发生变化')
    if 'desc' in new_body:
        raise SystemExit('校验失败：仍残留 desc 字段')
    if any(e['desc'] for v in after.values() for e in v):
        raise SystemExit('校验失败：解析后仍有 desc')

    size_before, size_after = len(body.encode()), len(new_body.encode())
    print(f'事件 {total_before} 条；EVENTS {size_before/1024:.0f}KB -> {size_after/1024:.0f}KB')

    if DRY:
        print('dry-run：未写入')
        return

    os.makedirs(OUTDIR, exist_ok=True)
    for d, mp in payloads.items():
        path = os.path.join(OUTDIR, d + '.json')
        merged = {}
        # 合并已有详情，避免只新增一条时把该日期原有 desc 覆盖丢失
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8') as f:
                    merged = json.load(f)
            except Exception:
                merged = {}
        merged.update(mp)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, separators=(',', ':'))
    # 只清理“已不在事件库里”的旧日期文件；已有的按天文件不动（幂等，反复跑不会丢数据）
    keep = {d + '.json' for d in before.keys()}
    for fn in os.listdir(OUTDIR):
        if fn.endswith('.json') and fn not in keep:
            os.remove(os.path.join(OUTDIR, fn))

    html = html[:m.start(1)] + new_body + html[m.end(1):]
    open(SRC, 'w', encoding='utf-8').write(html)
    print(f'已外置 {len(payloads)} 天的 desc → {OUTDIR}')
    print(f'index.html 体积：{len(html.encode())/1024:.0f}KB')


if __name__ == '__main__':
    main()
