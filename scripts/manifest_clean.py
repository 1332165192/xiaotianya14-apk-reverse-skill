#!/usr/bin/env python3
"""清理 apktool 解码后的 AndroidManifest.xml：广告组件清理组件/权限/拆分包标记。

用法:
    python3 manifest_clean.py <decode目录> [--keep-referrer] [--dry-run]

默认处理:
- 删除 android:requiredSplitTypes 与 android:splitTypes 属性（合并通用 APK 必需）
- 删除广告权限: com.google.android.gms.permission.AD_ID / ACCESS_ADSERVICES_AD_ID /
  ACCESS_ADSERVICES_ATTRIBUTION / ACCESS_ADSERVICES_TOPICS
- 删除 AdMob 组件: AdActivity/AdService/MobileAdsInitProvider/
  NotificationHandlerActivity/OutOfContextTestingActivity
- 删除 meta-data: com.google.android.gms.ads.APPLICATION_ID 与 com.google.android.gms.ads.flag.*
--keep-referrer: 保留 com.google.android.finsky.permission.BIND_GET_INSTALL_REFERRER_SERVICE（默认保留，此参数仅文档说明）
"""
import argparse
import os
import re
import sys

AD_PERMS = [
    'com.google.android.gms.permission.AD_ID',
    'android.permission.ACCESS_ADSERVICES_AD_ID',
    'android.permission.ACCESS_ADSERVICES_ATTRIBUTION',
    'android.permission.ACCESS_ADSERVICES_TOPICS',
]
AD_COMPONENTS = [
    'com.google.android.gms.ads.AdActivity',
    'com.google.android.gms.ads.AdService',
    'com.google.android.gms.ads.MobileAdsInitProvider',
    'com.google.android.gms.ads.NotificationHandlerActivity',
    'com.google.android.gms.ads.OutOfContextTestingActivity',
]


def remove_component(s, tag, name):
    """删除 name 为 name 的 <tag> 组件（自闭合或有子元素）。返回 (新串, 次数)"""
    n = 0
    pos = 0
    pat = re.compile(r'<%s\b[^>]*?android:name="%s"[^>]*?(/?)>' % (tag, re.escape(name)))
    while True:
        m = pat.search(s, pos)
        if not m:
            break
        if m.group(1) == '/':  # 自闭合
            s = s[:m.start()] + s[m.end():]
            pos = m.start()
        else:  # 有子元素，找闭合标签
            close = s.find('</%s>' % tag, m.end())
            if close == -1:
                break
            s = s[:m.start()] + s[close + len(tag) + 3:]
            pos = m.start()
        n += 1
    return s, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dec', help='apktool 解码目录')
    ap.add_argument('--keep-referrer', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    p = os.path.join(a.dec, 'AndroidManifest.xml')
    if not os.path.isfile(p):
        print(f'ERROR: {p} 不存在', file=sys.stderr)
        return 2
    s = open(p, encoding='utf-8').read()
    orig = s

    # 1. 拆分包标记
    s = re.sub(r'\s+android:requiredSplitTypes="[^"]*"', '', s)
    s = re.sub(r'\s+android:splitTypes="[^"]*"', '', s)

    # 2. 广告权限
    cnt_perm = 0
    for perm in AD_PERMS:
        pat = re.compile(r'<uses-permission\s+android:name="%s"\s*/>' % re.escape(perm))
        s, n = pat.subn('', s)
        cnt_perm += n
    cnt_perm += len(re.findall(r'<uses-permission\s+android:name="%s"' % re.escape('com.google.android.gms.permission.AD_ID'), s))

    # 3. AdMob 组件
    cnt_comp = 0
    for cls in AD_COMPONENTS:
        tagname = 'provider' if 'InitProvider' in cls else ('service' if cls.endswith('AdService') else 'activity')
        s, n = remove_component(s, tagname, cls)
        cnt_comp += n

    # 4. meta-data
    cnt_meta = 0
    pat = re.compile(r'<meta-data\s+[^>]*android:name="com\.google\.android\.gms\.ads\.(?:APPLICATION_ID|flag\.[^"]*)"[^>]*/>')
    s, n = pat.subn('', s)
    cnt_meta += n

    if s == orig:
        print('没有需要修改的内容（或都已清理过）')
        return 0

    if a.dry_run:
        print(f'[dry-run] 将删除: 权限 {cnt_perm}, 组件 {cnt_comp}, meta-data {cnt_meta}')
        return 0
    open(p, 'w', encoding='utf-8').write(s)
    print(f'manifest cleaned: 权限 {cnt_perm}, 组件 {cnt_comp}, meta-data {cnt_meta}')
    print('剩余 gms.ads 引用:', s.count('gms.ads'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
