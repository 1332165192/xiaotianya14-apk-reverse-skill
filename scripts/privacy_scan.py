#!/usr/bin/env python3
"""发布前隐私扫描：公开包里不得出现个人信息 / 本机路径 / 账号令牌 / 内部资料标记。

用法:
  python3 scripts/privacy_scan.py             # 扫描仓库（发布前跑，命中 exit 1）
  python3 scripts/privacy_scan.py --root DIR  # 扫描打包后的解压目录
  python3 scripts/privacy_scan.py --fix       # 自动替换命中项（只改 .md/.txt，改完再扫一遍）
  python3 scripts/privacy_scan.py --json      # 输出 JSON

发布流程（make_release --public / CI / github-publish 技能）把它当门禁。
"""
import argparse
import json
import os
import re
import sys

WORKDIR = '/sdcard/Download/' + 'D' + 'SH-Go'

# (正则, 说明, 自动替换值)；自动替换只作用于 .md / .txt
RULES = [
    (re.compile(r'\bPixel 7\b'), '示例机型', '示例机型'),
    (re.compile(r'\b(Samsung|三星)\b'), '示例品牌', '示例品牌'),
    (re.compile(re.escape(WORKDIR) + r'\b'), '本机工作目录', '<输出目录>'),
    (re.compile(r'/root/\.dsh\b'), '本机 home 路径', '$HOME'),
    (re.compile(r'/root/workspace\b'), '本机 home 路径', '$HOME/workspace'),
    (re.compile(r'\bghp_[A-Za-z0-9]{10,}\b|\bgithub_pat_[A-Za-z0-9_]{10,}\b'), 'GitHub 令牌', '<TOKEN>'),
    (re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'), '邮箱地址', 'user@example.com'),
    (re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)'), '手机号', '<手机号>'),
    (re.compile(r'内部资料'), '内部资料标记', '参考资料'),
    (re.compile(r'内部分发版'), '内部资料标记', '分发版'),
    (re.compile(r'内部测试版'), '内部资料标记', '测试版'),
    (re.compile(r'ro\.build\.fingerprint'), '设备指纹', '<fingerprint>'),
]

TEXT_EXT = {'.md', '.txt', '.sh', '.py', '.js', '.json', '.yml', '.yaml', '.svg', '.html', '.xml'}
FIX_EXT = {'.md', '.txt'}
SKIP_DIRS = {'.git', '__pycache__', 'assets', 'node_modules'}
SKIP_FILES = {'scripts/privacy_scan.py'}
EMAIL_ALLOW = ('@example.com', '@example.org', '@example.net')
# 项目公开联系方式（用户明确要求公开）
CONTACT_ALLOW_EMAILS = {'xiaotianya14@gmail.com'}
CONTACT_ALLOW_NUMBERS = {'258605008'}


def iter_files(root):
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            rel = os.path.relpath(os.path.join(dirpath, n), root)
            if rel in SKIP_FILES:
                continue
            if os.path.splitext(n)[1].lower() in TEXT_EXT or n in ('VERSION', 'LICENSE'):
                yield os.path.join(dirpath, n)


def is_placeholder_email(val):
    low = val.lower()
    return low.endswith(EMAIL_ALLOW) or low in ('a@b.com', 'user@example.com', 'hello@example.com') or low in CONTACT_ALLOW_EMAILS


def scan(root, fix=False):
    hits, changed = [], []
    for path in iter_files(root):
        try:
            text = open(path, encoding='utf-8', errors='ignore').read()
        except OSError:
            continue
        new = text
        for rx, reason, rep in RULES:
            for m in rx.finditer(new):
                val = m.group()
                if reason == '邮箱地址' and is_placeholder_email(val):
                    continue
                hits.append({
                    'file': os.path.relpath(path, root),
                    'line': new[:m.start()].count('\n') + 1,
                    'match': val[:60],
                    'reason': reason,
                })
            if fix and os.path.splitext(path)[1].lower() in FIX_EXT:
                def _sub(m, reason=reason, rep=rep):
                    v = m.group()
                    if reason == '邮箱地址' and is_placeholder_email(v):
                        return v
                    return rep
                new = rx.sub(_sub, new)
        if fix and new != text:
            open(path, 'w', encoding='utf-8').write(new)
            changed.append(os.path.relpath(path, root))
    return hits, changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--fix', action='store_true', help='自动替换（只改 .md/.txt）')
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    if a.fix:
        _, changed = scan(root, fix=True)
        if changed:
            print('已自动替换的文件:')
            for f in changed:
                print('  ' + f)
        else:
            print('没有需要自动替换的内容')
        # 修完再扫一遍，剩下的是脚本/二进制里的或无法自动处理的
    hits, _ = scan(root, fix=False)

    if a.json:
        print(json.dumps({'root': root, 'hits': hits}, ensure_ascii=False, indent=2))
    elif hits:
        print(f'✗ 隐私扫描发现 {len(hits)} 处可能泄露：')
        for h in hits[:40]:
            print(f"  {h['file']}:{h['line']}  [{h['reason']}]  {h['match']}")
        if len(hits) > 40:
            print(f'  …还有 {len(hits) - 40} 处')
        print('  处理：改通用示例；或先跑 --fix 自动替换 .md/.txt')
        if a.fix:
            print('  （已跑过 --fix，剩余项需要手工处理）')
    else:
        print('✅ 隐私扫描通过')
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
