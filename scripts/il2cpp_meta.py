#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unity IL2CPP global-metadata.dat 最小解析器（自研，手机端可跑）。

用法:
    python3 il2cpp_meta.py global-metadata.dat
    python3 il2cpp_meta.py global-metadata.dat --strings --min 4
    python3 il2cpp_meta.py global-metadata.dat --json

能力（当前版本）:
  - 校验 magic 0xFAB11BAF、读取 metadata 版本；
  - 提取可打印 UTF-8/UTF-16 字符串（类名/方法名/URL 线索）；
  - 输出字符串数量与可疑 API/URL 线索。
限制:
  - 不做完整 type/method/field 结构还原；完整还原仍在路线图里。
  - 手机端只读文件，不依赖 Il2CppDumper / .NET。
"""
import argparse
import json
import os
import re
import sys

MAGIC = 0xFAB11BAF
URL_RE = re.compile(r'https?://[^\s"\'<>]+')
PRINT_RE = re.compile(rb'[\x20-\x7e]{3,}')
UTF16_RE = re.compile(rb'(?:[\x20-\x7e]\x00){3,}')


def extract_strings(data, min_len):
    out = set()
    for m in PRINT_RE.finditer(data):
        s = m.group(0).decode('ascii', 'ignore')
        if len(s) >= min_len:
            out.add(s)
    for m in UTF16_RE.finditer(data):
        s = m.group(0).decode('utf-16-le', 'ignore')
        if len(s) >= min_len:
            out.add(s)
    return sorted(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='il2cpp_meta.py', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('metadata')
    ap.add_argument('--strings', action='store_true', help='输出提取到的字符串')
    ap.add_argument('--min', type=int, default=4, help='最小字符串长度（默认 4）')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--max-strings', type=int, default=500, help='最多输出条数')
    args = ap.parse_args(argv)

    path = os.path.abspath(args.metadata)
    if not os.path.isfile(path):
        print('错误: 文件不存在: %s' % path, file=sys.stderr)
        return 2
    data = open(path, 'rb').read()
    if len(data) < 8:
        print('错误: 文件过短', file=sys.stderr)
        return 2
    magic = int.from_bytes(data[0:4], 'little')
    version = int.from_bytes(data[4:8], 'little')
    if magic != MAGIC:
        print('错误: 不是 global-metadata.dat（magic=0x%X，期望 0x%X）' % (magic, MAGIC), file=sys.stderr)
        return 1

    strings = extract_strings(data, max(2, args.min))
    urls = [s for s in strings if URL_RE.search(s) and len(s) <= 200]
    result = {
        'file': path, 'size': len(data), 'magic': hex(magic), 'version': version,
        'strings': len(strings), 'urls': urls[:20],
    }
    if args.json:
        result['sample'] = strings[:args.max_strings]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print('文件: %s' % path)
    print('大小: %d B' % len(data))
    print('magic: 0x%X（OK）' % magic)
    print('metadata 版本: %d' % version)
    print('可打印字符串: %d' % len(strings))
    if urls:
        print('URL 线索:')
        for u in urls[:20]:
            print('  - %s' % u)
    if args.strings:
        print('字符串样本:')
        for s in strings[:args.max_strings]:
            print('  %s' % s)
        if len(strings) > args.max_strings:
            print('  ...（共 %d，仅显示前 %d）' % (len(strings), args.max_strings))
    print('说明: 当前只做 header/字符串线索；完整类/方法还原见路线图。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
