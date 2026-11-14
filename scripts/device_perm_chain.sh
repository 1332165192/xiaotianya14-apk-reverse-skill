#!/usr/bin/env bash
# 权限链路检测（只读 v2）——分两层回答，避免「没有 adb 就查不了 root」的循环论证：
#
#   ① 能力层（唯一算「真检查」的）：真的提一次权，用**真实特权操作**（读 root-only 路径）验，
#      不看 `id -u`——proot 里 uid 恒显示 0，是假根。入口四条：
#        adb root（无线调试/USB）> 本机 su > App 侧 su（KernelSU/Magisk 授权本应用）> Shizuku(rish，只能 shell 级)
#   ② 迹象层（没有任何入口时，回答「设备有没有 root 方案」）：
#        /proc/modules 里 kernelsu 模块 / su「stat 得见、open ENOENT」的隐藏特征 / 内核版本后缀 /
#        verifiedbootstate·flash.locked / root 管理器与 Shizuku 是否安装（adb 在线时直接查包名）
#      **迹象 ≠ 能力**：设备有 KernelSU 不代表本进程能用 root（未授权时 su 被内核隐藏）。
#
# 本脚本只读：不启动/关闭 adb、不配对 Shizuku、不改 settings、不代用户授权。
#
# 用法:
#   bash scripts/device_perm_chain.sh            # 完整报告（能力层 + 迹象层 + 结论）
#   bash scripts/device_perm_chain.sh --channel  # 只打印通道名：adb-root|local-root|app-root|adb-shell|rish|none
#   bash scripts/device_perm_chain.sh -h         # 帮助
#   exit: 0=有真 root 能力  2=仅 shell 级能力  1=无能力（只能查迹象）
set -u

HERE_DIR=$(cd "$(dirname "$0")" && pwd)
[ -f "$HERE_DIR/adb_common.sh" ] && . "$HERE_DIR/adb_common.sh"

ADB_BIN="${ADB_BIN:-adb}"
SERIAL="${ADB_SERIAL:-}"
MODE="report"
case "${1:-}" in
    --channel) MODE="channel" ;;
    -h|--help) MODE="help" ;;
    "") ;;
    *) echo "未知参数: $1（用 -h 看用法）" >&2; exit 1 ;;
esac

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
yel()   { printf '\033[33m%s\033[0m\n' "$*"; }

if [ "$MODE" = "help" ]; then
    sed -n '2,/^set -u/p' "$0" | grep -v '^set -u' | sed 's/^# \{0,1\}//'
    exit 0
fi

# 真实特权操作：能读到这些 root-only 路径之一，才算「真的提权成功了」（不看 uid 显示）
PRIV_TEST='for d in /data/adb /data/misc/adb /data/system/users/0; do [ -r "$d" ] && { echo REAL; break; }; done'
real_priv() {  # real_priv <命令...>（命令里自己执行 PRIV_TEST）
    timeout 12 "$@" 2>/dev/null | tr -d '\r' | grep -q REAL
}

# ── ① 能力层：逐条尝试入口 ───────────────────────────────────────
ADB_INSTALLED=1; command -v "$ADB_BIN" >/dev/null 2>&1 || ADB_INSTALLED=0
ADB_ONLINE=0; ADB_PRIV=0; DEV_UID=""; DEV_CTX=""
if [ "$ADB_INSTALLED" = "1" ]; then
    [ -n "${SERIAL:-}" ] || SERIAL="$(adb_resolve_serial "$ADB_BIN" 127.0.0.1:5555 2>/dev/null || true)"
    if [ -n "${SERIAL:-}" ] && "$ADB_BIN" -s "$SERIAL" get-state 2>/dev/null | grep -q device; then
        ADB_ONLINE=1
        DEV_UID=$("$ADB_BIN" -s "$SERIAL" shell id -u 2>/dev/null | tr -d '\r' | head -1)
        DEV_CTX=$("$ADB_BIN" -s "$SERIAL" shell 'id | grep -o "context=[^ ]*"' 2>/dev/null | tr -d '\r' | head -1)
        real_priv "$ADB_BIN" -s "$SERIAL" shell "$PRIV_TEST" && ADB_PRIV=1
    fi
fi

LOCAL_PRIV=0
if command -v su >/dev/null 2>&1; then
    real_priv su -c "$PRIV_TEST" && LOCAL_PRIV=1
fi

APP_SU_PRESENT=0; APP_SU_READ=0; APP_PRIV=0
[ -e /system/bin/su ] && APP_SU_PRESENT=1
if [ "$APP_SU_PRESENT" = "1" ] && cat /system/bin/su >/dev/null 2>&1; then
    APP_SU_READ=1
    real_priv /system/bin/su -c "$PRIV_TEST" && APP_PRIV=1
fi

RISH_AVAILABLE=0; RISH_UID=""
if command -v rish >/dev/null 2>&1; then
    RISH_UID=$(timeout 12 rish -c 'id -u' 2>/dev/null | tr -d '\r' | tail -1)
    case "${RISH_UID:-}" in 0|2000) RISH_AVAILABLE=1 ;; esac
fi

# ── ② 迹象层：没有入口时仍可回答「设备有没有 root 方案」 ─────────
KSU_MODULE=""
if [ -r /proc/modules ]; then
    KSU_MODULE=$(grep -m1 -oi 'kernelsu' /proc/modules 2>/dev/null || true)
fi
KSU_SYMS=""
if [ -z "$KSU_MODULE" ] && [ -r /proc/kallsyms ]; then
    KSU_SYMS=$(timeout 20 grep -m1 -o '\[kernelsu\]' /proc/kallsyms 2>/dev/null || true)
fi
KVER_SUFFIX=$(grep -m1 -oiE 'kernelsu|apatch|magisk' /proc/version 2>/dev/null || true)
VBSTATE=$(/system/bin/getprop ro.boot.verifiedbootstate 2>/dev/null | head -1)
FLASH_LOCK=$(/system/bin/getprop ro.boot.flash.locked 2>/dev/null | head -1)
SELF_CTX=$(cat /proc/self/attr/current 2>/dev/null | cut -d: -f3 | head -1)
ROOT_MGR="未知（需 adb 或 MCP 查包名）"
if [ "$ADB_ONLINE" = "1" ]; then
    ROOT_MGR=$("$ADB_BIN" -s "$SERIAL" shell 'pm list packages 2>/dev/null | grep -iE "weishu.kernelsu|topjohnwu.magisk|bmax.apatch|shizuku"' 2>/dev/null | tr -d '\r' | sed 's/package://' | paste -sd, -)
    [ -n "$ROOT_MGR" ] || ROOT_MGR="未安装（KernelSU/Magisk/APatch/Shizuku 都没查包到）"
fi

# ── 通道选择（只认能力层）───────────────────────────────────────
CHANNEL="none"; EXITCODE=1; ABILITY="无真机通道：静态改包 + 重签名；真机验证走 MCP 点屏"
if [ "$ADB_PRIV" = "1" ]; then
    CHANNEL="adb-root"; EXITCODE=0; ABILITY="真 root：settings/装包/日志/frida-server(27043)/root 抓包"
elif [ "$LOCAL_PRIV" = "1" ]; then
    CHANNEL="local-root"; EXITCODE=0; ABILITY="真 root（本机 su）：同 adb-root"
elif [ "$APP_PRIV" = "1" ]; then
    CHANNEL="app-root"; EXITCODE=0; ABILITY="真 root（App 侧 su 授权）：同 adb-root"
elif [ "$ADB_ONLINE" = "1" ]; then
    CHANNEL="adb-shell"; EXITCODE=2; ABILITY="shell 级：pm 装包/日志/截图/读 settings；不能 frida-server/root 抓包"
elif [ "$RISH_AVAILABLE" = "1" ] && [ "${RISH_UID:-}" = "2000" ]; then
    CHANNEL="rish"; EXITCODE=2; ABILITY="shell 级（Shizuku rish, uid=2000）：同 adb-shell"
fi

if [ "$MODE" = "channel" ]; then printf '%s\n' "$CHANNEL"; exit "$EXITCODE"; fi

# ── 报告 ───────────────────────────────────────────────────────
echo "══════ 权限链路检测（只读：能力层 + 迹象层） ══════"
echo "  adb: $([ "$ADB_INSTALLED" = 1 ] && "$ADB_BIN" version 2>/dev/null | head -1 || echo '未安装')"
echo "  adb 设备: ${SERIAL:-（未发现在线设备）}$([ "$ADB_ONLINE" = 1 ] && echo '（在线）')"
yel "  ⚠ proot 内 id -u 恒显示 0（假根）；下面能力层一律用「真实读 /data/adb 等路径」判定，不看 uid"
echo
echo "  ── ① 能力层（真的提权成功才算）──"
if [ "$ADB_ONLINE" = "1" ]; then
    if [ "$ADB_PRIV" = "1" ]; then green "  adb root : 真 root 成功（uid=${DEV_UID:-?} ${DEV_CTX:-}，能读 /data/adb）"
    elif [ "$DEV_UID" = "0" ]; then yel "  adb root : uid 显示 0 但读不到 /data/adb（可疑，按无 root 处理）"
    else yel "  adb shell: 在线但非 root（uid=${DEV_UID:-?}）→ 只 shell 级"; fi
else
    yel "  adb root : 无 adb（离线/未开调试）"
fi
if [ "$LOCAL_PRIV" = "1" ]; then green "  本机 su  : 真 root 成功"
elif command -v su >/dev/null 2>&1; then echo "  本机 su  : 有 su 命令但提权失败（proot 内属正常）"
else echo "  本机 su  : 无 su 命令"; fi
if [ "$APP_PRIV" = "1" ]; then
    green "  App 侧 su: 真 root 成功（本应用已被 root 管理器授权）"
elif [ "$APP_SU_PRESENT" = "1" ] && [ "$APP_SU_READ" = "0" ]; then
    yel "  App 侧 su: /system/bin/su 存在但打不开（stat 可见、open ENOENT）→ 本进程未获授权（SELinux=${SELF_CTX:-?}）"
elif [ "$APP_SU_PRESENT" = "1" ]; then
    yel "  App 侧 su: 可读但提权失败 → 可能未授权/被拒"
else
    echo "  App 侧 su: /system/bin/su 不存在（该机 root 方案可能不提供，或已隐藏）"
fi
if [ "$RISH_AVAILABLE" = "1" ]; then
    green "  rish     : 可用（Shizuku → uid=${RISH_UID}，$( [ "${RISH_UID:-}" = 0 ] && echo 'root' || echo '仅 shell 级' )）"
elif command -v rish >/dev/null 2>&1; then
    yel "  rish     : 有 rish 命令但连不上 Shizuku（未运行/未授权）"
else
    echo "  rish     : 未找到（Shizuku 的 CLI 外壳；装了 Shizuku 不等于能用 rish）"
fi
echo
echo "  ── ② 迹象层（设备有没有 root 方案，≠ 你能提权）──"
if [ -n "$KSU_MODULE" ]; then green "  KernelSU  : 内核模块已加载（/proc/modules: kernelsu）"
elif [ -n "$KSU_SYMS" ]; then green "  KernelSU  : 内核符号可见（/proc/kallsyms: [kernelsu]）"
else echo "  KernelSU  : 未发现内核特征"; fi
if [ "$KVER_SUFFIX" != "" ]; then echo "  内核版本  : 带后缀 $KVER_SUFFIX"; else echo "  内核版本  : 无 KSU/APatch/Magisk 后缀（LKM 方案不会改版本号，属正常）"; fi
if [ "$APP_SU_PRESENT" = "1" ] && [ "$APP_SU_READ" = "0" ]; then
    green "  su 隐藏   : 命中（stat 有 / open ENOENT = KernelSU 对未授权进程的隐藏特征）"
else
    echo "  su 隐藏   : 未命中"
fi
echo "  适配状态  : verifiedbootstate=${VBSTATE:-?} flash.locked=${FLASH_LOCK:-?}（locked 也可能通过内核集成 KSU）"
echo "  Root 管理器: ${ROOT_MGR}"
echo "  ─────────────────────────────────────────────"
case "$CHANNEL" in adb-root|local-root|app-root) green "  可用通道: $CHANNEL（能力层判定，真 root）" ;;
    adb-shell|rish) yel "  可用通道: $CHANNEL（能力层判定，仅 shell 级）" ;;
    *) red "  可用通道: none（能力层未发现任何入口 → 「能不能用 root」无法验证）" ;; esac
echo "  ▸ 能力: $ABILITY"
if [ -n "$KSU_MODULE$KSU_SYMS" ] && [ "$EXITCODE" != "0" ]; then
    yel "  ▸ 迹象结论: 设备已加载 KernelSU（root 方案存在），但本进程没拿到授权；想用 root 需用户在 KernelSU 里给 App 授权，或开 adb 通道"
fi
case "$CHANNEL" in
    adb-root|adb-shell) echo "  ▸ 操作入口: device_ui.sh（界面）/ adb_device.sh（装、日志、frida、抓包）/ device_adb_guard.sh（开关只读复核）" ;;
    rish|app-root|local-root) echo "  ▸ 注意: 无 adb 时 frida/root 抓包仍受限制，按能力层结论用" ;;
    none) red "  ▸ 降级: 静态改包 → MCP 点屏验证；用前如实告诉用户差在哪" ;;
esac
if [ "$EXITCODE" != "1" ]; then
    echo "  ▸ 收工: 两个调试开关由用户手动关（AI 不代关；device_adb_guard.sh status 只读复核）"
fi
exit "$EXITCODE"
