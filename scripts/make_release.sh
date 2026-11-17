#!/usr/bin/env bash
# make_release.sh — 发布打包：自检 → 打包 → 完整性检查 → SHA256 → 解压复检
#
# 用法:
#   bash scripts/make_release.sh [输出目录] [--public|--internal] [--name 包名]
# 例:
#   bash scripts/make_release.sh --name apk-reverse-公开版 --public
#   bash scripts/make_release.sh --name apk-reverse-内部版 --internal
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
ROOTNAME=$(basename "$ROOT")
DL_BASE="${DL_BASE:-/sdcard/Download}"
OUT="${OUT:-$DL_BASE/DSH-Go}"
MODE=normal
ZIPNAME="$ROOTNAME"

while [ $# -gt 0 ]; do
    case "$1" in
        --public) MODE=public; shift ;;
        --internal) MODE=internal; shift ;;
        --name) ZIPNAME="$2"; shift 2 ;;
        *) OUT="$1"; shift ;;
    esac
done
mkdir -p "$OUT"

check() {
    local dir="$1"
    case "$MODE" in
        public) python3 "$dir/scripts/check_repo.py" --public && python3 "$dir/scripts/privacy_scan.py" ;;
        internal) python3 "$dir/scripts/check_repo.py" --internal ;;
        *) python3 "$dir/scripts/check_repo.py" ;;
    esac
}

# 同步版本徽章（发版前执行，保证 README/表格/SVG 与 VERSION 一致）
sync_version_badge() {
    local VER
    VER=$(cat "$ROOT/VERSION" 2>/dev/null | tr -d '[:space:]')
    [ -n "$VER" ] || return 0
    # 按版本号生成新的徽章文件（jsdelivr 对同名文件缓存久，换名字可立即生效）
    if [ -f "$ROOT/assets/badges/version.svg" ]; then
        sed -E "s#>v[0-9]+\.[0-9]+\.[0-9]+<#>v$VER<#" "$ROOT/assets/badges/version.svg"             > "$ROOT/assets/badges/version-$VER.svg"
    fi
    sed -i -E "s#>v[0-9]+\.[0-9]+\.[0-9]+<#>v$VER<#" "$ROOT/assets/badges/version.svg" 2>/dev/null || true
    # 清掉其它旧版本徽章文件（按版本号命名的都只保留当前版本）
    find "$ROOT/assets/badges" -maxdepth 1 -name 'version-[0-9]*.svg' ! -name "version-$VER.svg" -delete 2>/dev/null || true
    # README 引用换成当前版本号的文件名
    sed -i -E "s#assets/badges/version-[0-9]+\.[0-9]+\.[0-9]+\.svg#assets/badges/version-$VER.svg#g" "$ROOT/README.md" "$ROOT/README_zh.md" 2>/dev/null || true
    # At a glance 表格版本号
    sed -i -E "s/\| v[0-9]+\.[0-9]+\.[0-9]+ \|/| v$VER |/g" "$ROOT/README.md" "$ROOT/README_zh.md" 2>/dev/null || true
    echo "徽章与表格版本已同步: v$VER"
}

sync_version_badge

echo "== 1/4 自检（$MODE）=="
check "$ROOT" || { echo "自检失败，停止发布"; exit 1; }

echo "== 2/4 打包 =="
ZIP="$OUT/${ZIPNAME}.zip"
rm -f "$ZIP"
cd "$(dirname "$ROOT")" || exit 1
zip -qr "$ZIP" "$ROOTNAME" -x "*__pycache__*" "*.pyc" "*.bak" "*/.git/*" "*.tgz" "*.zip" || { echo "打包失败"; exit 1; }
echo "   $ZIP"

echo "== 3/4 完整性 + SHA256 =="
unzip -t "$ZIP" >/dev/null || { echo "zip 完整性检查失败"; exit 1; }
SUM=$(sha256sum "$ZIP" | awk '{print $1}')
printf '%s  %s\n' "$SUM" "$(basename "$ZIP")" > "$ZIP.sha256"
cat "$ZIP.sha256"

echo "== 4/4 解压复检 =="
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
unzip -q "$ZIP" -d "$TMP" || { echo "解压失败"; exit 1; }
check "$TMP/$ROOTNAME" || { echo "解压后自检失败"; exit 1; }
echo "发布包就绪: $ZIP"
