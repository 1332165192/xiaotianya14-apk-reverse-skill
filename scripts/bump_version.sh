#!/usr/bin/env bash
# bump_version.sh — 统一升级三个版本号（VERSION + README 徽章 + CHANGELOG 占位）
# 用法: bash scripts/bump_version.sh <x.y.z>
# 之后手工补 CHANGELOG 的 [Unreleased] 内容；CI 会校验版本一致性。
set -euo pipefail
V="${1:-}"
[ -n "$V" ] || { echo "用法: $0 <x.y.z>"; exit 2; }
echo "$V" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || { echo "版本格式应为 x.y.z"; exit 2; }
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
printf '%s\n' "$V" > VERSION
for f in README.md README_zh.md; do
    [ -f "$f" ] && sed -i "s/version-v[0-9][0-9.]*-/version-v${V}-/" "$f"
done
python3 - "$V" <<'PY'
import sys, datetime, re
v = sys.argv[1]
p = 'CHANGELOG.md'
try:
    s = open(p, encoding='utf-8').read()
except FileNotFoundError:
    sys.exit('缺 CHANGELOG.md')
if f'## [{v}]' in s:
    print(f'CHANGELOG 已有 [{v}]，跳过')
elif '## [Unreleased]' in s:
    entry = f'## [{v}] - {datetime.date.today().isoformat()}\n\n### Changed\n\n- （填写本次改动）\n\n'
    s = s.replace('## [Unreleased]\n', '## [Unreleased]\n\n' + entry, 1)
    open(p, 'w', encoding='utf-8').write(s)
    print(f'已在 CHANGELOG 插入 [{v}] 占位')
else:
    sys.exit('CHANGELOG 缺 [Unreleased] 段')
PY
echo "版本已改为 $V；请补 CHANGELOG 内容后跑:"
echo "  python3 scripts/check_repo.py $( [ -f .public_marker ] && echo --public )"
