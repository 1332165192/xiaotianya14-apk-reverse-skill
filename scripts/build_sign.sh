#!/bin/bash
# APK 重打包 + 对齐 + 签名一键脚本
# 用法: build_sign.sh <apktool解码目录> [输出apk] [keystore] [密码]
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/safe_rm.sh"

if [ $# -lt 1 ]; then
    echo "用法: build_sign.sh <解码目录> [输出apk] [keystore] [密码]" >&2
    exit 2
fi
DEC="$1"
OUT="${2:-$(dirname "$DEC")/mod_signed.apk}"
KS="${3:-$HOME/mod.ks}"
PASS="${4:-modmod1}"

# 清掉可能损坏的 framework 缓存（aapt2 运行时报告 RES_TABLE_TYPE_TYPE 错误时也需要）
safe_rm_tree "$HOME/.local/share/apktool/framework"

DIR="$(dirname "$OUT")"
RAW="$DIR/mod_raw.apk"
ALIGNED="$DIR/mod_aligned.apk"

echo "== 1/4 打包（aapt2） =="
apktool b "$DEC" -o "$RAW" --use-aapt2 2>&1 | tail -2

echo "== 2/4 对齐 =="
zipalign -p -f 4 "$RAW" "$ALIGNED"

echo "== 3/4 签名 =="
if [ ! -f "$KS" ]; then
  keytool -genkeypair -keystore "$KS" -alias mod -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass "$PASS" -keypass "$PASS" \
    -dname "CN=Mod, OU=Mod, O=Mod, L=CN"
fi
apksigner sign --ks "$KS" --ks-pass "pass:$PASS" --key-pass "pass:$PASS" -out "$OUT" "$ALIGNED"

echo "== 4/4 验证 =="
apksigner verify "$OUT" && echo "SIGN_OK: $OUT"
ls -la "$OUT"
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$OUT"
fi
