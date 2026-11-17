#!/usr/bin/env bash
# frida-server 准备/检查/收尾小工具（动态 Hook 用）
#
# 真机 root 通道可用时（adb -s <自动发现的 serial> 即 root），AI 可以全自动：
#   bash scripts/adb_device.sh frida start     # 推送 + root 启动 + frida-ps 验证（默认端口 27043）
# 本脚本优先检测这条自动通道；仍保留 Termux 手动兜底流程，供 adb 不可用时使用。
#
# 用法:
#   bash scripts/frida_server_prep.sh              # 检测 adb 自动通道 + 打印兜底 Termux 操作卡
#   bash scripts/frida_server_prep.sh --auto       # 直接走 adb 自动启动（等价 adb_device.sh frida start）
#   bash scripts/frida_server_prep.sh --status     # 检查是否已启动（优先用 adb_device.sh 验证）
#   bash scripts/frida_server_prep.sh --stop-hint  # 打印/给出停止方式
#   bash scripts/frida_server_prep.sh --port 8888  # 自定义端口（默认 27043；27042 是 宿主自带实例，别用）
#   bash scripts/frida_server_prep.sh --check      # 只检查本地文件，不复制
#   bash scripts/frida_server_prep.sh --serial SERIAL   # 指定 adb 目标（省略时自动发现：ADB_SERIAL > 5555 > adb devices 首个真机）
set -u

VER="17.26.2"
SRC="/root/tools/frida-server-${VER}-android-arm64"
DL_BASE="${DL_BASE:-/sdcard/Download}"
DST_DIR="${DST_DIR:-$DL_BASE/DSH-Go}"
DST="$DST_DIR/frida-server-${VER}-arm64"
PORT="27043"                     # 27042 是 宿主自带实例，禁止使用
MODE="prep"
SERIAL="${ADB_SERIAL:-}"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ADB_DEVICE="$SCRIPT_DIR/adb_device.sh"

while [ $# -gt 0 ]; do
    case "$1" in
        --status) MODE="status" ;;
        --stop-hint) MODE="stop" ;;
        --check) MODE="check" ;;
        --auto) MODE="auto" ;;
        --port) shift; PORT="${1:-27043}" ;;
        --serial) shift; SERIAL="${1:-$SERIAL}" ;;
        -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
        *) echo "未知参数: $1"; exit 2 ;;
    esac
    shift
done

ADB_BIN="${ADB_BIN:-adb}"
# 旧 tcpip 固定端口：仅作自动发现候选（无线调试端口是随机的，不一定是 5555）
SERIAL_DEFAULT="127.0.0.1:5555"
resolve_serial() {
    [ -n "${ADB_SERIAL:-}" ] && { printf '%s' "$ADB_SERIAL"; return; }
    command -v "$ADB_BIN" >/dev/null 2>&1 || return 0
    if "$ADB_BIN" -s "$SERIAL_DEFAULT" get-state 2>/dev/null | grep -q device; then
        printf '%s' "$SERIAL_DEFAULT"; return
    fi
    "$ADB_BIN" devices 2>/dev/null | awk 'NR>1 && $2=="device" && $1 !~ /^emulator-/ {print $1; exit}'
}
if [ -z "${SERIAL:-}" ]; then SERIAL="$(resolve_serial)"; fi
ADB_ARGS=()
[ -n "${SERIAL:-}" ] && ADB_ARGS+=(--serial "$SERIAL")

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
yel()   { printf '\033[33m%s\033[0m\n' "$*"; }

# ── 先探测 adb root 自动通道（不改变原有退出码语义）──────────────────────
ADB_OK=0
if [ -f "$ADB_DEVICE" ] && bash "$ADB_DEVICE" "${ADB_ARGS[@]}" check >/dev/null 2>&1; then
    ADB_OK=1
fi
# adb_device.sh 可能靠它自己的自动发现连上；这里同步一下显示的 serial
if [ "$ADB_OK" -eq 1 ] && [ -z "${SERIAL:-}" ]; then
    SERIAL="$(resolve_serial)"
    [ -n "${SERIAL:-}" ] && ADB_ARGS=(--serial "$SERIAL")
fi

# ── --auto：直接走 adb 自动启动 ─────────────────────────────────────────
if [ "$MODE" = "auto" ]; then
    if [ "$ADB_OK" -ne 1 ]; then
        red "adb root 通道不可用（先跑 bash scripts/adb_device.sh check 看原因）。"
        echo "→ 回退手动方式：bash scripts/frida_server_prep.sh（打印 Termux 操作卡）"
        exit 1
    fi
    green "检测到真机 root 通道（${SERIAL:-自动发现}），走 adb 自动启动（端口 $PORT）"
    exec bash "$ADB_DEVICE" "${ADB_ARGS[@]}" frida start --port "$PORT"
fi

# ── --status：AI 用来确认是否已经起好 ──────────────────────────────────
if [ "$MODE" = "status" ]; then
    if [ "$ADB_OK" -eq 1 ] && [ "$PORT" = "27043" ]; then
        green "检测到 adb root 通道，直接用 adb_device.sh 验证："
        exec bash "$ADB_DEVICE" "${ADB_ARGS[@]}" frida status
    fi
    if ! command -v frida-ps >/dev/null 2>&1; then
        red "frida-ps 不在 PATH（pip 的 frida-tools 没装？）"
        exit 1
    fi
    out=$(timeout 12 frida-ps -H "127.0.0.1:${PORT}" 2>&1)
    if [ $? -eq 0 ]; then
        green "已连上 frida-server（127.0.0.1:${PORT}），进程前几行："
        echo "$out" | head -8
        exit 0
    fi
    red "还没连上（127.0.0.1:${PORT}）：$(echo "$out" | head -2)"
    echo "→ 让用户按操作卡起 frida-server，或检查版本/端口/SELinux。"
    exit 1
fi

# ── --stop-hint ─────────────────────────────────────────────────────────
if [ "$MODE" = "stop" ]; then
    if [ "$ADB_OK" -eq 1 ]; then
        green "adb root 通道可用，可直接停止本脚本/自动通道启动的实例："
        echo "  bash scripts/adb_device.sh frida stop"
    fi
    cat <<EOF
手动兜底（Termux 里起的话）：

  su -c 'pkill -f frida-server'
  # 或者：su -c 'kill \$(pidof frida-server)'

关闭后 AI 再跑 --status 会显示连不上，属正常。
EOF
    exit 0
fi

# ── 文件检查 ────────────────────────────────────────────────────────────
if [ ! -f "$SRC" ]; then
    red "找不到 $SRC"
    echo "→ 按 references/mobile-toolchain.md 重新下载同版本 frida-server，或先跑 toolcheck.sh 看版本。"
    exit 1
fi
if ! python3 -c "import frida,sys; sys.exit(0 if frida.__version__=='$VER' else 1)" 2>/dev/null; then
    yel "注意：pip frida 版本与 $VER 不一致，连不上；先对齐版本再继续。"
fi

if [ "$MODE" = "check" ]; then
    green "本机已有 $SRC（$(du -h "$SRC" | cut -f1)），版本 $VER 与客户端一致。"
    [ "$ADB_OK" -eq 1 ] && green "adb root 通道可用（${SERIAL:-自动发现}），AI 可自动起：bash scripts/adb_device.sh frida start"
    exit 0
fi

# ── prep：打印自动通道结论 + 保留 Termux 兜底卡 ─────────────────────────
if [ "$ADB_OK" -eq 1 ]; then
    echo
    green "══════ 检测到真机 root 通道（${SERIAL:-自动发现}，adbd 已是 root）══════"
    echo "✅ AI 可自动起 frida-server（adb root），无需你手动 Termux："
    echo "     bash scripts/adb_device.sh frida start --port $PORT"
    echo "     起好后：bash scripts/adb_device.sh frida status   # frida-ps -H 127.0.0.1:$PORT 验证"
    echo "     停止：  bash scripts/adb_device.sh frida stop"
    echo "   （本脚本的 --auto 等价于上面第一条：bash scripts/frida_server_prep.sh --auto）"
    echo
    echo "↓ 以下 Termux 操作卡仅作兜底（adb 不可用时）"
    echo
else
    yel "未检测到可用的 adb root 通道（bash scripts/adb_device.sh check 看原因），走手动兜底流程。"
    echo
fi

mkdir -p "$DST_DIR" || { red "无法创建 $DST_DIR"; exit 1; }
cp -f "$SRC" "$DST" || { red "复制失败：$DST"; exit 1; }
chmod 755 "$DST" 2>/dev/null || true
SIZE=$(du -h "$DST" | cut -f1)
green "已复制到：$DST（$SIZE）"
echo
cat <<EOF
══════════════════════════════════════════════════════════
 兜底操作卡（仅当 adb root 通道不可用；复制方框里的命令到手机 root 终端）
══════════════════════════════════════════════════════════
 打开哪个终端：手机上的 Termux（推荐，已安装）→ 输入 su 回车 → root 管理器（KernelSU/Magisk 等）弹"授权"点允许
               （或在 root 管理器里授权后，用任意支持 su 的终端）

 在 Termux 里依次粘贴执行（3 条）：
┌────────────────────────────────────────────────────────┐
  su
  cp ${DST_DIR}/frida-server-${VER}-arm64 /data/local/tmp/frida-server
  chmod 755 /data/local/tmp/frida-server && /data/local/tmp/frida-server -l 127.0.0.1:${PORT} &
└────────────────────────────────────────────────────────┘

 （第 3 条执行后没报错就是起好了；窗口回到普通提示符属正常，别关 Termux）
 端口默认 27043。注意：27042 是 宿主自带实例，别用。
 要反检测可换端口：/data/local/tmp/frida-server -l 127.0.0.1:${PORT} &

 AI 验证：bash scripts/frida_server_prep.sh --status
 用完关闭：bash scripts/frida_server_prep.sh --stop-hint
══════════════════════════════════════════════════════════
EOF
