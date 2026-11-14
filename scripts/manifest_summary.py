#!/usr/bin/env python3
"""抽取 apktool 解码目录的 AndroidManifest 摘要（手机端反查用）。

用法:
    python3 manifest_summary.py <apktool解码目录 | AndroidManifest.xml>

输出: 包名/版本/minSdk/入口 Activity/权限/组件/危险标记/ad 相关组件高亮。
"""
import os
import re
import sys

AD_RE = re.compile(r'(ads?|admob|bytedance|pangle|kwad|qq\.e|mobads|mbridge|ironsource|applovin|jiagu|stub|shell|pairip|license)', re.I)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    p = sys.argv[1]
    if os.path.isdir(p):
        p = os.path.join(p, 'AndroidManifest.xml')
    if not os.path.isfile(p):
        print(f'ERR: 找不到 {p}')
        return 1
    s = open(p, encoding='utf-8', errors='ignore').read()

    def attr(tag_re, name):
        m = re.search(tag_re, s)
        return m.group(1) if m else ''

    pkg = attr(r'<manifest[^>]*\bpackage="([^"]+)"', 'package')
    vn = attr(r'android:versionName="([^"]+)"', 'vn')
    vc = attr(r'android:versionCode="([^"]+)"', 'vc')
    minsdk = attr(r'android:minSdkVersion="([^"]+)"', 'min')
    targetsdk = attr(r'android:targetSdkVersion="([^"]+)"', 'target')

    # apktool 会把版本/SDK 信息挪到同目录 apktool.yml，缺失时回退读取
    yml = os.path.join(os.path.dirname(p), 'apktool.yml')
    if (not vn or not minsdk) and os.path.isfile(yml):
        y = open(yml, encoding='utf-8', errors='ignore').read()
        def yget(pat):
            m = re.search(pat, y)
            return m.group(1).strip().strip("'\"") if m else ''
        vn = vn or yget(r'versionName:\s*(.+)')
        vc = vc or yget(r"versionCode:\s*'?([^'\n]+)")
        minsdk = minsdk or yget(r"minSdkVersion:\s*'?([^'\n]+)")
        targetsdk = targetsdk or yget(r"targetSdkVersion:\s*'?([^'\n]+)")
        pkg = pkg or yget(r'package:\s*(.+)')
    appname = attr(r'<application[^>]*android:name="([^"]+)"', 'app')
    debuggable = 'android:debuggable="true"' in s
    allowbackup = re.search(r'android:allowBackup="([^"]+)"', s)
    cleartext = 'usesCleartextTraffic="true"' in s

    print('══════ Manifest 摘要 ══════')
    print(f'package      = {pkg}')
    print(f'version      = {vn} ({vc})')
    print(f'sdk          = min {minsdk or "?"} / target {targetsdk or "?"}')
    print(f'application  = {appname}')
    print(f'debuggable   = {debuggable}')
    print(f'allowBackup  = {allowbackup.group(1) if allowbackup else "?"}')
    print(f'cleartext    = {cleartext}')

    perms = re.findall(r'<uses-permission[^>]*android:name="([^"]+)"', s)
    print(f'\n权限 ({len(perms)}):')
    for x in sorted(set(perms)):
        mark = '  ⚠ ' if AD_RE.search(x) else '    '
        print(mark + x)

    # 组件
    comps = re.findall(r'<(activity|service|receiver|provider)[^>]*android:name="([^"]+)"', s)
    print(f'\n组件 ({len(comps)}):')
    ad_comps = []
    for tag, name in comps:
        if AD_RE.search(name):
            ad_comps.append(name)
        else:
            print(f'    {tag:9s} {name}')
    if ad_comps:
        print('\n广告/加固相关组件:')
        for n in sorted(set(ad_comps)):
            print('  ⚠ ' + n)

    # 入口 Activity
    m = re.search(r'<activity[^>]*android:name="([^"]+)"[^>]*>(?:(?!</activity>).)*?intent-filter[^>]*>.*?android.intent.action.MAIN.*?LAUNCHER', s, re.S)
    print(f'\n启动 Activity: {m.group(1) if m else "（未识别，检查 intent-filter）"}')

    # 广告 meta-data
    metas = re.findall(r'<meta-data[^>]*android:name="([^"]+)"', s)
    ad_meta = [x for x in metas if AD_RE.search(x)]
    if ad_meta:
        print('\n广告/加固 meta-data:')
        for x in sorted(set(ad_meta)):
            print('  ⚠ ' + x)
    return 0


if __name__ == '__main__':
    sys.exit(main())
