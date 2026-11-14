#!/usr/bin/env bash
# adb 通道「只检查」守口脚本：看调试开关开没开、adb 在不在线、root 行不行。
#
# 背景：真机 root 通道 = adb 127.0.0.1:<端口>（无线调试随机端口，如实测 42777；旧 tcpip 模式才是 5555），KernelSU 下 shell 即 root。它不是常驻：
# 关「USB 调试」/「无线调试」开关、切换开关、重启都会让它消失；adb root 等于全机 root。
#
# 设计（按安全考虑修订）：
#   - **本脚本不自动关任何开关**，也不执行 adb usb / settings put 去改设置；
#   - 只做检查 + 提醒：把 `adb_enabled`（设置里的「USB 调试」）、`adb_wifi_enabled`（无线调试）
#     当前值读出来给人看；关闭由用户自己在开发者选项里手动操作；
#   - 原因：`adb usb` 只切换 adbd 模式，不等于关设置开关；脚本改 settings 容易出现
#     “以为关了、设置里其实还开着”的误判，所以交给用户手动关最可靠。
#
# 用法:
#   bash scripts/device_adb_guard.sh status      # 检查：自动发现 serial、adb/设备/root/两个调试开关/是否重启过
#   bash scripts/device_adb_guard.sh open-hint   # 恢复步骤（含设置路径；端口随机，别写死）
#   bash scripts/device_adb_guard.sh policy      # 什么时候开、什么时候该手动关
#   bash scripts/device_adb_guard.sh [--serial SERIAL] status   # 覆盖自动发现的 serial
set -u

# 共享 adb 自动发现（无线调试端口随机：扫描监听端口并自动 connect）
HERE_DIR=$(cd "$(dirname "$0")" && pwd)
[ -f "$HERE_DIR/adb_common.sh" ] && . "$HERE_DIR/adb_common.sh"

# ── 自动发现在线 adb 设备（无线调试端口是随机的，不一定是 5555）──────────
# 规则：ADB_SERIAL / --serial > 5555（旧 tcpip 端口，在线才用）> adb devices 首个真机（跳过 emulator-*）
SERIAL_DEFAULT="127.0.0.1:5555"     # 旧 tcpip 固定端口：仅作自动发现候选，无线调试不用它
resolve_serial() { adb_resolve_serial "${ADB_BIN:-adb}" "${SERIAL_DEFAULT:-127.0.0.1:5555}"; }
list_devices() { "$ADB_BIN" devices 2>/dev/null | sed -n '2,$p' | sed '/^$/d'; }

ADB_BIN="${ADB_BIN:-adb}"
SERIAL="${ADB_SERIAL:-}"

ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --serial) shift; SERIAL="${1:-$SERIAL}" ;;
        --serial=*) SERIAL="${1#*=}" ;;
        *) ARGS+=("$1") ;;
    esac
    shift
done
SUB="${ARGS[0]:-status}"


green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
yel()   { printf '\033[33m%s\033[0m\n' "$*"; }

online() {
    command -v "$ADB_BIN" >/dev/null 2>&1 || return 1
    [ -n "${SERIAL:-}" ] || return 1
    "$ADB_BIN" -s "$SERIAL" get-state 2>/dev/null | grep -q device
}
adb_s() { "$ADB_BIN" -s "$SERIAL" shell "$@"; }
setting_get() { adb_s settings get global "$1" 2>/dev/null | tr -d '\r' | head -1; }

fmt_switch() {
    case "${1:-}" in
        1) echo "开(1)" ;;
        0) echo "关(0)" ;;
        "") echo "读不到" ;;
        null) echo "null（该 ROM 无此键）" ;;
        *) echo "未知($1)" ;;
    esac
}

# 5555 是否监听只作说明：无线调试端口随机，在线与否看下面的「连接」，不用 5555 判断通道
tcpip_hint() {
    python3 - <<'PY' 2>/dev/null
hit=False
for f in ('/proc/net/tcp','/proc/net/tcp6'):
    try: lines=open(f).read().splitlines()[1:]
    except OSError: continue
    for l in lines:
        p=l.split()
        if len(p)>3 and p[1].endswith(':15B3'):
            print('  5555(tcpip 模式): 有监听（adbd 在 5555；与无线调试随机端口无关）'); hit=True; break
    if hit: break
if not hit: print('  5555(tcpip 模式): 无监听（正常；无线调试走随机端口，不靠 5555）')
PY
}

uptime_hint() {
    local up btime bootstr
    up=$(awk '{print int($1)}' /proc/uptime 2>/dev/null || echo 0)
    btime=$(awk '/^btime/{print $2}' /proc/stat 2>/dev/null || echo 0)
    [ "$btime" = "0" ] && return
    bootstr=$(date -d "@$btime" '+%Y-%m-%d %H:%M' 2>/dev/null || echo '?')
    echo "  系统 uptime: $((up/3600))h（开机于 $bootstr）"
    if [ "$up" -lt 1800 ]; then
        yel "  → 刚重启过（<30 分钟）：adb 模式重启必丢，属正常。"
    fi
}



case "$SUB" in
  status|check)
    echo "══════ adb 通道检查（只读，不改任何开关） ══════"
    if ! command -v "$ADB_BIN" >/dev/null 2>&1; then
        red "  adb 未安装（apt-get install -y android-tools-adb）"; exit 1
    fi
    # 只在 status 里做自动发现：close/open-hint/policy 不探测 adb，保证零调用
    if [ -z "${SERIAL:-}" ]; then SERIAL="$(resolve_serial)"; fi
    echo "  adb: $("$ADB_BIN" version 2>/dev/null | head -1)"
    echo "  目标（自动发现）: ${SERIAL:-（未发现在线 adb 设备）}"
    tcpip_hint
    uptime_hint
    echo
    if online; then
        DEVUID=$(adb_s id -u 2>/dev/null | tr -d '\r')
        CTX=$(adb_s 'id | grep -o "context=[^ ]*"' 2>/dev/null | tr -d '\r')
        echo "  连接: 在线"
        echo "  设置里的「USB 调试」开关 (global adb_enabled): $(fmt_switch "$(setting_get adb_enabled)")"
        echo "  设置里的「无线调试」开关 (global adb_wifi_enabled): $(fmt_switch "$(setting_get adb_wifi_enabled)")"
        if [ "$DEVUID" = "0" ]; then
            green "  root: 可用 (id -u=0 ${CTX:-})"
            green "  结论: 通道可用（用 adb 优先操控，见 device_ui.sh）。"
        else
            yel "  连接正常但非 root（id -u=${DEVUID:-?}）：只能装包/看日志，动态 Hook 不行"
        fi
        echo
        echo "  用完请自己在设置里关（本脚本不会自动关）："
        echo "    设置 → 开发者选项 → 关闭「USB 调试」和「无线调试」"
        exit 0
    fi
    red "  连接: 离线（${SERIAL:-未发现在线 adb 设备}）"
    echo "  → 端口是自动发现的：无线调试端口随机（不是固定 5555），看无线调试页显示的端口或 adb devices。"
    yel "  设置里的「USB 调试」开关: 离线读不到（adb 不通时无法读取 settings）"
    yel "  设置里的「无线调试」开关: 离线读不到"
    echo "  → 离线常见原因：USB 调试/无线调试被关、切换过开关、重启过、换过网络。"
    echo "  → 想开：bash scripts/device_adb_guard.sh open-hint（只能人手动开）"
    echo "  → 不想开：如实说明并走静态路径（不要静默降级成纯视觉）。"
    exit 1
    ;;
  close)
    # 按安全考虑移除自动关闭：不再改 settings，也不再 adb usb。
    echo "══════ 自动关闭已移除 ══════"
    echo "本脚本不再自动关 adb/USB 调试（避免“以为关了、设置里还开着”的误判）。"
    echo "请手动关闭：设置 → 开发者选项 → 关闭「USB 调试」和「无线调试」。"
    echo "关闭后可用 status 复查（在线时能看到两个开关的值；离线说明已断）。"
    exit 0
    ;;
  open-hint)
    cat <<'EOF'
══════ 打开 adb root 通道（需要人工操作） ══════
【设置在哪（厂商不同，路径略有差异）】
  · ColorOS / OPPO / 真我：设置 → 系统设置（或其他设置）→ 开发者选项
      （没开开发者选项：设置 → 关于本机 → 版本信息 → 连点「版本号」7 次）
  · 原生 / AOSP：设置 → 系统 → 开发者选项
  里面有「USB 调试」「无线调试」两个开关。

【路线 1 · 无线调试（端口随机，如实测 42777，不是固定 5555）】
  1) 开发者选项 → 无线调试 打开
  2) 「使用配对码配对」记下 IP:端口 与 6 位配对码
  3) adb pair <IP>:<配对端口>     # 输入配对码
     adb connect <IP>:<调试端口>  # 端口看无线调试页，每次可能不同
  4) adb devices                    # 从这里看当前在线端口（status 会自动发现）

【路线 2 · USB 线（最稳；tcpip 固定端口 5555 是可选的）】
  1) 手机连 USB；开发者选项 → USB 调试 打开
  2) adb devices
     adb tcpip 5555
     adb connect 127.0.0.1:5555
  3) bash scripts/adb_device.sh check

【说明】
  · 开/关调试开关都由用户手动操作；AI 只在开工时 status 检查并提醒，不代开、不代关、不改设置。
  · 无线调试端口是随机的（实测 42777），不要写死 5555；各脚本会自动发现。
EOF
    ;;
  policy)
    cat <<'EOF'
══════ adb 通道规则 ══════
开：只在本次需要真机动态（Frida/抓包/改内存）或真机验证（装/卸/日志/截图/点击）时开。
不用：纯静态改包（广告组件清理/适配/数值）不需要 adb，别开。
用：adb 在线时优先用 adb 做安装/启动/读界面/点击/输入（scripts/device_ui.sh），
    不要因为“安全”绕开 adb 去用纯视觉；只有 adb 离线才提示用户开。
检查：开工 `device_adb_guard.sh status` 看两个开关值（只读，不改）。
关：AI **不自动关**；任务结束/连公共网络/长时间不用时，由用户手动在开发者选项里关。
红线：不开公网端口转发；adb devices 出现陌生设备先 disconnect；不装来路不明 APK。
EOF
    ;;
  -h|--help|"")
    sed -n '2,18p' "$0" 2>/dev/null
    ;;
  *)
    red "未知子命令: $SUB"
    sed -n '2,18p' "$0" 2>/dev/null
    exit 2
    ;;
esac
