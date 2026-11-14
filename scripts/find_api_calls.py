#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API / 接口 / 凭据线索扫描器（APK 逆向 · 手机 proot Ubuntu，纯 python3 标准库）。

给 jadx 输出目录、apktool 解码目录或单个源码文件做一遍扫描，分组输出
「对接服务端需要知道的接口与凭据线索」：

  1) 硬编码 URL / WebSocket（http(s)、ws(s)，按值聚合、标注出现文件）
  2) Retrofit 注解（@GET/@POST/@PUT/@DELETE/@PATCH/@Headers/@Multipart/
     @FormUrlEncoded/@Query/@Path …，尽量带出端点路径）
  3) OkHttp / Volley / WebSocket 调用点（Request.Builder、url()、newCall、
     StringRequest、JsonObjectRequest、newWebSocket、WebSocketListener）
  4) GraphQL（query / mutation / subscription 操作、graphql 关键字、/graphql 路径）
  5) 认证类关键字（Authorization、Bearer、api_key、token、secret、sign=、
     X-Sign、timestamp、nonce）
  6) 可疑密钥 / 凭据（AWS AKIA、Google AIza、sk-、PRIVATE KEY、password= 等；
     值默认脱敏，只标文件行）

输出中文报告（适合直接贴给用户），结尾给「下一步」；`--json` 输出结构化结果，
`--report out.md` 另存 Markdown。

用法（输入路径省略时扫描当前目录）：
    python3 find_api_calls.py /root/reapk/jadx_out              # 自动找 sources/
    python3 find_api_calls.py /root/reapk/dec                    # apktool 解码目录
    python3 find_api_calls.py /root/reapk/dec --urls --auth
    python3 find_api_calls.py app/src/com/x/Api.java --all --context 3
    python3 find_api_calls.py /root/reapk/dec --all --dedup --report /tmp/api.md
    python3 find_api_calls.py /root/reapk/dec --all --json > /tmp/api.json

常用参数：
    --urls --retrofit --okhttp --graphql --auth --secrets --all
    --context N      每条命中附 N 行上下文（0–20，默认 0）
    --dedup          文本/报告按值聚合（URL 组始终聚合）
    --report out.md  另存 Markdown 报告
    --json           只输出 JSON（诊断信息走 stderr）
    --max-files N    最多扫描 N 个文件（默认 50000，防大目录卡死）

已知限制：
    - 字符串被加密/混淆（StringFog、加固壳）时静态扫不到，需动态抓包或 .so 扫描；
    - 第三方库（okhttp/retrofit/广告 SDK）的命中不会被剔除，需按包名自行过滤；
    - 密钥值会脱敏（只保留首尾），确认真值请按命中行回看文件；
    - `--json` 输出始终按值聚合（含全部 occurrences），`--dedup` 只影响文本/报告展示；
    - 单行超长（> 200 字符）的命中只截取片段；URL 跨字符串拼接可能只抓到片段。
"""
import argparse
import glob
import json
import os
import re
import sys

TOOL_NAME = 'find_api_calls.py'
TOOL_VERSION = '1.0.0'

# ── 扫描规模限制（防大目录卡死） ────────────────────────────────────────────
MAX_HITS_PER_GROUP = 5000      # 单组最多记录多少处命中（超出截断并提示）
MAX_FILE_BYTES = 8 * 1024 * 1024
DEFAULT_MAX_FILES = 50000
MAX_CONTEXT = 20

SKIP_DIR_NAMES = {
    '.git', '.svn', '.hg', '.idea', '.gradle', 'build', 'node_modules',
    '__pycache__', '.cache', 'META-INF',
}

GROUP_ORDER = ['urls', 'retrofit', 'okhttp', 'graphql', 'auth', 'secrets']
GROUP_TITLES = {
    'urls': '硬编码 URL / WebSocket',
    'retrofit': 'Retrofit 注解',
    'okhttp': 'OkHttp / Volley / WebSocket 调用',
    'graphql': 'GraphQL',
    'auth': '认证类关键字',
    'secrets': '可疑密钥 / 凭据',
}

# 组内排序优先级：越靠前越重要（同优先级再按出现次数降序）
RETROFIT_KIND_ORDER = [
    'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS', 'HTTP',
    'Headers', 'Multipart', 'FormUrlEncoded',
    'Query', 'QueryMap', 'Path', 'Body', 'Field', 'FieldMap', 'Header',
    'Part', 'PartMap', 'Url', 'Streaming',
]
OKHTTP_KIND_ORDER = [
    'OkHttp Request.Builder', 'OkHttp url()', 'OkHttp newCall()', 'OkHttp 客户端',
    'Volley StringRequest', 'Volley JsonObjectRequest', 'Volley RequestQueue',
    'WebSocket newWebSocket()', 'WebSocket 类型',
]
AUTH_KIND_ORDER = [
    'Authorization 头', 'Bearer 令牌', 'X-Sign 头', 'api_key 关键字',
    'access_token', 'client_secret', 'sign 参数', 'timestamp 参数', 'nonce 参数',
    'token 关键字', 'secret 关键字',
]
SECRET_KIND_ORDER = [
    'AWS Access Key', 'Google API Key', 'sk- 密钥', '阿里云 AccessKey',
    '腾讯云 SecretId', 'GitHub Token', 'Slack Token', 'JWT', 'Basic 认证头',
    'password 赋值', 'secret/key 赋值', 'Google OAuth Client ID', '私钥文件头',
]
KIND_PRIORITY = {
    'retrofit': RETROFIT_KIND_ORDER,
    'okhttp': OKHTTP_KIND_ORDER,
    'auth': AUTH_KIND_ORDER,
    'secrets': SECRET_KIND_ORDER,
}
_KIND_INDEX = {g: {k: i for i, k in enumerate(order)} for g, order in KIND_PRIORITY.items()}

# ── 1) URL ───────────────────────────────────────────────────────────────────
URL_RE = re.compile(r'(?i)\b(?:https?|wss?)://[^\s"\'<>()\\\x00-\x1f]+')
# 框架/规范用 URL，不是业务接口，默认过滤
URL_NOISE_SUBSTR = (
    'schemas.android.com', 'www.w3.org', 'ns.adobe.com', 'java.sun.com',
    'json-schema.org', 'xmlpull.org', 'xml.org', 'openxmlformats.org',
    'purl.org', 'apache.org/licenses', 'www.apache.org/licenses',
    'example.com', 'example.org', 'example.net',
)

# ── 2) Retrofit ─────────────────────────────────────────────────────────────
RETROFIT_ENDPOINT_ANN = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS', 'HTTP'}
RETROFIT_ANNOT_RE = re.compile(
    r'@(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|HTTP|Headers|Multipart|FormUrlEncoded|'
    r'Query|QueryMap|Path|Body|Field|FieldMap|Part|PartMap|Url|Streaming|Header)\b')
RETROFIT_SMALI_RE = re.compile(r'Lretrofit2/http/([A-Za-z]+);')
RETROFIT_SMALI_VALUE_RE = re.compile(r'(?:\bvalue|\.value)\s*=\s*"([^"]*)"')

# ── 3) OkHttp / Volley / WebSocket ──────────────────────────────────────────
OKHTTP_PATTERNS = [
    ('OkHttp Request.Builder', re.compile(r'(?<![A-Za-z0-9_])Request\$Builder|(?<![A-Za-z0-9_])Request\.Builder')),
    ('OkHttp 客户端', re.compile(r'OkHttpClient|Lokhttp3/OkHttpClient;')),
    ('OkHttp url()', re.compile(r'(?:\.|->)url\s*\(')),
    ('OkHttp newCall()', re.compile(r'(?:\.|->)newCall\s*\(')),
    ('Volley StringRequest', re.compile(r'StringRequest')),
    ('Volley JsonObjectRequest', re.compile(r'JsonObjectRequest')),
    ('Volley RequestQueue', re.compile(r'Volley\.newRequestQueue|Lcom/android/volley/')),
    ('WebSocket newWebSocket()', re.compile(r'newWebSocket\s*\(')),
    ('WebSocket 类型', re.compile(r'okhttp3[/.]WebSocket|Lokhttp3/WebSocket;|WebSocketListener')),
]
OKHTTP_URL_ARG_RE = re.compile(r'(?:\.|->)url\s*\(\s*"([^"]+)"')

# ── 4) GraphQL ──────────────────────────────────────────────────────────────
GQL_OP_RE = re.compile(r'(?i)\b(query|mutation|subscription)\s+[A-Za-z_$][\w$]*\s*[({]')
GQL_PATH_RE = re.compile(r'(?i)/graphql\b')
GQL_KW_RE = re.compile(r'graphql', re.I)

# ── 5) 认证关键字 ───────────────────────────────────────────────────────────
AUTH_PATTERNS = [
    ('Authorization 头', re.compile(r'\bAuthorization\b', re.I)),
    ('Bearer 令牌', re.compile(r'\bBearer\b', re.I)),
    ('api_key 关键字', re.compile(r'\bapi[_-]?key\b', re.I)),
    ('access_token', re.compile(r'\baccess[_-]?token\b', re.I)),
    ('client_secret', re.compile(r'\bclient[_-]?secret\b', re.I)),
    ('token 关键字', re.compile(r'\btoken\b', re.I)),
    ('secret 关键字', re.compile(r'\bsecret\b', re.I)),
    ('sign 参数', re.compile(r'(?i)(?:[?&]|\b)sign\s*=')),
    ('X-Sign 头', re.compile(r'(?i)\bx[-_]sign\b')),
    ('timestamp 参数', re.compile(r'(?i)\btimestamp\b')),
    ('nonce 参数', re.compile(r'(?i)\bnonce\b')),
]

# ── 6) 可疑密钥 / 凭据 ─────────────────────────────────────────────────────
SECRET_PATTERNS = [
    ('AWS Access Key', re.compile(r'\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[0-9A-Z]{16}\b')),
    ('Google API Key', re.compile(r'\bAIza[0-9A-Za-z_\-]{35}\b')),
    ('sk- 密钥', re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}')),
    ('私钥文件头', re.compile(r'-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----')),
    ('password 赋值', re.compile(r'(?i)\bpassword\s*[=:]\s*\\?["\'][^"\']{4,}')),
    ('secret/key 赋值', re.compile(
        r'(?i)\b(?:client[_-]?secret|secret[_-]?key|app[_-]?secret|api[_-]?secret)\s*[=:]\s*'
        r'\\?["\'][^"\']{8,}')),
    ('Basic 认证头', re.compile(r'\bBasic\s+[A-Za-z0-9+/=]{16,}')),
    ('JWT', re.compile(r'\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}')),
    ('阿里云 AccessKey', re.compile(r'\bLTAI[0-9A-Za-z]{12,}')),
    ('腾讯云 SecretId', re.compile(r'\bAKID[0-9A-Za-z]{13,}')),
    ('GitHub Token', re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}')),
    ('Slack Token', re.compile(r'\bxox[baprs]-[A-Za-z0-9\-]{10,}')),
    ('Google OAuth Client ID', re.compile(r'\b[0-9]{10,}-[a-z0-9]{32}\.apps\.googleusercontent\.com')),
]

# ── 小工具 ───────────────────────────────────────────────────────────────────


def eprint(*args):
    print(*args, file=sys.stderr)


def display_width(text):
    """粗略计算终端显示宽度（CJK 算 2），只用于对齐点线。"""
    width = 0
    for ch in text:
        width += 2 if ord(ch) >= 0x1100 and (
            0x2E80 <= ord(ch) <= 0xA4CF or 0xAC00 <= ord(ch) <= 0xD7A3 or
            0xF900 <= ord(ch) <= 0xFAFF or 0xFE30 <= ord(ch) <= 0xFE4F or
            0xFF00 <= ord(ch) <= 0xFF60 or 0xFFE0 <= ord(ch) <= 0xFFE6
        ) else 1
    return width


def snippet(line, maxlen=200):
    s = line.strip()
    if len(s) <= maxlen:
        return s
    return s[:maxlen - 1] + '…'


def clean_url(url):
    u = url.replace('&amp;', '&')
    u = u.rstrip('.,;:!?，。；：、')
    pairs = (('(', ')'), ('[', ']'), ('{', '}'))
    changed = True
    while changed and u:
        changed = False
        for opener, closer in pairs:
            if u.endswith(closer) and u.count(opener) < u.count(closer):
                u = u[:-1]
                changed = True
    return u


def mask_secret(kind, raw):
    """密钥值脱敏：保留少量首尾便于辨认，避免报告/聊天里泄露完整凭据。"""
    if kind in ('私钥文件头', 'Google OAuth Client ID'):
        return raw.strip()
    if kind in ('password 赋值', 'secret/key 赋值'):
        head = raw.split('=', 1)[0] if '=' in raw else raw.split(':', 1)[0]
        return head.strip() + '=***'
    s = raw.strip()
    if len(s) <= 14:
        return s[:3] + '***'
    return s[:6] + '***' + s[-4:]


def context_window(lines, idx, radius):
    start = max(0, idx - radius)
    end = min(len(lines), idx + radius + 1)
    return [{'line': n + 1, 'text': lines[n]} for n in range(start, end)]


# ── 分组匹配 ─────────────────────────────────────────────────────────────────

def match_urls(line):
    hits = []
    if '\\/' in line:
        line = line.replace('\\/', '/')
    for m in URL_RE.finditer(line):
        url = clean_url(m.group(0))
        if not url:
            continue
        if any(noise in url for noise in URL_NOISE_SUBSTR):
            continue
        scheme = url.split(':', 1)[0].lower()
        kind = 'wss' if scheme == 'wss' else 'ws' if scheme == 'ws' else \
            'https' if scheme == 'https' else 'http'
        hits.append((kind, url))
    return hits


def match_retrofit(line, lines, idx, is_smali):
    hits = []
    if is_smali:
        m = RETROFIT_SMALI_RE.search(line)
        if not m:
            return hits
        ann = m.group(1)
        path = ''
        # apktool 把注解参数放在随后的 value = "..." 行
        for j in range(idx + 1, min(idx + 8, len(lines))):
            vm = RETROFIT_SMALI_VALUE_RE.search(lines[j])
            if vm:
                path = vm.group(1)
                break
            if '.end annotation' in lines[j]:
                break
        hits.append((ann, path))
        return hits

    for m in RETROFIT_ANNOT_RE.finditer(line):
        ann = m.group(1)
        if ann in RETROFIT_ENDPOINT_ANN:
            pm = re.search(r'@' + ann + r'\s*\(\s*(?:value\s*=\s*)?"([^"]*)"', line)
            hits.append((ann, pm.group(1) if pm else ''))
        else:
            hits.append((ann, ''))
    return hits


def match_okhttp(line):
    hits = []
    url_arg = ''
    um = OKHTTP_URL_ARG_RE.search(line)
    if um:
        url_arg = um.group(1)
    for kind, rx in OKHTTP_PATTERNS:
        if rx.search(line):
            value = url_arg if (url_arg and kind in ('OkHttp url()', 'OkHttp newCall()')) else ''
            if not value:
                value = snippet(line, 120)
            hits.append((kind, value))
    return hits


def match_graphql(line):
    hits = []
    snip = snippet(line)
    path_hit = False
    for _m in GQL_PATH_RE.finditer(line):
        hits.append(('/graphql 路径', snip))
        path_hit = True
    for m in GQL_OP_RE.finditer(line):
        op = m.group(1).lower()
        kind = {'query': 'query 操作', 'mutation': 'mutation 操作',
                'subscription': 'subscription 操作'}[op]
        hits.append((kind, snip))
    if not path_hit and GQL_KW_RE.search(line):
        hits.append(('graphql 关键字', snip))
    return hits


def match_auth(line):
    hits = []
    snip = snippet(line, 200)
    for kind, rx in AUTH_PATTERNS:
        if rx.search(line):
            hits.append((kind, snip))
    return hits


def match_secrets(line):
    hits = []
    for kind, rx in SECRET_PATTERNS:
        for m in rx.finditer(line):
            hits.append((kind, mask_secret(kind, m.group(0))))
    return hits


def collect_line_hits(line, lines, idx, enabled, is_smali):
    """行级扫描：先用廉价子串判断这行是否有线索，再按组匹配（性能关键）。"""
    hits = []

    # ── 行级快速预筛：绝大多数代码行在这里直接跳过 ──
    if is_smali:
        if ('"' not in line and 'okhttp' not in line and 'WebSocket' not in line
                and 'volley' not in line and 'retrofit2' not in line):
            return hits
    else:
        if line.startswith(('import ', 'package ')):
            return hits
        if ('"' not in line and '@' not in line and '://' not in line
                and 'okhttp' not in line and 'OkHttp' not in line
                and 'WebSocket' not in line and 'volley' not in line and 'Volley' not in line
                and 'StringRequest' not in line and 'JsonObjectRequest' not in line
                and 'Request.Builder' not in line and 'Request$Builder' not in line
                and 'newCall(' not in line and 'newWebSocket' not in line
                and 'token' not in line and 'Token' not in line
                and 'secret' not in line and 'Secret' not in line
                and 'sign' not in line and 'nonce' not in line
                and 'timestamp' not in line and 'Timestamp' not in line
                and 'graphql' not in line and 'GraphQL' not in line
                and 'query ' not in line and 'mutation ' not in line):
            return hits

    if 'urls' in enabled and '://' in line:
        for kind, url in match_urls(line):
            hits.append(('urls', kind, url))

    if 'retrofit' in enabled:
        if is_smali:
            if 'Lretrofit2/http/' in line:
                for kind, path in match_retrofit(line, lines, idx, True):
                    hits.append(('retrofit', kind, path))
        elif '@' in line:
            for kind, path in match_retrofit(line, lines, idx, False):
                hits.append(('retrofit', kind, path))

    if 'okhttp' in enabled and (
            'okhttp' in line or 'OkHttp' in line or 'Request$Builder' in line
            or 'Request.Builder' in line or '.url(' in line or '->url(' in line
            or '.newCall(' in line or '->newCall(' in line or 'newWebSocket' in line
            or 'WebSocket' in line or 'StringRequest' in line
            or 'JsonObjectRequest' in line or 'volley' in line or 'Volley' in line):
        for kind, value in match_okhttp(line):
            hits.append(('okhttp', kind, value))

    if 'graphql' in enabled and (
            'graphql' in line or 'GraphQL' in line or '/graphql' in line
            or 'query ' in line or 'mutation ' in line or 'subscription ' in line):
        for kind, value in match_graphql(line):
            hits.append(('graphql', kind, value))

    if 'auth' in enabled and (
            'Authorization' in line or 'authorization' in line
            or 'Bearer' in line or 'bearer' in line or 'api_key' in line
            or 'apiKey' in line or 'API_KEY' in line or 'access_token' in line
            or 'client_secret' in line or 'token' in line or 'Token' in line
            or 'secret' in line or 'Secret' in line or 'sign' in line
            or 'Sign' in line or 'nonce' in line or 'timestamp' in line
            or 'Timestamp' in line):
        for kind, value in match_auth(line):
            hits.append(('auth', kind, value))

    if 'secrets' in enabled and (
            'AKIA' in line or 'ASIA' in line or 'AIza' in line or 'sk-' in line
            or 'PRIVATE KEY' in line or 'password' in line or 'Password' in line
            or 'passwd' in line or 'secret' in line or 'Secret' in line
            or 'Basic ' in line or 'eyJ' in line or 'LTAI' in line or 'AKID' in line
            or 'ghp_' in line or 'gho_' in line or 'ghu_' in line or 'ghs_' in line
            or 'ghr_' in line or 'xox' in line
            or 'apps.googleusercontent.com' in line):
        for kind, value in match_secrets(line):
            hits.append(('secrets', kind, value))

    return hits


# ── 输入解析 ────────────────────────────────────────────────────────────────

def walk_ext(root, exts):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIR_NAMES)
        for fn in sorted(filenames):
            if fn.lower().endswith(exts):
                found.append(os.path.join(dirpath, fn))
    return found


def resolve_input(path):
    """返回 (files, base, type_text) ；无法识别时抛 ValueError。"""
    abs_path = os.path.abspath(path)

    if os.path.isfile(abs_path):
        ext = os.path.splitext(abs_path)[1].lower()
        if ext not in ('.java', '.kt', '.smali'):
            raise ValueError('单文件输入仅支持 .java / .kt / .smali，当前: %s' % (ext or '无扩展名'))
        return [abs_path], os.path.dirname(abs_path), '单文件（%s）' % ext

    if not os.path.isdir(abs_path):
        raise ValueError('路径不存在或不是目录/文件: %s' % path)

    root = abs_path
    jadx_files, smali_files, strings_files = [], [], []
    used_sources_dir = False

    sources = os.path.join(root, 'sources')
    if os.path.isdir(sources):
        jadx_files = walk_ext(sources, ('.java', '.kt'))
        used_sources_dir = bool(jadx_files)

    smali_dirs = []
    try:
        for name in sorted(os.listdir(root)):
            if os.path.isdir(os.path.join(root, name)) and \
                    re.fullmatch(r'smali(?:_classes\d+)?', name):
                smali_dirs.append(os.path.join(root, name))
    except OSError:
        smali_dirs = []
    for d in smali_dirs:
        smali_files.extend(walk_ext(d, ('.smali',)))

    strings_files = sorted(glob.glob(os.path.join(root, 'res', 'values*', 'strings.xml')))

    if not (jadx_files or smali_files or strings_files):
        # 兜底：直接传了 jadx 的 sources/ 目录或单个 smali 根目录
        jadx_files = walk_ext(root, ('.java', '.kt'))
        smali_files = walk_ext(root, ('.smali',))

    types = []
    if jadx_files:
        types.append('jadx sources/ 目录' if used_sources_dir else 'jadx sources 目录')
    if smali_files:
        types.append('apktool smali*/（%d 个目录）' % max(1, len(smali_dirs)))
    if strings_files:
        types.append('apktool res/values*/strings.xml')

    if not (jadx_files or smali_files or strings_files):
        raise ValueError(
            '未在目录中找到 .java/.kt 源码、smali*/ 或 res/values*/strings.xml：%s\n'
            '请传 jadx 输出目录（含 sources/）或 apktool 解码目录。' % path)

    files = list(dict.fromkeys(jadx_files + smali_files + strings_files))
    files.sort()
    return files, root, ' + '.join(types)


# ── 扫描主流程 ──────────────────────────────────────────────────────────────

def scan(files, base, enabled, context_n, show_progress=False):
    store = {
        g: {'entries': {}, 'occurrences': 0, 'truncated': False} for g in enabled
    }
    scan_stats = {'read': 0, 'skipped_large': 0, 'unreadable': 0}
    total = len(files)
    progress_step = 2000

    for i, fp in enumerate(files):
        if show_progress and i and i % progress_step == 0:
            sys.stderr.write('\r扫描 %d/%d ...' % (i, total))
            sys.stderr.flush()
        try:
            if os.path.getsize(fp) > MAX_FILE_BYTES:
                scan_stats['skipped_large'] += 1
                continue
            with open(fp, 'r', encoding='utf-8', errors='replace') as fh:
                text = fh.read()
        except OSError:
            scan_stats['unreadable'] += 1
            continue

        scan_stats['read'] += 1
        rel = os.path.relpath(fp, base)
        is_smali = fp.lower().endswith('.smali')
        lines = text.splitlines()

        for idx, line in enumerate(lines):
            if not line:
                continue
            line_hits = collect_line_hits(line, lines, idx, enabled, is_smali)
            if not line_hits:
                continue
            ctx = context_window(lines, idx, context_n) if context_n else None
            seen = set()
            for group, kind, value in line_hits:
                key = (group, kind, value)
                if key in seen:
                    continue
                seen.add(key)
                _add_hit(store, group, kind, value, rel, idx + 1, ctx)

    if show_progress and total:
        sys.stderr.write('\r扫描 %d/%d ... 完成\n' % (total, total))
        sys.stderr.flush()
    return store, scan_stats


def _add_hit(store, group, kind, value, file_rel, line_no, ctx):
    gdata = store[group]
    if gdata['occurrences'] >= MAX_HITS_PER_GROUP:
        gdata['truncated'] = True
        return
    key = (kind, value)
    ent = gdata['entries'].get(key)
    if ent is None:
        ent = {'kind': kind, 'value': value, 'count': 0, 'occurrences': [], '_seen': set()}
        gdata['entries'][key] = ent
    if (file_rel, line_no) in ent['_seen']:
        return
    ent['_seen'].add((file_rel, line_no))
    ent['occurrences'].append((file_rel, line_no, ctx))
    ent['count'] += 1
    gdata['occurrences'] += 1


def sorted_entries(group, gdata):
    index = _KIND_INDEX.get(group, {})
    return sorted(
        gdata['entries'].values(),
        key=lambda e: (index.get(e['kind'], len(index)), -e['count'], e['value']))


def build_next_steps(enabled, store):
    def has(group):
        return group in store and store[group]['occurrences'] > 0

    steps = []
    if has('urls'):
        steps.append('硬编码 URL：在 jadx 打开命中文件，确认请求封装类与域名拼接；'
                     '真机用 mitmproxy / Charles 代理抓包验证实际请求。')
    if has('retrofit'):
        steps.append('Retrofit：打开 @GET/@POST 所在接口类，整理端点、参数与 @Headers；'
                     '再搜 addInterceptor 看公共头与签名逻辑。')
    if has('okhttp'):
        steps.append('OkHttp/Volley：搜 OkHttpClient.Builder 与 addInterceptor，'
                     '定位签名、加密、重试；有 certificatePinner / TrustManager 时先处理 SSL Pinning。')
    if has('graphql'):
        steps.append('GraphQL：整理 query/mutation 的 operationName 与字段，'
                     '尝试对 /graphql 做 introspection 确认 schema。')
    if has('auth'):
        steps.append('认证：在拦截器或登录响应处 hook / 打日志，确认 Authorization、token、'
                     'sign、nonce、timestamp 的生成方式（JWT 可 base64 解 payload 看结构）。')
    if has('secrets'):
        steps.append('密钥：按「文件:行」回看确认是否为真实凭据；外发或入库前脱敏，'
                     '不要用高权限密钥做联网验证。')
    if not steps:
        steps.append('未发现明显线索：确认输入目录（jadx 的 sources/ 或 apktool 的 smali*/），'
                     '或提高 --max-files；字符串可能被加密/加固，改用动态抓包或 strings lib/*.so。')
    return steps


# ── 渲染：终端文本 ─────────────────────────────────────────────────────────

def _group_header(g, gdata):
    return '── %d) %s（%d 处 / %d 唯一）──' % (
        GROUP_ORDER.index(g) + 1, GROUP_TITLES[g],
        gdata['occurrences'], len(gdata['entries']))


def _hit_label(group, ent):
    if group == 'retrofit':
        label = '@' + ent['kind']
        if ent['value']:
            label += ' ' + ent['value']
        else:
            label += '（无路径参数）'
        return label
    return '[%s] %s' % (ent['kind'], ent['value'])


def _locations(entries, limit=6):
    shown = ['%s:%d' % (f, ln) for f, ln, _ctx in entries[:limit]]
    text = ', '.join(shown)
    if len(entries) > limit:
        text += ' 等 %d 处' % len(entries)
    return text


def render_text(res, enabled, dedup, context_n, all_groups):
    out = []
    sep = '═' * 58
    out.append(sep)
    out.append(' API / 凭据线索扫描')
    out.append(sep)
    out.append('目标: %s' % res['input'])
    out.append('类型: %s' % res['input_type'])
    files_line = '扫描: %d 个文件' % res['scanned_files']
    if res['truncated']:
        files_line += '（共 %d 个，--max-files=%d 已截断）' % (
            res['available_files'], res['max_files'])
    out.append(files_line)
    if res['file_stats']['smali'] or res['file_stats']['source'] or res['file_stats']['xml']:
        out.append('构成: smali %d / java·kt %d / strings.xml %d' % (
            res['file_stats']['smali'], res['file_stats']['source'],
            res['file_stats']['xml']))
    if res['scan_stats']['skipped_large'] or res['scan_stats']['unreadable']:
        out.append('跳过: 超大 %d / 不可读 %d' % (
            res['scan_stats']['skipped_large'], res['scan_stats']['unreadable']))
    out.append('分组: %s' % ('全部' if all_groups else '、'.join(
        '%s' % GROUP_TITLES[g] for g in GROUP_ORDER if g in enabled)))
    total_occ = sum(res['summary'][g]['occurrences'] for g in enabled)
    total_uniq = sum(res['summary'][g]['unique'] for g in enabled)
    out.append('命中: 共 %d 处 / %d 个唯一值' % (total_occ, total_uniq))
    out.append('')

    out.append('── 概况 ──')
    for g in GROUP_ORDER:
        if g not in enabled:
            continue
        meta = res['summary'][g]
        prefix = '  %d) %s ' % (GROUP_ORDER.index(g) + 1, GROUP_TITLES[g])
        dots = '.' * max(2, 40 - display_width(prefix))
        out.append('%s%s %d 处 / %d 唯一' % (
            prefix, dots, meta['occurrences'], meta['unique']))
    out.append('')

    for g in GROUP_ORDER:
        if g not in enabled:
            continue
        gdata = res['groups'][g]
        out.append(_group_header(g, {
            'occurrences': gdata['occurrences'],
            'entries': gdata['hits'],
        }))
        if gdata['truncated']:
            out.append('  （命中过多，已截断到 %d 处；建议加 --max-files 或缩小目录）'
                       % MAX_HITS_PER_GROUP)
        if not gdata['hits']:
            out.append('  （无命中）')
            out.append('')
            continue

        aggregated = dedup or (g == 'urls')
        for ent in gdata['hits']:
            out.append('  ' + _hit_label(g, ent))
            occ = ent['occurrences']
            if aggregated:
                out.append('        位置: %s' % _locations(occ))
                if context_n:
                    for file_rel, line_no, ctx in occ:
                        if not ctx:
                            continue
                        out.append('        上下文 %s:%d' % (file_rel, line_no))
                        out.extend(_render_ctx(ctx, line_no))
            else:
                for file_rel, line_no, ctx in occ:
                    out.append('        - %s:%d' % (file_rel, line_no))
                    if context_n and ctx:
                        out.extend(_render_ctx(ctx, line_no))
        out.append('')

    out.append('── 下一步 ──')
    for i, step in enumerate(res['next_steps'], 1):
        out.append('  %d. %s' % (i, step))
    out.append('')
    return '\n'.join(out)


def _render_ctx(ctx, hit_line, indent='          '):
    lines = []
    for item in ctx:
        mark = '>' if item['line'] == hit_line else ' '
        lines.append('%s%s%5d| %s' % (indent, mark, item['line'], item['text']))
    return lines


def render_markdown(res, enabled, dedup, context_n, all_groups):
    out = []
    out.append('# API / 凭据线索扫描报告')
    out.append('')
    out.append('- **生成工具**: `%s %s`' % (TOOL_NAME, TOOL_VERSION))
    out.append('- **目标**: `%s`' % res['input'])
    out.append('- **类型**: %s' % res['input_type'])
    line = '- **扫描文件**: %d' % res['scanned_files']
    if res['truncated']:
        line += '（共 %d，`--max-files=%d` 已截断）' % (
            res['available_files'], res['max_files'])
    out.append(line)
    out.append('- **构成**: smali %d / java·kt %d / strings.xml %d' % (
        res['file_stats']['smali'], res['file_stats']['source'], res['file_stats']['xml']))
    out.append('- **分组**: %s' % ('全部' if all_groups else '、'.join(
        GROUP_TITLES[g] for g in GROUP_ORDER if g in enabled)))
    total_occ = sum(res['summary'][g]['occurrences'] for g in enabled)
    total_uniq = sum(res['summary'][g]['unique'] for g in enabled)
    out.append('- **命中**: %d 处 / %d 个唯一值' % (total_occ, total_uniq))
    out.append('')

    out.append('## 概况')
    out.append('')
    out.append('| # | 分组 | 处数 | 唯一值 |')
    out.append('|---|---|---|---|')
    for g in GROUP_ORDER:
        if g not in enabled:
            continue
        meta = res['summary'][g]
        out.append('| %d | %s | %d | %d |' % (
            GROUP_ORDER.index(g) + 1, GROUP_TITLES[g], meta['occurrences'], meta['unique']))
    out.append('')

    for g in GROUP_ORDER:
        if g not in enabled:
            continue
        gdata = res['groups'][g]
        out.append('## %d) %s（%d 处 / %d 唯一）' % (
            GROUP_ORDER.index(g) + 1, GROUP_TITLES[g],
            gdata['occurrences'], len(gdata['hits'])))
        out.append('')
        if gdata['truncated']:
            out.append('> 命中过多，已截断到 %d 处。' % MAX_HITS_PER_GROUP)
            out.append('')
        if not gdata['hits']:
            out.append('（无命中）')
            out.append('')
            continue

        aggregated = dedup or (g == 'urls')
        for ent in gdata['hits']:
            label = _hit_label(g, ent).replace('`', "'").replace('|', '\\|')
            out.append('- `%s`' % label)
            occ = ent['occurrences']
            if aggregated:
                out.append('  - 位置: %s' % _locations(occ, 8))
                if context_n:
                    for file_rel, line_no, ctx in occ:
                        if not ctx:
                            continue
                        out.append('  - 上下文 `%s:%d`' % (file_rel, line_no))
                        out.append('')
                        out.append('    ```text')
                        for item in ctx:
                            mark = '>' if item['line'] == line_no else ' '
                            out.append('    %s%5d| %s' % (mark, item['line'], item['text']))
                        out.append('    ```')
            else:
                for file_rel, line_no, ctx in occ:
                    out.append('  - 位置: `%s:%d`' % (file_rel, line_no))
                    if context_n and ctx:
                        out.append('')
                        out.append('    ```text')
                        for item in ctx:
                            mark = '>' if item['line'] == line_no else ' '
                            out.append('    %s%5d| %s' % (mark, item['line'], item['text']))
                        out.append('    ```')
        out.append('')

    out.append('## 下一步')
    out.append('')
    for i, step in enumerate(res['next_steps'], 1):
        out.append('%d. %s' % (i, step))
    out.append('')
    return '\n'.join(out)


# ── JSON 组装 ──────────────────────────────────────────────────────────────

def build_json(res, enabled):
    groups = {}
    for g in GROUP_ORDER:
        if g not in enabled:
            continue
        gdata = res['groups'][g]
        hits = []
        for ent in gdata['hits']:
            occurrences = []
            for file_rel, line_no, ctx in ent['occurrences']:
                item = {'file': file_rel, 'line': line_no}
                if ctx:
                    item['context'] = ctx
                occurrences.append(item)
            hits.append({
                'kind': ent['kind'],
                'value': ent['value'],
                'count': ent['count'],
                'occurrences': occurrences,
            })
        groups[g] = {
            'title': GROUP_TITLES[g],
            'occurrences': gdata['occurrences'],
            'unique': len(gdata['hits']),
            'truncated': gdata['truncated'],
            'hits': hits,
        }
    return {
        'tool': TOOL_NAME,
        'version': TOOL_VERSION,
        'input': res['input'],
        'input_type': res['input_type'],
        'groups_enabled': [g for g in GROUP_ORDER if g in enabled],
        'scanned_files': res['scanned_files'],
        'available_files': res['available_files'],
        'max_files': res['max_files'],
        'truncated': res['truncated'],
        'file_stats': res['file_stats'],
        'scan_stats': res['scan_stats'],
        'context': res['context'],
        'dedup': res['dedup'],
        'summary': res['summary'],
        'groups': groups,
        'next_steps': res['next_steps'],
    }


# ── 入口 ───────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description='API / 接口 / 凭据线索扫描器：硬编码 URL、Retrofit、OkHttp/Volley/'
                    'WebSocket、GraphQL、认证关键字、可疑密钥。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例:\n'
               '  %(prog)s /root/reapk/jadx_out --all\n'
               '  %(prog)s /root/reapk/dec --urls --auth --context 2\n'
               '  %(prog)s /root/reapk/dec --all --dedup --report /tmp/api.md\n'
               '  %(prog)s /root/reapk/dec --retrofit --json\n'
               '  %(prog)s src/com/x/Api.java --all --context 1\n')
    parser.add_argument('path', nargs='?', default='.',
                        help='jadx 输出目录（自动找 sources/）、apktool 解码目录，'
                             '或单个 .java/.kt/.smali 文件；省略时扫描当前目录')
    parser.add_argument('--urls', action='store_true', help='只扫硬编码 URL / WebSocket')
    parser.add_argument('--retrofit', action='store_true', help='只扫 Retrofit 注解')
    parser.add_argument('--okhttp', action='store_true', help='只扫 OkHttp / Volley / WebSocket')
    parser.add_argument('--graphql', action='store_true', help='只扫 GraphQL')
    parser.add_argument('--auth', action='store_true', help='只扫认证类关键字')
    parser.add_argument('--secrets', action='store_true', help='只扫可疑密钥 / 凭据')
    parser.add_argument('--all', action='store_true', help='扫描全部分组（默认）')
    parser.add_argument('--context', type=int, default=0, metavar='N',
                        help='每条命中附 N 行上下文（0–20，默认 0）')
    parser.add_argument('--dedup', action='store_true',
                        help='文本/报告按值聚合展示（URL 组始终聚合）')
    parser.add_argument('--report', metavar='OUT.md',
                        help='另存 Markdown 报告到指定文件')
    parser.add_argument('--json', action='store_true',
                        help='只输出 JSON（报告与诊断信息走 stderr）')
    parser.add_argument('--max-files', type=int, default=DEFAULT_MAX_FILES, metavar='N',
                        help='最多扫描 N 个文件（默认 %d）' % DEFAULT_MAX_FILES)
    return parser


def main(argv=None):
    # 手机上可能遇到非法 UTF-8 文件名（surrogateescape），输出时替换而不是崩掉
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')
        except (AttributeError, ValueError):
            pass

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.max_files < 1:
        parser.error('--max-files 必须 >= 1')
    if args.context < 0 or args.context > MAX_CONTEXT:
        parser.error('--context 需在 0 到 %d 之间' % MAX_CONTEXT)

    requested = [g for g, flag in (
        ('urls', args.urls), ('retrofit', args.retrofit), ('okhttp', args.okhttp),
        ('graphql', args.graphql), ('auth', args.auth), ('secrets', args.secrets)) if flag]
    all_groups = args.all or not requested
    enabled = list(GROUP_ORDER) if all_groups else [g for g in GROUP_ORDER if g in requested]

    try:
        files, base, type_text = resolve_input(args.path)
    except ValueError as exc:
        eprint('错误: %s' % exc)
        return 2

    available_files = len(files)
    truncated = False
    if available_files > args.max_files:
        files = files[:args.max_files]
        truncated = True

    file_stats = {'smali': 0, 'source': 0, 'xml': 0}
    for fp in files:
        low = fp.lower()
        if low.endswith('.smali'):
            file_stats['smali'] += 1
        elif low.endswith('.java') or low.endswith('.kt'):
            file_stats['source'] += 1
        elif low.endswith('.xml'):
            file_stats['xml'] += 1

    show_progress = (not args.json) and sys.stderr.isatty()
    store, scan_stats = scan(files, base, enabled, args.context, show_progress)

    summary = {}
    for g in enabled:
        gdata = store[g]
        summary[g] = {
            'title': GROUP_TITLES[g],
            'occurrences': gdata['occurrences'],
            'unique': len(gdata['entries']),
            'truncated': gdata['truncated'],
        }

    res = {
        'input': os.path.abspath(args.path),
        'input_type': type_text,
        'scanned_files': len(files),
        'available_files': available_files,
        'max_files': args.max_files,
        'truncated': truncated,
        'file_stats': file_stats,
        'scan_stats': scan_stats,
        'context': args.context,
        'dedup': args.dedup,
        'summary': summary,
        'next_steps': [],
        'groups': {},
    }
    res['next_steps'] = build_next_steps(enabled, store)

    # 把内部条目整理成对外结构（text / markdown / json 共用）
    for g in enabled:
        gdata = store[g]
        res['groups'][g] = {
            'occurrences': gdata['occurrences'],
            'truncated': gdata['truncated'],
            'hits': [],
        }
        for ent in sorted_entries(g, gdata):
            res['groups'][g]['hits'].append({
                'kind': ent['kind'],
                'value': ent['value'],
                'count': ent['count'],
                'occurrences': ent['occurrences'],
            })

    if args.report:
        try:
            with open(args.report, 'w', encoding='utf-8', errors='replace') as fh:
                fh.write(render_markdown(res, enabled, args.dedup, args.context, all_groups))
            eprint('已写入 Markdown 报告: %s' % os.path.abspath(args.report))
        except OSError as exc:
            eprint('错误: 写报告失败: %s' % exc)
            return 1

    if args.json:
        json.dump(build_json(res, enabled), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write('\n')
    else:
        print(render_text(res, enabled, args.dedup, args.context, all_groups))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except BrokenPipeError:
        # 被 head / less 截断时安静退出
        try:
            sys.stderr.close()
        except Exception:
            pass
        sys.exit(0)
