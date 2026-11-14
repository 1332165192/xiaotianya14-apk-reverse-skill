#!/usr/bin/env python3
"""校验文档里引用的脚本/文档路径真实存在（吸收「文档命令必须可执行」的思路）。

扫描仓库内 *.md 中出现的 scripts/、references/、docs/、tests/ 路径；
路径不存在则报错。不改任何文件。退出码 0 = 通过。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = re.compile(r'(?<![A-Za-z0-9_])(?:scripts|references|docs|tests)/[A-Za-z0-9_./+-]+')
SKIP_CHARS = set('<>*{}#$|')


def md_files():
    for dirpath, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'assets')]
        for n in names:
            if n.endswith('.md'):
                yield os.path.join(dirpath, n)


def main():
    missing = {}
    for path in md_files():
        try:
            text = open(path, encoding='utf-8', errors='ignore').read()
        except OSError:
            continue
        for m in PAT.finditer(text):
            tok = m.group().rstrip('.,;:)]}')
            if any(ch in tok for ch in SKIP_CHARS):
                continue
            # 跳过 URL 里的路径片段（如 github.com/.../scripts/x）
            if m.start() > 0 and text[m.start() - 1] == '/':
                continue
            if not os.path.exists(os.path.join(ROOT, tok)):
                missing.setdefault(tok, set()).add(os.path.relpath(path, ROOT))
    if missing:
        print(f'✗ 文档里引用了不存在的路径：{len(missing)} 个')
        for tok, files in sorted(missing.items()):
            print(f'  {tok}  ← {", ".join(sorted(files))}')
        return 1
    print('✅ 文档命令/路径检查通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
