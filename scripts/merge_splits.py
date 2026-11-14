#!/usr/bin/env python3
"""合并 AAB 拆分包（apktool 解码后的目录）进 base 解码目录。

用法:
    python3 merge_splits.py --base dec_base --splits dec_split_config.zh dec_split_config.en dec_split_config.xxxhdpi

规则:
- 拷贝 split 的 res/ 子目录（跳过 split 自己的 values/，它通常只有 public.xml，覆盖会破坏 base 资源表）
- 拷贝 split 的 lib/（ABI split 的原生库）
- 不拷贝 AndroidManifest.xml；拆分包标记需另行从 base 清单删除
- 已存在的同名文件不覆盖（base 优先）
"""
import argparse
import os
import shutil
import sys


def merge_one(base, split):
    n_res = n_lib = 0
    sres = os.path.join(split, 'res')
    if os.path.isdir(sres):
        for d in sorted(os.listdir(sres)):
            if d == 'values':
                continue  # split 的 values/ 只有 public.xml，绝不覆盖 base
            sp = os.path.join(sres, d)
            if not os.path.isdir(sp):
                continue
            dst = os.path.join(base, 'res', d)
            os.makedirs(dst, exist_ok=True)
            for f in sorted(os.listdir(sp)):
                dstf = os.path.join(dst, f)
                if not os.path.exists(dstf):
                    shutil.copy2(os.path.join(sp, f), dstf)
                    n_res += 1
    slib = os.path.join(split, 'lib')
    if os.path.isdir(slib):
        for root, _dirs, files in os.walk(slib):
            rel = os.path.relpath(root, split)
            dst = os.path.join(base, rel)
            os.makedirs(dst, exist_ok=True)
            for f in files:
                dstf = os.path.join(dst, f)
                if not os.path.exists(dstf):
                    shutil.copy2(os.path.join(root, f), dstf)
                    n_lib += 1
    return n_res, n_lib


def main():
    ap = argparse.ArgumentParser(description='合并拆分包解码目录到 base')
    ap.add_argument('--base', required=True, help='base 的 apktool 解码目录')
    ap.add_argument('--splits', nargs='+', required=True, help='各 split 的 apktool 解码目录')
    a = ap.parse_args()
    if not os.path.isdir(os.path.join(a.base, 'res')):
        print(f'ERROR: {a.base} 不像 apktool 解码目录（缺 res/）', file=sys.stderr)
        return 2
    ok = True
    for s in a.splits:
        if not os.path.isdir(s):
            print(f'skip missing: {s}')
            ok = False
            continue
        r, l = merge_one(a.base, s)
        print(f'{s}: res={r} lib={l}')
    libdir = os.path.join(a.base, 'lib')
    print('merged lib:', sorted(os.listdir(libdir)) if os.path.isdir(libdir) else 'none')
    vals = [d for d in os.listdir(os.path.join(a.base, 'res')) if d.startswith('values-')]
    print('values-* dirs:', vals)
    print('下一步: 删清单里 android:requiredSplitTypes / android:splitTypes 后打包')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
