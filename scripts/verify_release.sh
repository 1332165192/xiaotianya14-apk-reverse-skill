#!/usr/bin/env bash
# verify_release.sh — 校验发布包 SHA256
# 用法: bash scripts/verify_release.sh <zip> [sha256 文件]
#   不传 sha 文件时：优先用 <zip>.sha256，其次当前目录 SHA256SUMS
set -uo pipefail
Z="${1:-}"
[ -n "$Z" ] || { echo "用法: $0 <zip> [sha256 文件]"; exit 2; }
[ -f "$Z" ] || { echo "找不到: $Z"; exit 2; }
DIR=$(cd "$(dirname "$Z")" && pwd)
BASE=$(basename "$Z")
SHA="${2:-}"
if [ -z "$SHA" ]; then
    if [ -f "$DIR/$BASE.sha256" ]; then SHA="$DIR/$BASE.sha256"
    elif [ -f "$DIR/SHA256SUMS" ]; then
        SHA=$(mktemp); grep "  $BASE\$" "$DIR/SHA256SUMS" > "$SHA" || { echo "SHA256SUMS 里没有 $BASE"; rm -f "$SHA"; exit 1; }
    else echo "缺 $BASE.sha256 或 SHA256SUMS"; exit 1; fi
fi
cd "$DIR"
if sha256sum -c "$SHA" 2>/dev/null | grep -q ": OK"; then
    echo "✅ 校验通过: $BASE"
else
    echo "❌ 校验失败: $BASE"; sha256sum -c "$SHA"; exit 1
fi
