#!/usr/bin/env python3
"""仓库自检：SKILL 元数据、Markdown 内链、脚本语法、版本一致性、隐私项。

用于本地和 CI，不修改任何文件。退出码 0 = 通过，1 = 有问题。

用法:
  python3 scripts/check_repo.py            # 基础检查（内部/公开版都适用）
  python3 scripts/check_repo.py --public   # 公开版额外检查隐私项（宿主/个人输入法/内部用语）
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD_EXT = ('.md',)
SKIP_DIRS = {'.git', '__pycache__', 'work', 'deapk-work', 'toolcache'}


def files(exts=None):
    for dirpath, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            p = os.path.join(dirpath, n)
            if exts is None or p.endswith(exts):
                yield p


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, '/')


def read(p):
    with open(p, encoding='utf-8', errors='ignore') as f:
        return f.read()


def check_frontmatter(errors):
    p = os.path.join(ROOT, 'SKILL.md')
    if not os.path.isfile(p):
        errors.append('缺少 SKILL.md')
        return
    txt = read(p)
    if not txt.startswith('---'):
        errors.append('SKILL.md 缺 YAML frontmatter')
        return
    m = re.match(r'---\s*\n(.*?)\n---', txt, re.S)
    if not m:
        errors.append('SKILL.md frontmatter 不完整')
        return
    fm = m.group(1)
    for key in ('name:', 'description:'):
        if key not in fm:
            errors.append(f'SKILL.md frontmatter 缺 {key}')


def strip_code_blocks(txt):
    out, fence = [], False
    for line in txt.splitlines():
        if re.match(r'^\s*(```|~~~)', line):
            fence = not fence
            continue
        if not fence:
            out.append(line)
    return '\n'.join(out)


def check_links(errors):
    link_re = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
    skip = ('http://', 'https://', 'mailto:', 'tel:', 'ftp:', 'data:', '//', '#')
    bad_chars = set('{}<>`$*|')
    for p in files(MD_EXT):
        base = os.path.dirname(p)
        for target in link_re.findall(strip_code_blocks(read(p))):
            t = target.strip()
            if not t or t.startswith(skip) or any(c in t for c in bad_chars):
                continue
            t = t.split('#', 1)[0].split('?', 1)[0]
            if not t:
                continue
            tgt = os.path.normpath(os.path.join(base, t))
            if not os.path.exists(tgt):
                errors.append(f'{rel(p)}: 内链指向不存在: {target}')


def check_scripts(errors):
    for p in files(('.py',)):
        try:
            compile(read(p), p, 'exec')
        except SyntaxError as e:
            errors.append(f'{rel(p)}: Python 语法错误: {e}')
    bash = shutil.which('bash')
    if not bash:
        errors.append('找不到 bash，跳过 .sh 语法检查')
        return
    for p in files(('.sh',)):
        r = subprocess.run([bash, '-n', p], capture_output=True, text=True)
        if r.returncode != 0:
            errors.append(f'{rel(p)}: bash 语法错误: {r.stderr.strip()[:200]}')


def check_version(errors):
    vf = os.path.join(ROOT, 'VERSION')
    if not os.path.isfile(vf):
        return
    ver = read(vf).strip()
    if not re.match(r'^\d+\.\d+\.\d+', ver):
        errors.append(f'VERSION 不是语义化版本: {ver}')
    ch = os.path.join(ROOT, 'CHANGELOG.md')
    if os.path.isfile(ch):
        m = re.search(r'^##\s*\[?v?([0-9]+\.[0-9]+\.[0-9]+)', read(ch), re.M)
        if not m:
            errors.append('CHANGELOG.md 找不到版本号')
        elif m.group(1) != ver:
            errors.append(f'VERSION({ver}) 与 CHANGELOG 最新版本({m.group(1)}) 不一致')
    for name in ('README.md', 'README_zh.md'):
        p = os.path.join(ROOT, name)
        if os.path.isfile(p):
            m = re.search(r'version-(v?[0-9]+\.[0-9]+\.[0-9]+)', read(p))
            if m and m.group(1).lstrip('v') != ver:
                errors.append(f'{name} 徽章版本({m.group(1)}) 与 VERSION({ver}) 不一致')


def check_privacy(errors):
    # 敏感标记用拼接构造，避免检查脚本自己命中
    tokens = ['搜' + '狗', '小' + '鹤', '用户' + '要求']  # DSH / DSH Go 是产品名，公开版允许出现
    skip = {os.path.normpath(__file__)}
    for p in files(('.md', '.sh', '.py')):
        if os.path.normpath(p) in skip:
            continue
        txt = read(p)
        for t in tokens:
            if t in txt:
                errors.append(f'{rel(p)}: 公开版不应出现隐私/内部标记 "{t}"')


def check_untracked_artifacts(errors):
    for p in files():
        base = os.path.basename(p)
        if base.endswith(('.pyc', '.bak')) or '__pycache__' in p:
            errors.append(f'{rel(p)}: 打包不应包含缓存/备份文件')




def check_internal(errors):
    """内部版外发前提醒：列出内部专属内容/隐私项，仅告警。"""
    internal_markers = [
        'references/game-mod-toggle.md', 'references/game-native-il2cpp.md',
        'references/game-ball-example', 'scripts/mod_toggle.py',
        'references/jargon.md', 'field-journal/_maintenance.md',
    ]
    hits = [m for m in internal_markers if os.path.exists(os.path.join(ROOT, m))]
    print('\n⚠️  内部版标记（外发前请确认）：')
    if hits:
        for h in hits:
            print('   -', h)
    else:
        print('   - 未发现内部专属内容（可能是公开版）')
    tokens = ['搜' + '狗', '小' + '鹤', '用户' + '要求']  # DSH / DSH Go 是产品名，公开版允许出现
    hits2 = []
    for p in files(('.md', '.sh', '.py')):
        if os.path.normpath(p) == os.path.normpath(__file__):
            continue
        txt = read(p)
        if any(t in txt for t in tokens):
            hits2.append(rel(p))
    if hits2:
        print('   - 含隐私/内部标记的文件:', ', '.join(hits2[:10]) + (' …' if len(hits2) > 10 else ''))
    print('   提示：内部版含研究性内容与个人环境记录，对外分发前请脱敏或改用公开版。')


def main():
    ap = argparse.ArgumentParser(description='仓库自检（不修改文件）')
    ap.add_argument('--public', action='store_true', help='额外检查公开版隐私项')
    ap.add_argument('--internal', action='store_true',
                    help='内部/分发前检查：列出内部专属内容与隐私项，仅告警不失败')
    args = ap.parse_args()
    errors = []
    check_frontmatter(errors)
    check_links(errors)
    check_scripts(errors)
    check_version(errors)
    check_untracked_artifacts(errors)
    if args.public:
        check_privacy(errors)
    if args.internal:
        check_internal(errors)
    if errors:
        print(f'❌ {len(errors)} 个问题:')
        for e in errors:
            print(' -', e)
        return 1
    print('✅ 检查通过（frontmatter / 内链 / 脚本语法 / 版本 / 打包卫生'
          + (' / 隐私' if args.public else '') + '）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
