#!/usr/bin/env python3
"""广告特征扫描器：给 apktool 解码目录做广告/保护结构扫描，输出可执行线索。

用法:
    python3 analyze_ads.py <apktool解码目录> [--json]

输出:
1. 命中的广告 SDK（按包名前缀统计 smali 文件数）
2. 非 SDK 自身文件里的广告类型引用（应用侧调用点 / R8 relocate 后的 SDK 内部引用）
3. 广告相关字符串资源（strings.xml 命中 + 对应资源 ID + 使用类反查）
4. 开关候选类（静态 Z 字段 / sput-boolean / ()Z 判定方法 的交叉命中）
5. 保护特征（StringFog / pairip / 常见加固壳 / 原生库）
6. 下一步建议
"""
import json
import os
import re
import subprocess
import sys

SDK_SIGNATURES = [
    ('AdMob', ['com/google/android/gms/ads', 'com/google/ads/mediation', 'com/google/android/gms/internal/ads']),
    ('UMP同意', ['com/google/android/gms/internal/consent_sdk', 'com/google/android/ump']),
    ('穿山甲Pangle', ['com/bytedance/sdk/openadsdk', 'com/bytedance/sdk/msdk', 'com/ss/android']),
    ('优量汇GDT', ['com/qq/e']),
    ('快手Kwad', ['com/kwad']),
    ('百度百青藤', ['com/baidu/mobads']),
    ('Mintegral', ['com/mbridge/msdk']),
    ('UnityAds', ['com/unity3d/ads']),
    ('AppLovin', ['com/applovin']),
    ('ironSource', ['com/ironsource']),
    ('Vungle', ['com/vungle']),
    ('AmazonAds', ['com/amazon/device/ads']),
    ('Meta Ads', ['com/facebook/ads']),
    ('InMobi', ['com/inmobi']),
    ('Chartboost', ['com/chartboost']),
    ('AdColony', ['com/adcolony']),
    ('厂商广告', ['com/huawei/hms/ads', 'com/miui/ads', 'com/heytap', 'com/vivo/ads']),
]

AD_STRING_RE = re.compile(
    r'(广告|广告开关适配|广告组件清理|会员|永久|Remove Ads|remove_ad|ad_remove|ad_free|ad_loading|'
    r'Banner|banner|reward|interstitial|splash|watch_ad|no_ad|premium|vip|pro_)',
    re.I)

PACKER_SIGNATURES = [
    ('360加固', ['com/stub/StubApp', 'com/qihoo/util', 'libjiagu']),
    ('腾讯乐固', ['com/tencent/StubShell', 'libshell']),
    ('梆梆', ['com/secneo/apkwrapper', 'libDexHelper']),
    ('爱加密', ['libexec.so', 's/h/e/l/l']),
    ('网易易盾', ['libnesec']),
    ('娜迦', ['libnaga']),
    ('阿里聚安全', ['libmobisec', 'com/ali/mobisec']),
    ('pairip授权', ['com/pairip/licensecheck']),
]


def run_grep(root, patterns, include='*.smali'):
    """在 root 下 grep -rlE 多模式，返回文件列表（相对 root）"""
    if not patterns:
        return []
    cmd = ['grep', '-rlE', '--include=' + include, '|'.join(patterns), root]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=600).stdout
    except Exception:
        return []
    files = []
    for line in out.splitlines():
        rel = os.path.relpath(line, root)
        if not rel.startswith('.'):
            files.append(rel)
    return files


def scan_sdks(dec):
    print('\n══════ 广告 SDK 命中 ══════')
    sdk_files = {}
    all_prefixes = []
    for name, prefixes in SDK_SIGNATURES:
        all_prefixes.extend(prefixes)
    hits = run_grep(dec, [re.escape(p) for p in all_prefixes])
    for rel in hits:
        for name, prefixes in SDK_SIGNATURES:
            if any(p in rel for p in prefixes):
                sdk_files.setdefault(name, []).append(rel)
                break
    any_hit = False
    for name in [n for n, _ in SDK_SIGNATURES]:
        if name in sdk_files:
            any_hit = True
            print(f'  [{name}] {len(sdk_files[name])} 个 smali 文件')
    if not any_hit:
        print('  未命中已知 SDK 包名——可能是服务端驱动广告/Flutter/RN，或混淆彻底（见 SKILL.md §4.6）')
    return sdk_files


def scan_app_refs(dec, sdk_files):
    """非 SDK 自身文件里引用广告类型（应用侧调用点）"""
    print('\n══════ 应用侧广告引用（非 SDK 目录） ══════')
    sdk_roots = {os.path.dirname(f) for files in sdk_files.values() for f in files}
    pats = [r'com/google/android/gms/ads', r'com/google/android/gms/internal/ads',
            r'com/bytedance/sdk/openadsdk', r'com/qq/e', r'com/kwad', r'com/baidu/mobads']
    hits = run_grep(dec, pats)
    noise = ('smali/com/google', 'smali/com/bytedance', 'smali/androidx', 'smali/android/',
             'smali/kotlin', 'smali/kotlinx', 'smali/org/chromium', 'smali/android/support')
    app_refs = []
    for rel in hits:
        if any(rel.startswith(r) or ('/' + r) in rel for r in sdk_roots):
            continue
        if any(rel.startswith(n) for n in noise):
            continue
        app_refs.append(rel)
    for rel in app_refs[:40]:
        print('  ' + rel)
    if not app_refs:
        print('  （无——应用可能不直接引用 SDK 公开 API；注意 R8 relocate 的内部类调用，见 SKILL.md §4.3）')
    return app_refs


def parse_public_ids(dec):
    """res/values/public.xml -> name->hex(按 type 限 string/layout 等)"""
    name2id = {}
    pub = os.path.join(dec, 'res', 'values', 'public.xml')
    if not os.path.isfile(pub):
        return name2id
    for m in re.finditer(r'<public\s+type="([^"]+)"\s+name="([^"]+)"\s+id="(0x[0-9a-fA-F]+)"', open(pub, encoding='utf-8', errors='ignore').read()):
        name2id[(m.group(1), m.group(2))] = m.group(3)
    return name2id


def scan_strings(dec):
    print('\n══════ 广告相关字符串资源 ═══════')
    name2id = parse_public_ids(dec)
    results = []
    for d in sorted(os.listdir(os.path.join(dec, 'res'))) if os.path.isdir(os.path.join(dec, 'res')) else []:
        if not d.startswith('values'):
            continue
        f = os.path.join(dec, 'res', d, 'strings.xml')
        if not os.path.isfile(f):
            continue
        txt = open(f, encoding='utf-8', errors='ignore').read()
        for m in re.finditer(r'<string\s+name="([^"]+)"[^>]*>([^<]*)</string>', txt):
            name, val = m.group(1), m.group(2)
            if AD_STRING_RE.search(name) or AD_STRING_RE.search(val):
                rid = name2id.get(('string', name))
                results.append({'name': name, 'id': rid, 'value': val.strip()})
    seen = set()
    for r in results:
        k = (r['name'], r['value'])
        if k in seen:
            continue
        seen.add(k)
        print(f"  {r['id'] or '?':12s} {r['name']}: {r['value'][:60]}")
    if not results:
        print('  未命中（字符串可能整体加密/外包资源）')
    return results


def scan_id_usage(dec, string_hits):
    print('\n══════ 资源 ID 使用类反查 ═══════')
    ids = [r['id'] for r in string_hits if r.get('id')]
    if not ids:
        print('  无可用 ID（public.xml 缺失或字符串未命中）')
        return []
    pat = '|'.join(re.escape(i.lower()) for i in ids)
    hits = run_grep(dec, [pat])
    app_hits = [h for h in hits if not h.startswith('smali/com/google')]
    for h in app_hits[:40]:
        print('  ' + h)
    if not app_hits:
        print('  无命中')
    return app_hits


def scan_switches(dec, candidates):
    print('\n══════ 开关候选（Z 字段 / sput-boolean / ()Z 判定） ═══════')
    rows = []
    for rel in candidates:
        p = os.path.join(dec, rel)
        if not os.path.isfile(p):
            continue
        txt = open(p, encoding='utf-8', errors='ignore').read()
        zfields = len(re.findall(r'\.field[^\n]*:Z', txt))
        sputs = len(re.findall(r'sput-boolean', txt))
        zbool_methods = len(re.findall(r'\.method[^\n]*\([^)]*\)Z', txt))
        if zfields or sputs:
            rows.append((rel, zfields, sputs, zbool_methods))
    # 广告引用/资源反查命中的类优先（这类才是关键开关所在），再按布尔密度排其他
    cand_set = set(candidates)
    first = [r for r in rows if r[0] in cand_set]
    rest = [r for r in rows if r[0] not in cand_set]
    rest.sort(key=lambda x: -(x[1] + x[2]))
    print('  [来自广告引用/资源反查的候选]')
    for rel, zf, sp, zm in first[:15]:
        print(f'  {rel}: Z字段={zf} sput-boolean={sp} ()Z方法={zm}')
    if rest:
        print('  [其他布尔密集类]')
        for rel, zf, sp, zm in rest[:8]:
            print(f'  {rel}: Z字段={zf} sput-boolean={sp} ()Z方法={zm}')
    if not rows:
        print('  （候选里没有静态布尔开关；可能是 StateFlow/其他判定方式）')
    return rows


def scan_protection(dec):
    print('\n══════ 保护特征 ═══════')
    found_any = False
    for name, prefixes in PACKER_SIGNATURES:
        hits = run_grep(dec, [re.escape(p) for p in prefixes])
        if hits:
            found_any = True
            print(f'  [{name}] {len(hits)} 处，如 {hits[0]}')
    # StringFog 特征
    hits = run_grep(dec, [r'L\$/\$;->\$_'])
    if hits:
        found_any = True
        print(f'  [StringFog 字符串加密] {len(hits)} 个文件（native 解密，明文 grep 不到）')
    # 原生库
    lib = os.path.join(dec, 'lib')
    if os.path.isdir(lib):
        sos = []
        for root, dirs, files in os.walk(lib):
            for f in files:
                if f.endswith('.so'):
                    sos.append(os.path.relpath(os.path.join(root, f), dec))
        if sos:
            found_any = True
            print(f'  原生库 {len(sos)} 个: {", ".join(os.path.basename(x) for x in sos[:8])}')
    if not found_any:
        print('  未发现明显保护特征')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    dec = sys.argv[1].rstrip('/')
    as_json = '--json' in sys.argv
    if not os.path.isdir(dec):
        print(f'ERR: 目录不存在: {dec}')
        return 1
    sdk_files = scan_sdks(dec)
    app_refs = scan_app_refs(dec, sdk_files)
    string_hits = scan_strings(dec)
    usage = scan_id_usage(dec, string_hits)
    candidates = list(dict.fromkeys(app_refs + usage))
    switches = scan_switches(dec, candidates)
    scan_protection(dec)

    print('\n══════ 下一步建议 ══════')
    if sdk_files:
        print('  1. 用 strings.xml 的广告资源 ID 反查到的类，读它的静态 Z 字段与 ()Z 判断（SKILL.md §4.5）')
        print('  2. 在 SDK 调用点附近找"加载广告"的入口（如 internal/ads/li;->a 之类），可删调用')
        print('  3. 优先找"已购/广告开关适配"开关置真，比拆 SDK 稳')
    else:
        print('  1. 检查 assets（Flutter libapp.so / RN bundle）与服务端广告 API（SKILL.md §4.6）')
    print('  4. 清单清理: manifest_clean.py；合并拆分包: merge_splits.py；打包: build_sign.sh')
    if as_json:
        print(json.dumps({'sdk': {k: len(v) for k, v in sdk_files.items()},
                          'strings': string_hits, 'switches': switches}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
