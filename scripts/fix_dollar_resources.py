#!/usr/bin/env python3
"""修复 AGP 8 / Material 新版资源名（$mtrl_*/$avd_* 等）在旧 aapt2 下打包失败的问题。

用法:
    python3 fix_dollar_resources.py <apktool解码目录> [--dry-run]

做三件事（保持一致，资源 ID 不变，smali 里的资源数字引用不受影响）:
1. 把 res/ 下所有以 '$' 开头的文件名去掉前导 '$'
2. 同步改 res/values/public.xml 里的 name="$xxx" 条目
3. 同步替换所有 res/**/*.xml 里对它们的引用（@drawable/$xxx 等）

报错特征: aapt2: "invalid entry name '$mtrl_...'"。
"""
import argparse
import glob
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dec', help='apktool 解码目录')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    res = os.path.join(a.dec, 'res')
    if not os.path.isdir(res):
        print(f'ERROR: {res} 不存在', file=sys.stderr)
        return 2

    renamed = []  # (dir, old_basename, new_basename)
    for root, _dirs, files in os.walk(res):
        for f in files:
            if not f.startswith('$'):
                continue
            new = f[1:]
            renamed.append((root, f, new))
    if not renamed:
        print('没有 $ 开头的资源文件，无需处理')
        return 0

    # 引用替换用的名字集合（去掉扩展名，引用形如 @drawable/mtrl_xxx）
    names = sorted({os.path.splitext(n)[0] for _r, _o, n in renamed}, key=len, reverse=True)

    if not a.dry_run:
        for root, f, new in renamed:
            os.rename(os.path.join(root, f), os.path.join(root, new))
    print(f'rename files: {len(renamed)}' + (' (dry-run)' if a.dry_run else ''))

    # public.xml：条目名是去扩展名的资源名（如 name="$mtrl_xxx"）
    pub = os.path.join(res, 'values', 'public.xml')
    fixed_pub = 0
    if os.path.isfile(pub):
        s = open(pub, encoding='utf-8').read()
        for _r, _o, new in renamed:
            stem = os.path.splitext(new)[0]
            old_attr = f'name="${stem}"'
            if old_attr in s:
                s = s.replace(old_attr, f'name="{stem}"')
                fixed_pub += 1
        if not a.dry_run:
            open(pub, 'w', encoding='utf-8').write(s)
    print(f'public.xml entries fixed: {fixed_pub}')

    # 所有 res XML 的引用
    fixed_refs = 0
    for f in glob.glob(os.path.join(res, '**', '*.xml'), recursive=True):
        if os.path.basename(f) == 'public.xml':
            continue
        s = open(f, encoding='utf-8').read()
        t = s
        for n in names:
            t = t.replace('$' + n, n)
        if t != s:
            fixed_refs += 1
            if not a.dry_run:
                open(f, 'w', encoding='utf-8').write(t)
    print(f'xml files with refs fixed: {fixed_refs}')
    print('完成。重新用 apktool b ... --use-aapt2 打包')
    return 0


if __name__ == '__main__':
    sys.exit(main())
