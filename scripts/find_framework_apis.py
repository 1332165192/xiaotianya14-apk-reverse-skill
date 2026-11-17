#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 Kotlin 常见框架线索：Ktor / Apollo GraphQL / Koin。

用法:
    python3 find_framework_apis.py <jadx输出目录|apktool目录|单文件> [--ktor] [--apollo] [--koin] [--all] [--json]

说明:
  - Ktor: HttpClient、install(ContentNegotiation)、url("...")、.get/.post/.request
  - Apollo: ApolloClient、query/mutation、.graphql 文件、Subscription
  - Koin: module { single/factory/viewModel }、org.koin 导入
  只做线索定位，不保证覆盖所有写法；字符串加密时需动态分析。
"""
import argparse
import json
import os
import re
import sys

GROUPS = {
    'ktor': ('Ktor', [
        ('HttpClient', re.compile(r'\bHttpClient\s*\(')),
        ('ContentNegotiation', re.compile(r'\bContentNegotiation\b')),
        ('url()', re.compile(r'\.url\s*\(\s*"([^"]*)"')),
        ('get/post/request', re.compile(r'\.(?:get|post|put|delete|patch|request)\s*\(')),
        ('io.ktor', re.compile(r'\bio\.ktor\.')),
    ]),
    'apollo': ('Apollo GraphQL', [
        ('ApolloClient', re.compile(r'\bApolloClient\b')),
        ('query/mutation', re.compile(r'\b(?:query|mutation|subscription)\s*\(')),
        ('graphql path', re.compile(r'\.graphql\b', re.I)),
        ('com.apollographql', re.compile(r'\bcom\.apollographql\.')),
    ]),
    'koin': ('Koin', [
        ('module {}', re.compile(r'\bmodule\s*\{')),
        ('single/factory/viewModel', re.compile(r'\b(?:single|factory|viewModel|scoped)\s*(?:<[^>]*>)?\s*\{')),
        ('org.koin', re.compile(r'\borg\.koin\.')),
    ]),
}
SKIP = {'.git', 'build', 'node_modules', '__pycache__', '.gradle'}
MAX_FILE = 8 * 1024 * 1024


def iter_files(path):
    if os.path.isfile(path):
        yield path
        return
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for n in files:
            if n.lower().endswith(('.java', '.kt', '.smali', '.xml', '.graphql')):
                yield os.path.join(root, n)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='find_framework_apis.py', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('path', nargs='?', default='.')
    ap.add_argument('--ktor', action='store_true')
    ap.add_argument('--apollo', action='store_true')
    ap.add_argument('--koin', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)

    enabled = [g for g in GROUPS if args.all or getattr(args, g)]
    if not enabled:
        enabled = list(GROUPS)
    result = {g: [] for g in enabled}
    for fp in iter_files(args.path):
        try:
            if os.path.getsize(fp) > MAX_FILE:
                continue
            text = open(fp, 'r', encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        lines = text.splitlines()
        for g in enabled:
            title, pats = GROUPS[g]
            for kind, rx in pats:
                for i, line in enumerate(lines, 1):
                    m = rx.search(line)
                    if not m:
                        continue
                    val = m.group(1) if m.groups() else ''
                    result[g].append({
                        'kind': kind, 'value': val.strip()[:200],
                        'file': os.path.relpath(fp, args.path if os.path.isdir(args.path) else os.path.dirname(fp) or '.'),
                        'line': i, 'snippet': line.strip()[:200],
                    })
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    total = 0
    for g in enabled:
        title, _ = GROUPS[g]
        rows = result[g]
        total += len(rows)
        print('\n## %s（%d 处）' % (title, len(rows)))
        seen = set()
        for r in rows:
            key = (r['kind'], r['value'], r['file'])
            if key in seen:
                continue
            seen.add(key)
            print('  [%s] %s:%d  %s' % (r['kind'], r['file'], r['line'], r['snippet']))
    print('\n合计: %d 处线索（只做定位，需结合 jadx/Frida 验证）' % total)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
