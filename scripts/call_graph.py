#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态 Java/Kotlin 调用链追踪（轻量、只依赖标准库）。

用法:
    python3 call_graph.py <jadx输出目录> [--entry Activity|Service|Receiver|.*] [--depth 4]
    python3 call_graph.py src/ --entry '.*Activity' --json

做法:
  - 扫 .java/.kt，识别 class 与 method（按花括号配平取方法体）；
  - 方法体内出现的 `foo(` 作为调用边，优先解析同类方法，再按唯一方法名解析；
  - 从入口方法（onCreate/onClick/main 或类名匹配）做 DFS，输出调用链。
限制:
  - 静态近似：反射、接口分派、lambda、R8 混淆会导致漏边；
  - 只用于快速定位链路，结论需用 Frida/动态栈复核。
"""
import argparse
import json
import os
import re
import sys

CLASS_RE = re.compile(r'\b(?:class|interface|enum)\s+([A-Za-z_$][\w$]*)')
METHOD_RE = re.compile(
    r'^\s*(?:(?:public|private|protected|static|final|abstract|synchronized|native|default)\s+)*'
    r'(?:[\w$<>\[\].?]+\s+)?([A-Za-z_$][\w$]*)\s*\([^;{}]*\)\s*(?:throws[^{]+)?\{')
CALL_RE = re.compile(r'([A-Za-z_$][\w$]*)\s*\(')
SKIP_CALL = {'if', 'for', 'while', 'switch', 'catch', 'return', 'new', 'else',
             'super', 'this', 'try', 'synchronized', 'throw', 'case'}
SKIP_DIR = {'.git', 'build', 'node_modules', '__pycache__'}


def parse_file(path):
    text = open(path, 'r', encoding='utf-8', errors='replace').read()
    lines = text.splitlines()
    cls = None
    methods = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = CLASS_RE.search(line)
        if m and cls is None:
            cls = m.group(1)
        mm = METHOD_RE.match(line)
        if mm:
            name = mm.group(1)
            depth = line.count('{') - line.count('}')
            body = [line]
            j = i
            while depth > 0 and j + 1 < len(lines):
                j += 1
                body.append(lines[j])
                depth += lines[j].count('{') - lines[j].count('}')
            methods.append({'name': name, 'line': i + 1, 'body': '\n'.join(body)})
            i = j
        i += 1
    return cls, methods


def main(argv=None):
    ap = argparse.ArgumentParser(prog='call_graph.py', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('path')
    ap.add_argument('--entry', default='Activity|Service|Receiver|Application',
                    help='入口类名正则（默认 Activity|Service|Receiver|Application）')
    ap.add_argument('--depth', type=int, default=4)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    if not os.path.isdir(args.path):
        print('错误: 需要目录: %s' % args.path, file=sys.stderr)
        return 2
    entry_re = re.compile(args.entry)

    classes = {}
    for root, dirs, files in os.walk(args.path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR]
        for n in files:
            if not n.lower().endswith(('.java', '.kt')):
                continue
            fp = os.path.join(root, n)
            try:
                cls, methods = parse_file(fp)
            except OSError:
                continue
            if cls:
                classes.setdefault(cls, {'file': fp, 'methods': []})['methods'].extend(methods)

    # 方法名索引
    by_name = {}
    for cls, info in classes.items():
        for m in info['methods']:
            by_name.setdefault(m['name'], []).append((cls, m))

    def edges_of(cls, method):
        out = []
        for name in CALL_RE.findall(method['body']):
            if name in SKIP_CALL or name == method['name']:
                continue
            if name in [m['name'] for m in classes.get(cls, {}).get('methods', [])]:
                out.append((cls, name))
            elif len(by_name.get(name, [])) == 1:
                out.append((by_name[name][0][0], name))
        # 去重
        return sorted(set(out))

    def label(edge):
        return '%s.%s' % edge

    chains = []
    seen_global = set()
    for cls, info in classes.items():
        if not entry_re.search(cls):
            continue
        for m in info['methods']:
            if m['name'] not in ('onCreate', 'onClick', 'main', 'onReceive', 'onStartCommand',
                                 'onBind', 'onResume'):
                continue
            start = (cls, m['name'])
            stack = [(start, [start])]
            while stack:
                (c, mn), path = stack.pop()
                if len(path) > args.depth:
                    chains.append(path)
                    continue
                method = next((x for x in classes[c]['methods'] if x['name'] == mn), None)
                if not method:
                    chains.append(path)
                    continue
                nxt = edges_of(c, method)
                if not nxt:
                    chains.append(path)
                for e in nxt:
                    if e in path:
                        continue
                    stack.append((e, path + [e]))
            # 只保留从入口出发的链
    # 简化：用 BFS 生成链（上面 DFS 可能重复，去重）
    uniq = []
    seen = set()
    for p in chains:
        key = tuple(label(x) for x in p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    uniq.sort(key=lambda p: (-len(p), [label(x) for x in p]))
    uniq = uniq[:200]

    if args.json:
        print(json.dumps([{'chain': [label(x) for x in p]} for p in uniq], ensure_ascii=False, indent=2))
    else:
        print('类: %d，方法: %d，入口链: %d' % (len(classes), sum(len(v['methods']) for v in classes.values()), len(uniq)))
        for p in uniq[:50]:
            print('  ' + ' -> '.join(label(x) for x in p))
        if len(uniq) > 50:
            print('  ...（仅显示前 50 条，用 --json 取全部）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
