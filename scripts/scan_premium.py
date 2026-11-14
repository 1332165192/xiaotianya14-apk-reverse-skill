#!/usr/bin/env python3
"""权益/付费墙 + 数值货币 定位扫描器（APK 逆向 · 手机 proot Ubuntu）。

给 apktool 解码目录做一遍扫描，输出「分析权益逻辑 / 改数值数值」需要的候选清单：
1. 付费点/支付 SDK 与支付回调（Google Billing / 支付宝 / 微信 / 华为 IAP / 自研）
2. 权益/付费墙字符串资源 + 资源 ID + 可直接跑的反查命令
3. 权益布尔判定候选（isVip/isPro/hasPurchased 字段与方法 → 恒真补丁点）
4. 数值/货币字段与方法候选（coin/gold/diamond/score… → 改返回值的补丁点）
5. 存档与持久化点（SharedPreferences / SQLite / 序列化）
6. 服务端权益线索（权益/数值/订单接口 URL）
7. 运行时安全校验与完整性校验（签名校验 / Play Integrity / root / Xposed / Frida）
8. native 库字符串线索（.so 里的权益/货币/风控关键字）

第三方库（androidx/com.google material/okhttp/alipay SDK …）会被过滤掉，
只报「应用自己的代码」。混淆后类名变成 a/b/c 时名字线索会失效，
改用 references/entitlement-analysis.md §3 的结构特征或 §4 动态 Hook。

用法:
    python3 scan_premium.py <apktool解码目录> [--json] [--top 25]
"""
import argparse
import json
import os
import re
import sys

# ── 第三方库前缀（命中即视为库代码，不参与权益/数值候选）───────────────────
LIB_PREFIXES = (
    'androidx/', 'android/support/', 'com/google/android/material/', 'com/google/android/gms/',
    'com/google/android/play/', 'com/google/common/', 'com/google/gson/', 'com/google/firebase/',
    'com/google/protobuf/', 'com/google/zxing/', 'com/google/ads/', 'com/google/android/ump/',
    'com/facebook/', 'com/alipay/', 'com/tencent/mm/opensdk/', 'com/tencent/bugly/',
    'com/umeng/', 'com/github/', 'com/squareup/', 'com/bumptech/', 'com/airbnb/', 'com/blankj/',
    'com/amazonaws/', 'com/bytedance/sdk/', 'com/qq/e/', 'com/kwad/', 'com/baidu/mobads/',
    'com/mbridge/', 'com/applovin/', 'com/unity3d/', 'com/ironsource/', 'com/vungle/',
    'org/', 'io/', 'kotlin/', 'kotlinx/', 'javax/', 'okhttp3/', 'retrofit2/', 'dagger/',
    'hilt_aggregated_deps/', 'net/', 'de/', 'jp/', 'pl/', 'it/', 'fr/', 'ru/', 'co/', 'ch/',
    'java/', 'dalvik/', 'sun/', 'libcore/', 'com/android/billingclient/', 'com/android/vending/',
    'com/huawei/', 'com/xiaomi/', 'com/oplus/', 'com/vivo/', 'com/paypal/', 'com/stripe/',
    'com/revenuecat/', 'com/pingxx/', 'com/onesignal/', 'com/amplitude/', 'com/appsflyer/',
    'com/adjust/', 'com/branch/', 'com/segment/', 'com/crashlytics/', 'io/reactivex/',
)

# ── 关键词 token（按 camelCase/下划线切词后比对，避免 provider→pro 这类误报）──
MEMBER_TOKENS = {
    'vip', 'svip', 'vvip', 'member', 'membership', 'premium', 'prime', 'pro',
    'subscribe', 'subscribed', 'subscription', 'purchase', 'purchased', 'buy', 'bought',
    'entitle', 'entitled', 'entitlement', 'unlock', 'unlocked', 'paid', 'pay',
    'trial', 'forever', 'permanent', 'lifetime', 'license', 'licence', 'activation', 'activate',
    'noads', 'adfree', 'upgrade', 'upgraded', 'renew', 'expire', 'expired',
}
CURRENCY_TOKENS = {
    'coin', 'gold', 'diamond', 'gem', 'credit', 'balance', 'wallet', 'cash', 'currency',
    'ticket', 'energy', 'money', 'score', 'point', 'quota', 'reward', 'coupon',
    'dollar', 'rmb', 'cents', 'bean', 'shell', 'star', 'heart', 'power', 'token',
}
# 明显是库/框架语义的 token 组合，避免 level/point 之类误报
WEAK_SUFFIXES = ('level', 'id', 'size', 'width', 'height', 'offset', 'margin', 'padding',
                 'index', 'count', 'type', 'flag', 'state', 'time', 'date', 'pointer')

FIELD_RE = re.compile(r'^\.field\s')
STRCONST_RE = re.compile(r'const-string(?:/jumbo)?\s+v\d+,\s*"([^"]*)"')
CONST_LIT_RE = re.compile(r'^\s*const(?:/4|/16|/high16|-wide(?:/32|/high16)?)?\s+v\d+,\s*(0x[0-9a-fA-F]+|-?\d+)')
URL_RE = re.compile(r'https?://[^\s"<>]+')
MEMBER_STR_RE = re.compile(r'(会员|付费|订阅|续费|永久|尊贵|高级版|解锁|购买|内购|去广告|免广告|'
                           r'vip|member|premium|subscrib|purchase|unlock|paid|trial|upgrade)', re.I)
CURRENCY_STR_RE = re.compile(r'(金币|钻石|积分|余额|点券|元宝|体力|能量|次数|额度|奖励|签到|'
                             r'coin|gold|diamond|gem|credit|balance|point|ticket|energy|reward|quota)', re.I)

PAY_SDKS = [
    ('Google Billing', 'com/android/billingclient/api'),
    ('Google Vending', 'com/android/vending/billing'),
    ('支付宝', 'com/alipay'),
    ('微信支付', 'com/tencent/mm/opensdk'),
    ('微信支付(旧)', 'com/tencent/mm/sdk'),
    ('华为 IAP', 'com/huawei/hms/iap'),
    ('小米 IAP', 'com/xiaomi/mipay'),
    ('OPPO 支付', 'com/oplus/pay'),
    ('vivo 支付', 'com/vivo/pay'),
    ('Ping++', 'com/pingxx'),
    ('Stripe', 'com/stripe'),
    ('PayPal', 'com/paypal'),
    ('RevenueCat', 'com/revenuecat'),
    ('友盟统计', 'com/umeng'),
    ('穿山甲(激励视频)', 'com/bytedance/sdk/openadsdk'),
]

BILLING_CALLBACKS = ['onPurchasesUpdated', 'acknowledgePurchase', 'queryPurchasesAsync',
                     'onBillingSetupFinished', 'consumeAsync', 'PayResult', 'WXPayEntry',
                     'onPayFinish', 'onResp', 'purchaseHistory']

INTEGRITY_SIGS = [
    ('签名校验(getPackageInfo)', 'getPackageInfo'),
    ('签名数组(GET_SIGNATURES)', 'GET_SIGNATURES'),
    ('签名数组(GET_SIGNING_CERTIFICATES)', 'GET_SIGNING_CERTIFICATES'),
    ('证书摘要(MessageDigest)', 'MessageDigest'),
    ('证书比较(java/security/cert)', 'java/security/cert'),
    ('Play Integrity', 'IntegrityManager'),
    ('SafetyNet(旧)', 'SafetyNet'),
    ('调试检测', 'isDebuggerConnected'),
    ('root 检测(su 路径)', '/system/xbin/su'),
    ('Magisk 检测', 'magisk'),
    ('Xposed 检测', 'xposed'),
    ('LSPosed 检测', 'lsposed'),
    ('Frida 检测', 'frida'),
    ('ptrace 检测', 'ptrace'),
    ('模拟器检测', 'goldfish'),
]

PERSIST_SIGS = [
    ('SharedPreferences', 'SharedPreferences'),
    ('Sqlite', 'SQLiteDatabase'),
    ('Room', 'androidx/room'),
    ('ObjectOutputStream 序列化', 'ObjectOutputStream'),
    ('FileOutputStream 存档', 'FileOutputStream'),
    ('MMKV', 'com/tencent/mmkv'),
]


def is_lib(rel):
    return any(rel.startswith(p) for p in LIB_PREFIXES)


def to_class(rel):
    """smali_classes2/com/app/User.smali → com/app/User"""
    p = rel.replace(os.sep, '/')
    if '/' in p:
        p = p.split('/', 1)[1]
    return p[:-len('.smali')] if p.endswith('.smali') else p


TOKEN_RE = re.compile(r'[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+')


def tokens(name):
    out = set()
    for t in TOKEN_RE.findall(name.replace('_', ' ').replace('$', ' ')):
        t = t.lower()
        if not t:
            continue
        out.add(t)
        if t.endswith('s') and len(t) > 3:
            out.add(t[:-1])
    return out


def match_kind(name, kind):
    """kind: member/currency → 命中的 token（或 None）"""
    tk = tokens(name)
    if kind == 'member':
        hit = tk & MEMBER_TOKENS
        if hit:
            return sorted(hit)[0]
        return None
    hit = tk & CURRENCY_TOKENS
    if hit:
        # 排除 xxxLevel / xxxCount 这类弱语义（配置项、UI 参数）
        strong = {h for h in hit if h not in ('level', 'point', 'token', 'power')}
        return sorted(strong)[0] if strong else None
    return None


def iter_smali_files(dec):
    for entry in sorted(os.listdir(dec)):
        if entry == 'smali' or entry.startswith('smali_'):
            root = os.path.join(dec, entry)
            if not os.path.isdir(root):
                continue
            for dirpath, _dirnames, filenames in os.walk(root):
                for fn in filenames:
                    if fn.endswith('.smali'):
                        yield os.path.join(dirpath, fn)


def parse_methods_in(text):
    """轻量解析：[(method_name, desc, ret)]"""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith('.method'):
            continue
        m = re.search(r'\(([^)]*)\)(\S+)\s*$', s)
        if not m:
            continue
        name = s.split('(')[0].split()[-1]
        out.append((name, m.group(1), m.group(2)))
    return out


def parse_strings_xml(dec):
    public = {}
    pubfile = os.path.join(dec, 'res', 'values', 'public.xml')
    if os.path.isfile(pubfile):
        try:
            txt = open(pubfile, encoding='utf-8', errors='ignore').read()
            for m in re.finditer(r'<public\s+type="string"\s+name="([^"]+)"\s+id="(0x[0-9a-fA-F]+)"', txt):
                public[m.group(1)] = m.group(2).lower()
        except OSError:
            pass
    out = []
    resdir = os.path.join(dec, 'res')
    if not os.path.isdir(resdir):
        return out
    for d in sorted(os.listdir(resdir)):
        if not d.startswith('values'):
            continue
        f = os.path.join(resdir, d, 'strings.xml')
        if not os.path.isfile(f):
            continue
        try:
            txt = open(f, encoding='utf-8', errors='ignore').read()
        except OSError:
            continue
        for m in re.finditer(r'<string\s+name="([^"]+)"[^>]*>(.*?)</string>', txt, re.S):
            name, val = m.group(1), re.sub(r'<[^>]+>', '', m.group(2)).strip()
            if MEMBER_STR_RE.search(name) or MEMBER_STR_RE.search(val):
                kind = 'member'
            elif CURRENCY_STR_RE.search(name) or CURRENCY_STR_RE.search(val):
                kind = 'currency'
            else:
                continue
            out.append({'name': name, 'value': val, 'id': public.get(name), 'kind': kind})
    seen, uniq = set(), []
    for r in out:
        k = (r['name'], r['value'])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    # 权益优先，其次中文内容优先
    uniq.sort(key=lambda r: (0 if r['kind'] == 'member' else 1,
                             0 if re.search(r'[\u4e00-\u9fff]', r['value']) else 1))
    return uniq


def scan(dec, top=25):
    res = {
        'package': '', 'smali_files': 0, 'pay_sdks': [], 'billing_callbacks': [],
        'member_strings': [], 'member_fields': [], 'member_methods': [],
        'currency_fields': [], 'currency_methods': [], 'const_hints': [],
        'persist': [], 'urls': [], 'integrity': [], 'native': [],
    }
    manifest = os.path.join(dec, 'AndroidManifest.xml')
    if os.path.isfile(manifest):
        m = re.search(r'package="([^"]+)"',
                      open(manifest, encoding='utf-8', errors='ignore').read())
        if m:
            res['package'] = m.group(1)

    sdk_hits, sdk_apprefs = {}, {}
    persist_hits, integrity_hits = {}, {}
    urls = {}
    n = 0
    for path in iter_smali_files(dec):
        n += 1
        if n % 10000 == 0:
            print(f'  …已扫描 {n} 个 smali', file=sys.stderr)
        rel = os.path.relpath(path, dec).replace(os.sep, '/')
        try:
            txt = open(path, encoding='utf-8', errors='ignore').read()
        except OSError:
            continue
        cls = to_class(rel)
        lib = is_lib(cls)
        member_fields, member_methods = [], []
        curr_fields, curr_methods = [], []
        consts = []
        for line in txt.splitlines():
            s = line.strip()
            if s.startswith('.field'):
                tok = s.split()[-1]
                if ':' not in tok:
                    continue
                name, typ = tok.split(':', 1)
                if typ == 'Z':
                    hit = match_kind(name, 'member')
                    if hit:
                        member_fields.append((name, typ, hit))
                elif typ in ('I', 'J', 'S', 'B', 'Ljava/lang/String;'):
                    hit = match_kind(name, 'currency')
                    if hit:
                        curr_fields.append((name, typ, hit))
            elif s.startswith('const') or s.startswith('const-wide'):
                m = CONST_LIT_RE.match(s)
                if m:
                    try:
                        v = int(m.group(1), 0)
                    except ValueError:
                        continue
                    if 10 <= abs(v) <= 0x7fffffff:
                        consts.append(v)
        for mname, desc, ret in parse_methods_in(txt):
            if ret == 'Z':
                hit = match_kind(mname, 'member')
                if hit:
                    member_methods.append((mname, desc, hit))
            elif ret in ('I', 'J'):
                hit = match_kind(mname, 'currency')
                if hit:
                    curr_methods.append((mname, desc, hit))
        if not lib:
            if member_fields or member_methods:
                res['member_fields'].extend(
                    {'file': rel, 'class': cls, 'name': f, 'type': t, 'token': k}
                    for f, t, k in member_fields)
                res['member_methods'].extend(
                    {'file': rel, 'class': cls, 'name': fn, 'desc': d, 'token': k}
                    for fn, d, k in member_methods)
            if curr_fields or curr_methods:
                res['currency_fields'].extend(
                    {'file': rel, 'class': cls, 'name': f, 'type': t, 'token': k}
                    for f, t, k in curr_fields)
                res['currency_methods'].extend(
                    {'file': rel, 'class': cls, 'name': fn, 'desc': d, 'token': k}
                    for fn, d, k in curr_methods)
                big = sorted({v for v in consts if abs(v) >= 1000})[:6]
                if big:
                    res['const_hints'].append({'file': rel, 'values': [hex(v) for v in big]})
        # 支付 SDK：库自身文件 + 应用侧引用（L 前缀描述符）
        for label, prefix in PAY_SDKS:
            if prefix in rel:
                sdk_hits.setdefault(label, set()).add(rel)
            elif ('L' + prefix) in txt:
                sdk_apprefs.setdefault(label, set()).add(rel)
        if not lib:
            for cb in BILLING_CALLBACKS:
                if cb in txt:
                    res['billing_callbacks'].append({'file': rel, 'cb': cb})
                    break
            for label, sig in PERSIST_SIGS:
                if sig in txt:
                    persist_hits.setdefault(label, set()).add(rel)
            for label, sig in INTEGRITY_SIGS:
                if sig in txt:
                    integrity_hits.setdefault(label, set()).add(rel)
            for u in URL_RE.findall(txt):
                if re.search(r'(vip|member|premium|order|pay|purchase|coin|gold|balance|'
                             r'account|subscri|user)', u, re.I):
                    urls[u] = urls.get(u, 0) + 1
    res['smali_files'] = n

    def sethits(h, apprefs=None, limit=10):
        out = []
        keys = set(h) | set(apprefs or {})
        for label in sorted(keys, key=lambda k: -(len(h.get(k, ())) + len((apprefs or {}).get(k, ())))) :
            out.append({'label': label,
                        'sdk_files': len(h.get(label, ())),
                        'app_refs': len((apprefs or {}).get(label, ())),
                        'sample': sorted(h.get(label, ()))[:limit]})
        return out

    res['pay_sdks'] = sethits(sdk_hits, sdk_apprefs)
    res['persist'] = sethits(persist_hits)
    res['integrity'] = sethits(integrity_hits)
    res['urls'] = [{'url': u, 'count': c} for u, c in sorted(urls.items(), key=lambda kv: -kv[1])[:top]]
    res['member_strings'] = parse_strings_xml(dec)[:120]
    # 去重（同文件同方法名，取 token 最强者优先）
    for k in ('member_fields', 'member_methods', 'currency_fields', 'currency_methods'):
        seen, uniq = set(), []
        for r in res[k]:
            key = (r['file'], r['name'])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(r)
        # 类名本身带 vip/member 的排前面，再按文件
        uniq.sort(key=lambda r: (0 if match_kind(r['class'].split('/')[-1], 'member') else 1,
                                 0 if match_kind(r['class'].split('/')[-1], 'currency') else 1, r['file']))
        res[k] = uniq[:top]
    res['const_hints'] = res['const_hints'][:top]
    # 支付回调去重
    seen, uniq = set(), []
    for r in res['billing_callbacks']:
        if r['file'] in seen:
            continue
        seen.add(r['file'])
        uniq.append(r)
    res['billing_callbacks'] = uniq[:top]
    res['native'] = scan_native(dec, top)
    return res


def scan_native(dec, top=12):
    out = []
    libdir = os.path.join(dec, 'lib')
    if not os.path.isdir(libdir):
        return out
    pat = re.compile(rb'[\x20-\x7e]{5,120}')
    kw = re.compile(rb'(?i)\bvip\b|\bmember\b|\bpremium\b|\bcoin\b|\bgold\b|\bdiamond\b|'
                    rb'\bbalance\b|\bpurchase\b|\bsubscri\w*\b|\bsignature\b|\bintegrity\b|'
                    rb'\broot\b|\bfrida\b|\bxposed\b|\bdebug\b|\blicen[cs]e\b|\bpaid\b|'
                    rb'\bunlock\b|\bcheckSign\b|\bverify\w*\b')
    for abi in sorted(os.listdir(libdir)):
        adir = os.path.join(libdir, abi)
        if not os.path.isdir(adir):
            continue
        for fn in sorted(os.listdir(adir)):
            if not fn.endswith('.so'):
                continue
            path = os.path.join(adir, fn)
            try:
                data = open(path, 'rb').read()
            except OSError:
                continue
            hits = []
            for m in pat.finditer(data):
                s = m.group()
                if kw.search(s):
                    hits.append(s.decode('utf-8', 'replace'))
                    if len(hits) >= 8:
                        break
            if hits:
                out.append({'file': os.path.relpath(path, dec), 'strings': hits})
            if len(out) >= top:
                return out
    return out


def report(res):
    p = print
    p('══════ 目标概况 ══════')
    p(f"  包名        : {res['package'] or '?'}")
    p(f"  smali 文件  : {res['smali_files']}")
    p('')

    p('══════ 1. 付费点/支付 SDK 与支付回调 ══════')
    if res['pay_sdks']:
        for h in res['pay_sdks']:
            p(f"  [{h['label']}] 库文件 {h['sdk_files']} / 应用引用 {h['app_refs']}  例: {h['sample'][0] if h['sample'] else ''}")
    else:
        p('  未命中标准支付 SDK —— 可能自研/服务端订单/第三方聚合，走第 6 节接口线索 + 抓包')
    if res['billing_callbacks']:
        p('  支付回调/结算类（补丁点常在回调里 sput-boolean 1）:')
        for b in res['billing_callbacks'][:10]:
            p(f"    {b['file']}  ({b['cb']})")
    p('')

    p('══════ 2. 权益/付费墙字符串（资源 ID → 反查类） ══════')
    if res['member_strings']:
        for r in res['member_strings'][:20]:
            name = '' if r['name'].startswith('APKTOOL_DUPLICATE') else f" {r['name']}"
            p(f"  {(r['id'] or '?'):12s}{name}: {r['value'][:70]}")
        ids = [r['id'] for r in res['member_strings'] if r['id']][:10]
        if ids:
            p('  → 反查使用类（把命中的类名交给 patch_method.py）:')
            p("    grep -rn '" + '|'.join(ids) + "' smali*")
        else:
            p('  → 无 public.xml ID（或字符串加密）：用 jadx 搜资源名 / grep 文案直查 smali')
    else:
        p('  无命中（字符串可能加密/服务端下发）→ 走第 3 节字段名 + 第 6 节接口线索')
    p('')

    p('══════ 3. 权益布尔判定候选（恒真补丁点） ══════')
    if res['member_fields'] or res['member_methods']:
        for r in res['member_fields']:
            p(f"  [字段] {r['class']}.{r['name']}:Z  ({r['file']})")
        for r in res['member_methods']:
            desc = f"({r['desc']})" if 'desc' in r else ''
            p(f"  [方法] {r['class']}.{r['name']}{desc}Z  ({r['file']})")
        p('  → 补丁（先 --dry-run）:')
        r = (res['member_methods'] or [None])[0]
        if r:
            p(f"    python3 scripts/patch_method.py ret <解码目录> --class {r['class']} "
              f"--method {r['name']} --return true --dry-run")
    else:
        p('  无命中 —— R8 混淆后名字变短（a()Z），改用第 4 节常量/结构特征或 Frida 动态找')
    p('')

    p('══════ 4. 数值/货币字段与方法候选（改返回值补丁点） ══════')
    if res['currency_fields'] or res['currency_methods']:
        for r in res['currency_fields'][:12]:
            p(f"  [字段] {r['class']}.{r['name']}:{r['type']}  ({r['file']})")
        for r in res['currency_methods'][:12]:
            p(f"  [方法] {r['class']}.{r['name']}({r['desc']})  ({r['file']})")
        p('  → 补丁: --return 999999999；余额/消费逻辑走 references/value-logic-analysis.md 的等长替换')
    else:
        p('  无命中 —— 数值只在服务端 / native 层 / 名字被混淆')
    if res['const_hints']:
        p('  候选类里的大常量（常见初始数值/价格/上限）:')
        for c in res['const_hints'][:10]:
            p(f"    {c['file']}: {' '.join(c['values'])}")
    p('')

    p('══════ 5. 存档与持久化点 ══════')
    if res['persist']:
        for h in res['persist']:
            p(f"  [{h['label']}] {h['sdk_files']} 个文件  例: {h['sample'][0] if h['sample'] else ''}")
        p('  → 真机存档需 root 读 /data/data/<包名>/shared_prefs 或 databases（value-logic-analysis.md §1）')
    else:
        p('  未命中')
    p('')

    p('══════ 6. 服务端权益线索（权益/数值/订单接口） ══════')
    if res['urls']:
        for u in res['urls'][:15]:
            p(f"  {u['count']:3d}x {u['url'][:110]}")
        p('  → 这类接口通常返回 isVip/coin 字段；客户端改不动时只能抓包/Hook 响应（entitlement-analysis.md §4）')
    else:
        p('  无命中（接口域名可能在 native/加密字符串里）')
    p('')

    p('══════ 7. 运行时安全校验 / 完整性校验（改包前先知道要过什么） ══════')
    if res['integrity']:
        for h in res['integrity']:
            p(f"  [{h['label']}] {h['sdk_files']} 个文件  例: {h['sample'][0] if h['sample'] else ''}")
        p('  → 先过校验再打功能补丁；对策见 references/protection-map.md')
    else:
        p('  未命中（也可能在 native 层，见第 8 节）')
    p('')

    p('══════ 8. native 库关键字线索 ══════')
    if res['native']:
        for h in res['native']:
            p(f"  {h['file']}: {', '.join(h['strings'][:5])}")
        p('  → .so 里的判定要 Frida Hook / r2 分析（protection-map.md §Frida）')
    else:
        p('  无命中')
    p('')

    p('══════ 下一步 ══════')
    p('  1) 权益/永久适配 → references/entitlement-analysis.md')
    p('  2) 数值/数值修改 → references/value-logic-analysis.md')
    p('  3) 判定点找准后打补丁 → scripts/patch_method.py（先 --dry-run 看 diff）')
    p('  4) 调用链看不清 / 服务端下发 → 动态 Hook（references/protection-map.md §Frida）')
    p('  5) 打包签名验证 → scripts/build_sign.sh + SKILL.md §3 第 8 步')


def main():
    ap = argparse.ArgumentParser(description='权益/付费墙 + 数值货币定位扫描器')
    ap.add_argument('decoded', help='apktool 解码目录')
    ap.add_argument('--json', action='store_true', help='输出 JSON')
    ap.add_argument('--top', type=int, default=25, help='每节最多输出条数')
    args = ap.parse_args()
    if not os.path.isdir(args.decoded):
        sys.exit(f'不是目录: {args.decoded}')
    res = scan(args.decoded, top=args.top)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        report(res)


if __name__ == '__main__':
    main()
