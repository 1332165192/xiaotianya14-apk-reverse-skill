#!/usr/bin/env bash
# run_frida.sh — 在真机上跑本目录的 Frida 脚本（spawn 或 attach）
# 用法:
#   bash scripts/frida/run_frida.sh -s ssl_unpinning.js -p com.example.app
#   bash scripts/frida/run_frida.sh -s anti_debug_bypass.js -n 进程名
# 前置: 设备已 root 并起好 frida-server（见 scripts/frida_server_prep.sh）
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPT=""; APP=""; NAME=""; SPAWN=0
while [ $# -gt 0 ]; do
  case "$1" in
    -s|--script) SCRIPT="${2:?}"; shift 2 ;;
    -p|--package) APP="${2:?}"; SPAWN=1; shift 2 ;;
    -n|--name) NAME="${2:?}"; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
done
[ -n "$SCRIPT" ] || { echo "缺 -s <脚本>"; exit 2; }
F="$HERE/$SCRIPT"; [ -f "$F" ] || { echo "脚本不存在: $F"; exit 2; }
if [ -n "$APP" ]; then
  echo "spawn: $APP"
  exec frida -U -f "$APP" -l "$F" --no-pause
elif [ -n "$NAME" ]; then
  echo "attach: $NAME"
  exec frida -U -n "$NAME" -l "$F"
else
  echo "需要 -p 包名 或 -n 进程名"; exit 2
fi
