#!/bin/bash
# decode.sh — 手机端 APK 一键解码（jadx Java 源码 + apktool smali/资源）+ Triage 摘要
# 手机版适配：默认输出到 /sdcard/Download/deapk-work；jadx 在 /root/jadx/bin/jadx
#
# 用法:
#   bash decode.sh <apk_path> [--name 任务名] [--out 输出根目录]
#                   [--skip-jadx] [--skip-apktool] [--clean]
#   bash decode.sh --summary-only <apktool解码目录>     # 已解码，只打印摘要
set -uo pipefail

APK_PATH=""; TASK_NAME=""; OUT_ROOT=""; SKIP_JADX=false; SKIP_APKTOOL=false; CLEAN=false; SUMMARY_ONLY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) TASK_NAME="$2"; shift 2 ;;
    --out) OUT_ROOT="$2"; shift 2 ;;
    --skip-jadx) SKIP_JADX=true; shift ;;
    --skip-apktool) SKIP_APKTOOL=true; shift ;;
    --clean) CLEAN=true; shift ;;
    --summary-only) SUMMARY_ONLY="$2"; shift 2 ;;
    -*) echo "未知选项: $1"; exit 1 ;;
    *) APK_PATH="$1"; shift ;;
  esac
done

print_summary() {
  local APKTOOL_OUT="$1" JADX_OUT="${2:-}"
  local PACKAGE="" JAVA=0 SMALI_DIRS=0 SO=0
  if [[ -f "$APKTOOL_OUT/AndroidManifest.xml" ]]; then
    PACKAGE=$(grep -oE 'package="[^"]*"' "$APKTOOL_OUT/AndroidManifest.xml" 2>/dev/null | head -1 | sed 's/package="//;s/"//')
    [[ -z "$PACKAGE" ]] && PACKAGE=$(grep -oE 'package="[^"]*"' "$APKTOOL_OUT/apktool.yml" 2>/dev/null | head -1 | sed 's/package="//;s/"//')
  fi
  [[ -d "$JADX_OUT" ]] && JAVA=$(find "$JADX_OUT" -name '*.java' 2>/dev/null | wc -l)
  [[ -d "$APKTOOL_OUT" ]] && SMALI_DIRS=$(find "$APKTOOL_OUT" -maxdepth 1 -type d -name 'smali*' 2>/dev/null | wc -l)
  [[ -d "$APKTOOL_OUT" ]] && SO=$(find "$APKTOOL_OUT" -name '*.so' 2>/dev/null | wc -l)
  echo ""
  echo "═══════════════════════════════════════════"
  echo "  APK 解码完成"
  echo "═══════════════════════════════════════════"
  echo "  apktool_out=$APKTOOL_OUT"
  [[ -n "$JADX_OUT" ]] && echo "  jadx_out=$JADX_OUT"
  echo "  package=$PACKAGE"
  echo "  java_files=$JAVA"
  echo "  smali_dirs=$SMALI_DIRS"
  echo "  so_files=$SO"
  echo "  下一步: analyze_ads.py / manifest_summary.py / 看 §4 广告定位"
}

if [[ -n "$SUMMARY_ONLY" ]]; then
  print_summary "$SUMMARY_ONLY" ""
  exit 0
fi

if [[ -z "$APK_PATH" || ! -f "$APK_PATH" ]]; then
  echo "用法: $0 <apk_path> [--name n] [--out dir] [--skip-jadx] [--skip-apktool] [--clean]"
  echo "     $0 --summary-only <apktool解码目录>"
  exit 1
fi

APK_BASENAME=$(basename "$APK_PATH" | sed 's/\.apk$//; s/[^A-Za-z0-9._-]/_/g')
TASK_NAME="${TASK_NAME:-$APK_BASENAME}"
OUT_ROOT="${OUT_ROOT:-/sdcard/Download/deapk-work}"
TASK_ROOT="$OUT_ROOT/$TASK_NAME"
JADX_OUT="$TASK_ROOT/jadx"
APKTOOL_OUT="$TASK_ROOT/apktool"
mkdir -p "$TASK_ROOT"
[[ "$CLEAN" == "true" ]] && rm -rf "$JADX_OUT" "$APKTOOL_OUT"

# 工具检查（手机版固定路径）
JADX_BIN="$(command -v jadx 2>/dev/null || true)"
[[ -z "$JADX_BIN" && -x /root/jadx/bin/jadx ]] && JADX_BIN=/root/jadx/bin/jadx
if [[ "$SKIP_JADX" != "true" && -z "$JADX_BIN" ]]; then
  echo "WARN: jadx 未找到（/root/jadx/bin/jadx）。先按 references/mobile-toolchain.md 安装，或 --skip-jadx"
  SKIP_JADX=true
fi
if [[ "$SKIP_APKTOOL" != "true" ]] && ! command -v apktool >/dev/null 2>&1; then
  echo "ERR: apktool 未安装（apt-get install apktool）"; exit 1
fi

# 1) jadx
if [[ "$SKIP_JADX" != "true" ]]; then
  echo "=== jadx 反编译（大包可能要 5-15 分钟，可后台跑）==="
  rm -rf "$JADX_OUT"
  "$JADX_BIN" -d "$JADX_OUT" -j 4 --no-debug-info --show-bad-code "$APK_PATH" 2>&1 | tail -2
  echo "jadx_exit=$?（部分类报错正常）"
fi

# 2) apktool（手机环境必须 --use-aapt2 才能在重建时不踩坑；解码本身不需要）
if [[ "$SKIP_APKTOOL" != "true" ]]; then
  echo "=== apktool 解包 ==="
  rm -rf "$APKTOOL_OUT"
  apktool d -f "$APK_PATH" -o "$APKTOOL_OUT" 2>&1 | tail -2
fi

print_summary "$APKTOOL_OUT" "$JADX_OUT"
