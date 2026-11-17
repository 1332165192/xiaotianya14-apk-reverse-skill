#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解包 XAPK / APKS / JAR / AAR（并可选继续用 jadx/decode.sh 分析）。

用法:
    python3 unpack_archive.py <file.xapk|.apks|.jar|.aar|.zip> [-o OUT] [--decode]
    python3 unpack_archive.py app.xapk -o /tmp/app --decode

说明:
  - XAPK/APKS: 解压后列出 *.apk；多 APK 时提示用 merge_splits.py 合并。
  - JAR: 直接交给 jadx（jadx 原生支持 jar）。
  - AAR: 解压后拿 classes.jar 交给 jadx；res/ 与 AndroidManifest.xml 保留。
  - 只做格式解包与调用现有工具，不修改原文件。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile

TOOL = 'unpack_archive.py'
ARCHIVE_EXT = {'.xapk', '.apks', '.jar', '.aar', '.zip'}


def safe_extract(zpath, out):
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            name = info.filename
            if name.startswith('/') or '..' in name.split('/'):
                raise ValueError('拒绝可疑路径: %s' % name)
            target = os.path.join(out, name)
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target) or out, exist_ok=True)
            with z.open(info) as src, open(target, 'wb') as dst:
                shutil.copyfileobj(src, dst)


def find_files(root, suffix):
    hits = []
    for dirpath, _dirs, names in os.walk(root):
        for n in names:
            if n.lower().endswith(suffix):
                hits.append(os.path.join(dirpath, n))
    return sorted(hits)


def run(cmd):
    print('+ ' + ' '.join(cmd))
    return subprocess.call(cmd)


def main(argv=None):
    ap = argparse.ArgumentParser(prog=TOOL, description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('archive')
    ap.add_argument('-o', '--out', help='输出目录（默认 <文件名>_unpacked）')
    ap.add_argument('--decode', action='store_true', help='解包后调用 jadx/decode.sh 继续分析')
    ap.add_argument('--json', action='store_true', help='输出 JSON 摘要')
    args = ap.parse_args(argv)

    src = os.path.abspath(args.archive)
    if not os.path.isfile(src):
        print('错误: 文件不存在: %s' % src, file=sys.stderr)
        return 2
    ext = os.path.splitext(src)[1].lower()
    if ext not in ARCHIVE_EXT:
        print('错误: 只支持 %s，收到 %s' % (', '.join(sorted(ARCHIVE_EXT)), ext), file=sys.stderr)
        return 2

    out = os.path.abspath(args.out or (os.path.splitext(src)[0] + '_unpacked'))
    if os.path.exists(out):
        print('错误: 输出目录已存在，换一个或先删除: %s' % out, file=sys.stderr)
        return 2
    os.makedirs(out)

    try:
        safe_extract(src, out)
    except (zipfile.BadZipFile, ValueError) as exc:
        print('错误: %s' % exc, file=sys.stderr)
        return 2

    result = {'archive': src, 'out': out, 'type': ext.lstrip('.'), 'apks': [], 'jars': []}
    if ext in ('.xapk', '.apks', '.zip'):
        result['apks'] = find_files(out, '.apk')
        if args.decode:
            if len(result['apks']) > 1:
                print('\n检测到多个 APK（split/分包）。建议先运行:')
                print('  python3 scripts/merge_splits.py %s' % out)
            elif result['apks']:
                run(['bash', os.path.join(os.path.dirname(__file__), 'decode.sh'), result['apks'][0]])
    elif ext == '.jar':
        result['jars'] = [src]
        if args.decode:
            run(['jadx', '-d', os.path.join(out, 'jadx'), src])
    elif ext == '.aar':
        result['jars'] = find_files(out, '.jar')
        if args.decode:
            for jar in result['jars']:
                run(['jadx', '-d', os.path.join(out, 'jadx', os.path.splitext(os.path.basename(jar))[0]), jar])

    # 常见分发包内容提示
    hints = []
    for p in ('manifest.json', 'AndroidManifest.xml', 'classes.jar'):
        fp = os.path.join(out, p)
        if os.path.isfile(fp):
            hints.append(p)
    result['hints'] = hints

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('\n解包完成: %s' % out)
        if result['apks']:
            print('APK 文件:')
            for p in result['apks']:
                print('  - %s' % os.path.relpath(p, out))
        if result['jars']:
            print('JAR 文件:')
            for p in result['jars']:
                print('  - %s' % os.path.relpath(p, out) if p.startswith(out) else '  - %s' % p)
        if hints:
            print('识别到: %s' % ', '.join(hints))
        print('下一步: APK 用 decode.sh；JAR/AAR 的 classes.jar 用 jadx -d <out> <jar>')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
