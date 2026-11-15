#!/usr/bin/env python3
"""发布前隐私扫描：公开包里不得出现个人信息 / 本机路径 / 内部资料标记。

用法:
  python3 scripts/privacy_scan.py            # 扫描仓库（发布前跑）
  python3 scripts/privacy_scan.py --root DIR # 扫描打包后的解压目录
  python3 scripts/privacy_scan.py --json     # 输出 JSON

命中即 exit 1；发布流程（make_release / CI / github-publish 技能）应把它当门禁。
"""
import argparse
import json
import os
import re
import sys

# (正则, 说明, 是否允许出现在示例里)
WORKDIR = '/sdcard/Download/' + 'D' + 'SH-Go'

RULES = [
    (r'\bPLC110\b', '真实设备型号 PLC110（换成“示例机型”）', False),
    (r'\b(OnePlus|一加)\b', '品牌名（换成通用表述）', False),
    (re.escape(WORKDIR) + r'\b', '本机工作目录（换成 <输出目录>）', False),
    (r'/root/\.dsh\b|/root/workspace\b', '本机 home 路径（换成通用路径）', False),
    (r'\bghp_[A-Za-z0-9]{10,}\b|\bgithub_pat_[A-Za-z0-9_]{10,}\b', 'GitHub 令牌', False),
    (r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '邮箱地址', False),
    (r'(?<!\d)1[3-9]\d{9}(?!\d)', '手机号', False),
    (r'内部资料|内部分发版|内部测试版', '内部资料标记', False),
    (r'ro\.build\.fingerprint|Build\.FINGERPRINT\s*=', '设备指纹', False),
]

TEXT_EXT = {'.md', '.txt', '.sh', '.py', '.js', '.json', '.yml', '.yaml', '.svg', '.html', '.xml'}
SKIP_DIRS = {'.git', '__pycache__', 'assets', 'node_modules'}
SKIP_FILES = {'scripts/privacy_scan.py'}


def iter_files(root):
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            rel = os.path.relpath(os.path.join(dirpath, n), root)
            if rel in SKIP_FILES:
                continue
            if os.path.splitext(n)[1].lower() in TEXT_EXT or n in ('VERSION', 'LICENSE'):
                yield os.path.join(dirpath, n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    hits = []
    for path in iter_files(root):
        try:
            text = open(path, encoding='utf-8', errors='ignore').read()
        except OSError:
            continue
        for pat, desc, _ in RULES:
            for m in re.finditer(pat, text):
                val = m.group()
                if desc == '邮箱地址':
                    low = val.lower()
                    if low.endswith(('@example.com', '@example.org', '@example.net')) or val in ('a@b.com', 'user@example.com', 'hello@example.com'):
                        continue
                line = text[:m.start()].count('\n') + 1
                hits.append({
                    'file': os.path.relpath(path, root),
                    'line': line,
                    'match': val[:60],
                    'reason': desc,
                })
    if a.json:
        print(json.dumps({'root': root, 'hits': hits}, ensure_ascii=False, indent=2))
    else:
        if hits:
            print(f'✗ 隐私扫描发现 {len(hits)} 处可能泄露：')
            for h in hits[:40]:
                print(f"  {h['file']}:{h['line']}  [{h['reason']}]  {h['match']}")
            if len(hits) > 40:
                print(f'  …还有 {len(hits) - 40} 处')
            print('  处理：改成通用示例（设备型号→示例机型、本机路径→<输出目录>、账号/令牌删除）')
        else:
            print('✅ 隐私扫描通过')
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
