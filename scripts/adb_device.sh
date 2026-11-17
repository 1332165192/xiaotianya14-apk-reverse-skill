#!/usr/bin/env bash
# adb 真机 root 通道一键脚本（在 proot 里驱动真机：frida / tcpdump / logcat / 安装/截图）
#
# 背景：proot 内是普通 app uid（无 CAP_NET_RAW，不能直接起 frida-server、不能直接抓包），
# 但真机已开无线调试且 adbd 为 root（KernelSU：u:r:ksu:s0），
# `adb -s <自动发现的 serial> shell` 就是真正的 root。本脚本把它包成常用子命令。
#
# 用法:
#   bash scripts/adb_device.sh [--serial SERIAL] <子命令> [参数]   # serial 省略时自动发现（5555 在线 > adb devices 首个真机）
#
#   check                                     检测 adb/设备/root/Android 版本/frida-server/tcpdump
#   frida start [--port 27043]                推送 + root 启动 frida-server，等端口就绪后 frida-ps 验证
#   frida stop                                按 pid 文件停止本脚本启动的实例（绝不碰 27042）
#   frida status                              查看 pid/端口/frida-ps 连通性
#   tcpdump start [-i any] [--out PATH]       真机抓包（默认 /data/local/tmp/cap.pcap）
#   tcpdump stop                              停止本脚本启动的抓包
#   tcpdump pull <本地路径>                   拉回 pcap，并用本地 tcpdump 解析前几包
#   logcat [--grep RE] [--lines N] [--clear]  看崩溃/AndroidRuntime/FATAL/异常栈（默认已内置过滤）
#   install <apk> [--dry-run]                 adb install -r -d（--dry-run 只打印命令）
#   uninstall <pkg> --yes                     ！必须 --yes；拒绝系统/厂商包
#   clear <pkg> --yes                         ！必须 --yes；拒绝系统/厂商包
#   start <pkg> | stop <pkg> | info <pkg>     启动 / 强制停止 / 看包信息
#   screencap <本地.png>                      截图并拉回
#   push <local> <remote> / pull <remote> <local>
#
# 安全约定:
#   - serial 自动发现：ADB_SERIAL/--serial > 5555（旧 tcpip 端口，在线才用）> adb devices 首个真机；
#     多设备时用 --serial 显式指定；真模拟器（goldfish/ranchu/qemu）拒绝，真机桥接名不受影响
#   - frida 默认端口 27043；27042 是 宿主自带实例，脚本拒绝使用，也绝不终止它
#   - uninstall / clear 必须 --yes，且拒绝 com.android.* / com.google.android.* 等系统/厂商包
#   - 每步失败都打印原始输出（stderr），不静默吞错
set -u

# 共享 adb 自动发现（无线调试端口随机：扫描监听端口并自动 connect）
HERE_DIR=$(cd "$(dirname "$0")" && pwd)
[ -f "$HERE_DIR/adb_common.sh" ] && . "$HERE_DIR/adb_common.sh"

# ── 自动发现在线 adb 设备（无线调试端口是随机的，不一定是 5555）──────────
resolve_serial() { adb_resolve_serial "${ADB_BIN:-adb}" "${SERIAL_DEFAULT:-127.0.0.1:5555}"; }
list_devices() { "$ADB_BIN" devices 2>/dev/null | sed -n '2,$p' | sed '/^$/d'; }

ADB_BIN="${ADB_BIN:-adb}"
SERIAL_DEFAULT="127.0.0.1:5555"    # 旧 tcpip 固定端口：仅作自动发现候选（无线调试端口随机）
FRIDA_PORT_DEFAULT=27043
RESERVED_FRIDA_PORT=27042          # 宿主自带 frida-server 实例，禁止触碰
FRIDA_SRC="/root/tools/frida-server-17.26.2-android-arm64"
FRIDA_DEV="/data/local/tmp/frida-server"
FRIDA_PIDFILE="/data/local/tmp/frida-server.pid"
FRIDA_PORTFILE="/data/local/tmp/frida-server.port"

TD_BIN="/system/bin/tcpdump"
TD_OUT_DEFAULT="/data/local/tmp/cap.pcap"
TD_PIDFILE="/data/local/tmp/tcpdump.pid"
TD_OUTFILE="/data/local/tmp/tcpdump.out"
TD_IFACEFILE="/data/local/tmp/tcpdump.iface"
TD_LOG="/data/local/tmp/tcpdump.log"

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
yel()   { printf '\033[33m%s\033[0m\n' "$*"; }
cya()   { printf '\033[36m%s\033[0m\n' "$*"; }
die()   { red "错误: $*"; exit 1; }
say()   { printf '%s\n' "$*"; }

usage() { sed -n '2,31p' "$0"; }

# ── 参数解析：全局 --serial 可以出现在任何位置 ─────────────────────────────
SERIAL="${ADB_SERIAL:-}"
_pos=()
while [ $# -gt 0 ]; do
    case "$1" in
        --serial)   shift; [ $# -gt 0 ] || die "--serial 需要一个值"; SERIAL="$1" ;;
        --serial=*) SERIAL="${1#*=}" ;;
        -h|--help)  usage; exit 0 ;;
        *)          _pos+=("$1") ;;
    esac
    shift
done
if [ "${#_pos[@]}" -gt 0 ]; then
    set -- "${_pos[@]}"
else
    set --
    usage
    exit 2
fi
CMD="${1:-}"; shift || true
if [ -z "${SERIAL:-}" ]; then SERIAL="$(resolve_serial)"; fi
[ -n "${SERIAL:-}" ] || SERIAL="${SERIAL_DEFAULT}"


[ -n "$SERIAL" ] || die "serial 不能为空"
if _adb_is_true_emulator "$ADB_BIN" "$SERIAL"; then
    die "拒绝操作真模拟器（$SERIAL）：检测到 qemu/goldfish/ranchu 属性；真机桥接名不受影响"
fi

# ── 通用 helper ───────────────────────────────────────────────────────────
ADB_ROOT_MODE="${ADB_ROOT_MODE:-}"   # 空=未探测；su=KernelSU/超级用户；adbd=adbd 本身为 root；none=无 root

adb_raw() { "$ADB_BIN" -s "$SERIAL" "$@"; }

# 探测 root 通道：优先 su -c（KernelSU/超级用户），再回退 adbd 已是 root 的环境
# 不使用任何个人机型/序列号/账号信息，仅用通用系统状态判断。
detect_root_mode() {
    local out uid
    out=$(adb_raw shell su -c id 2>&1)
    case "$out" in *"uid=0"*) ADB_ROOT_MODE=su; return 0 ;; esac
    uid=$(adb_raw shell id -u 2>&1 | tr -d '\r\n')
    if [ "$uid" = "0" ]; then ADB_ROOT_MODE=adbd; return 0; fi
    ADB_ROOT_MODE=none
    return 1
}

# shell 子命令在 su 模式下自动用 su -c 执行；其它子命令（push/pull/install/get-state…）保持原样
adb_() {
    local sub="${1:-}"
    shift || true
    if [ "$sub" = "shell" ] && [ "${ADB_ROOT_MODE:-}" = "su" ]; then
        adb_raw shell su -c "$*"
    else
        adb_raw "$sub" "$@"
    fi
}

need_adb() {
    command -v "$ADB_BIN" >/dev/null 2>&1 \
        || die "找不到 adb（$ADB_BIN）→ apt-get install -y android-tools-adb 后重试"
}

ensure_device() {
    need_adb
    local st
    st=$(adb_ get-state 2>&1) || die "adb 设备 $SERIAL 不可用，原始输出: $st
→ 修法: adb connect $SERIAL（手机需开「无线调试」并允许 USB/网络调试授权）"
    st=$(printf '%s' "$st" | tr -d '\r\n')
    [ "$st" = "device" ] \
        || die "adb 设备 $SERIAL 状态=$st（不是 device）
→ 修法: 手机端确认无线调试未关闭；adb kill-server && adb connect $SERIAL"
}

ensure_root() {
    ensure_device
    if [ -z "${ADB_ROOT_MODE:-}" ]; then detect_root_mode || true; fi
    if [ "${ADB_ROOT_MODE:-none}" != "none" ]; then
        return 0
    fi
    local uid ksu_hint=""
    uid=$(adb_raw shell id -u 2>&1 | tr -d '\r\n')
    if adb_raw shell pm list packages 2>/dev/null | tr -d '\r' | grep -q 'me.weishu.kernelsu'; then
        ksu_hint="（检测到 KernelSU 管理端：请在 KernelSU → 超级用户里给「Shell / ADB」授权）"
    fi
    die "设备 $SERIAL 当前没有 root（id -u='$uid'）$ksu_hint
→ 修法: 在 KernelSU/超级用户里授权「Shell / ADB」后重试；或确认设备已开 root 通道"
}

# run_adb <描述> <args...>：失败时打印原始输出后退出
run_adb() {
    local desc="$1"; shift
    local out rc
    out=$("$ADB_BIN" -s "$SERIAL" "$@" 2>&1); rc=$?
    if [ "$rc" -ne 0 ]; then
        red "✗ $desc 失败 (rc=$rc)，原始输出："
        printf '%s\n' "$out"
        return "$rc"
    fi
    [ -n "$out" ] && printf '%s\n' "$out"
    return 0
}

# 设备端命令：失败打印原始输出
dev_shell() {                       # dev_shell <描述> <shell 命令串>
    local desc="$1" cmd="$2"
    local out rc
    out=$(adb_ shell "$cmd" 2>&1); rc=$?
    if [ "$rc" -ne 0 ]; then
        red "✗ $desc 失败 (rc=$rc)，原始输出："
        printf '%s\n' "$out"
        return "$rc"
    fi
    printf '%s' "$out"
    return 0
}

frida_client_ok() { command -v frida-ps >/dev/null 2>&1; }

# 检查设备端某 pid 是否存活（用 /proc，不依赖 kill -0 的 toybox 兼容性）
dev_pid_alive() {                    # dev_pid_alive <pid>
    local pid="$1" out
    out=$(adb_ shell "[ -d '/proc/$pid' ] && echo alive" 2>&1)
    printf '%s' "$out" | grep -q 'alive'
}

dev_read_file() {                    # dev_read_file <远端路径>
    adb_ shell "cat '$1' 2>/dev/null" 2>/dev/null | tr -d '\r\n'
}

# 端口是否处于 LISTEN（只认 st=0A，TIME_WAIT 不算占用；用 /proc/net/tcp*，不依赖 netstat）
dev_port_listen() {                  # dev_port_listen <端口>
    local port="$1" hex out
    printf -v hex '%04X' "$port"
    out=$(adb_ shell "awk 'NR>1 && \$4==\"0A\" {split(\$2,a,\":\"); if (toupper(a[2])==\"$hex\") print \$0}' /proc/net/tcp /proc/net/tcp6 2>/dev/null" 2>&1)
    printf '%s' "$out" | grep -q ':' && return 0
    return 1
}

# ── check ─────────────────────────────────────────────────────────────────
cmd_check() {
    local fail=0
    echo "══════ adb 真机 root 通道自检 ══════"
    say "目标 serial: $SERIAL"
    if command -v "$ADB_BIN" >/dev/null 2>&1; then
        green "  [OK]   adb: $("$ADB_BIN" version 2>&1 | head -1)"
        say "  adb devices:"
        "$ADB_BIN" devices 2>&1 | sed 's/^/    /'
    else
        red "  [缺]   adb 不在 PATH → apt-get install -y android-tools-adb"; fail=$((fail+1))
    fi
    local dev_st=""
    if [ "$fail" -eq 0 ]; then
        dev_st=$(adb_ get-state 2>&1 | tr -d '\r\n')
        if [ "$dev_st" = "device" ]; then
            green "  [OK]   设备在线: $SERIAL"
        else
            red "  [失败] 设备 $SERIAL 状态='$dev_st'（原始输出: $(adb_ get-state 2>&1)）"
            red "         → 看无线调试页面显示的端口（端口随机，每次可能不同），或 adb devices 找在线端口后重试"
            fail=$((fail+1))
        fi
    fi
    if [ "$fail" -eq 0 ]; then
        if detect_root_mode; then
            local ctx
            ctx=$(adb_raw shell 'id | grep -o "context=[^ ]*"' 2>/dev/null | tr -d '\r')
            green "  [OK]   root: 通道=$ADB_ROOT_MODE ${ctx:+($ctx)}"
            green "  [OK]   Android $(adb_ shell getprop ro.build.version.release 2>/dev/null | tr -d '\r') / $(adb_ shell getprop ro.product.model 2>/dev/null | tr -d '\r') / abi=$(adb_ shell getprop ro.product.cpu.abi 2>/dev/null | tr -d '\r')"
        else
            local uid ksu_hint=""
            uid=$(adb_raw shell id -u 2>&1 | tr -d '\r\n')
            if adb_raw shell pm list packages 2>/dev/null | tr -d '\r' | grep -q 'me.weishu.kernelsu'; then
                ksu_hint="（KernelSU 已安装，但 Shell/ADB 未获授权）"
            fi
            red "  [失败] root: id -u='$uid'，未取得 root $ksu_hint"
            red "         → 在 KernelSU/超级用户里给「Shell / ADB」授权后重试"
            fail=$((fail+1))
        fi
    fi
    if [ "$fail" -eq 0 ]; then
        # frida-server（设备端）
        if adb_ shell "[ -x '$FRIDA_DEV' ]" >/dev/null 2>&1; then
            local fsv
            fsv=$(adb_ shell "'$FRIDA_DEV' --version" 2>/dev/null | tr -d '\r\n')
            green "  [OK]   设备 frida-server: $FRIDA_DEV (--version=$fsv)"
            if frida_client_ok; then
                local cv
                cv=$(frida --version 2>/dev/null)
                if [ "$cv" = "$fsv" ]; then
                    green "         版本与客户端一致 ($cv)"
                else
                    yel "         注意：pip frida=$cv，设备 frida-server=$fsv，版本不一致会连不上"
                fi
            else
                yel "         注意：proot 内没有 frida-ps（pip install frida-tools）"
            fi
        else
            red "  [缺]   设备端 $FRIDA_DEV 不存在 → bash scripts/adb_device.sh frida start（会自动 push）"; fail=$((fail+1))
        fi
        if [ -x "$FRIDA_SRC" ]; then
            green "  [OK]   本机 frida-server 源文件: $FRIDA_SRC"
        else
            yel "  [可选缺] 本机 $FRIDA_SRC（需要时按 references/mobile-toolchain.md 下载）"
        fi
        # tcpdump（设备端）
        if adb_ shell "[ -x '$TD_BIN' ]" >/dev/null 2>&1; then
            local tv
            tv=$(adb_ shell "'$TD_BIN' --version 2>&1" 2>/dev/null | head -1 | tr -d '\r')
            green "  [OK]   设备 tcpdump: $TD_BIN (${tv:-version 未知})"
        else
            red "  [缺]   设备端 $TD_BIN 不存在（真机抓包需要它）"; fail=$((fail+1))
        fi
        if command -v tcpdump >/dev/null 2>&1; then
            green "  [OK]   proot 分析用 tcpdump: $(tcpdump --version 2>&1 | head -1)"
        else
            yel "  [可选缺] proot 内 tcpdump（仅用于解析 pcap）→ apt-get install -y tcpdump"
        fi
    fi
    echo
    if [ "$fail" -eq 0 ]; then
        green "结论: 真机 root 通道可用——frida/tcpdump 均可由 AI 直接驱动，无需用户手动 Termux。"
        return 0
    fi
    red "结论: $fail 项不满足，先按上面的「修法」处理。"
    return 1
}

# ── frida ─────────────────────────────────────────────────────────────────
frida_read_pid()  { dev_read_file "$FRIDA_PIDFILE"; }
frida_read_port() { dev_read_file "$FRIDA_PORTFILE"; }

cmd_frida() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        start)  cmd_frida_start "$@" ;;
        stop)   cmd_frida_stop ;;
        status) cmd_frida_status ;;
        *)      die "用法: adb_device.sh frida start [--port 27043] | stop | status" ;;
    esac
}

cmd_frida_start() {
    local port="$FRIDA_PORT_DEFAULT"
    while [ $# -gt 0 ]; do
        case "$1" in
            --port) shift; port="${1:-}"; [ -n "$port" ] || die "--port 需要一个值" ;;
            *) die "frida start 未知参数: $1" ;;
        esac
        shift
    done
    [ "$port" = "$RESERVED_FRIDA_PORT" ] && die "端口 $port 是 宿主自带 frida-server 实例专用，禁止使用；请用 27043 或其它端口"
    [[ "$port" =~ ^[0-9]+$ ]] || die "端口必须是数字: $port"

    ensure_root
    frida_client_ok || die "proot 内没有 frida-ps → pip install frida-tools -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com"

    # 已在跑？
    local oldpid oldport
    oldpid=$(frida_read_pid)
    oldport=$(frida_read_port)
    if [ -n "$oldpid" ] && dev_pid_alive "$oldpid"; then
        green "frida-server 已在运行（pid=$oldpid, port=${oldport:-?}）"
        if [ -n "$oldport" ] && [ "$oldport" != "$port" ]; then
            yel "注意：当前实例端口是 $oldport，与请求的 $port 不同；如需换端口先 stop。"
        fi
        timeout 12 frida-ps -H "127.0.0.1:${oldport:-$port}" 2>&1 | head -8
        return 0
    fi

    # 端口占用？
    if dev_port_listen "$port"; then
        die "端口 $port 已被占用（不是本脚本 pid 文件记录的实例）
→ 修法: 换 --port，或先确认占用者：adb -s $SERIAL shell netstat -tlnp | grep $port"
    fi

    # push（已存在则跳过）
    if adb_ shell "[ -x '$FRIDA_DEV' ]" >/dev/null 2>&1; then
        green "设备端已有 $FRIDA_DEV，跳过 push"
    else
        [ -x "$FRIDA_SRC" ] || die "找不到本机 $FRIDA_SRC
→ 修法: 按 references/mobile-toolchain.md 下载 frida-server 17.26.2 android-arm64（或先跑 toolcheck.sh 看版本）"
        say "推送 frida-server（$(du -h "$FRIDA_SRC" | cut -f1)）..."
        run_adb "adb push frida-server" push "$FRIDA_SRC" "$FRIDA_DEV" || exit 1
    fi
    run_adb "chmod 755 $FRIDA_DEV" shell "chmod 755 '$FRIDA_DEV'" >/dev/null || exit 1

    say "以 root 启动 frida-server：-l 127.0.0.1:$port"
    local out pid
    out=$(adb_ shell "nohup '$FRIDA_DEV' -l 127.0.0.1:$port >/data/local/tmp/frida-server-$port.log 2>&1 & echo \$!" 2>&1)
    pid=$(printf '%s' "$out" | tr -d '\r\n' | grep -Eo '[0-9]+' | head -1)
    [ -n "$pid" ] || die "启动命令没有返回 pid，原始输出: $out"
    adb_ shell "echo '$pid' > '$FRIDA_PIDFILE'; echo '$port' > '$FRIDA_PORTFILE'" >/dev/null 2>&1

    say "等待端口就绪（最多 ~15s）..."
    local ok=0 i
    for i in $(seq 1 15); do
        sleep 1
        if dev_pid_alive "$pid" && timeout 10 frida-ps -H "127.0.0.1:$port" >/tmp/.adbdev-fridaps.$$ 2>&1; then
            ok=1; break
        fi
    done

    if [ "$ok" -ne 1 ]; then
        red "启动后验证失败（frida-ps -H 127.0.0.1:$port 不通），原始输出："
        cat /tmp/.adbdev-fridaps.$$ 2>/dev/null
        rm -f /tmp/.adbdev-fridaps.$$
        red "设备端日志 /data/local/tmp/frida-server-$port.log："
        adb_ shell "cat /data/local/tmp/frida-server-$port.log 2>/dev/null | tail -20" 2>&1
        red "进程状态：$(adb_ shell "ps -A | grep frida-server" 2>&1 | tail -3)"
        return 1
    fi
    rm -f /tmp/.adbdev-fridaps.$$
    green "frida-server 已就绪：127.0.0.1:$port（pid=$pid，pid 文件 $FRIDA_PIDFILE）"
    say "frida-ps -H 127.0.0.1:$port 前几行："
    timeout 15 frida-ps -H "127.0.0.1:$port" 2>&1 | head -8
    say "停止: bash scripts/adb_device.sh frida stop"
    return 0
}

cmd_frida_stop() {
    ensure_device
    local pid port
    pid=$(frida_read_pid); port=$(frida_read_port)
    if [ -z "$pid" ]; then
        yel "没有 pid 文件 $FRIDA_PIDFILE（不是本脚本启动的实例？）"
        yel "为免误杀 27042 / 宿主自带实例，不做自动停止。手动停:"
        say "  adb -s $SERIAL shell pkill -f 'frida-server -l 127.0.0.1:<你的端口>'"
        return 1
    fi
    dev_pid_alive "$pid" || {
        yel "pid $pid 已不在运行，清理 pid 文件"
        adb_ shell "rm -f '$FRIDA_PIDFILE' '$FRIDA_PORTFILE'" >/dev/null 2>&1
        return 0
    }
    local cmdline
    cmdline=$(adb_ shell "tr '\\0' ' ' < /proc/$pid/cmdline 2>/dev/null" 2>&1 | tr -d '\r')
    case "$cmdline" in
        *frida-server*"-l 127.0.0.1:$port"*) ;;
        *)
            red "拒绝 kill pid=$pid：其 cmdline 不是本脚本启动的实例"
            say "  实际 cmdline: $cmdline"
            return 1 ;;
    esac
    if adb_ shell "kill '$pid'" 2>&1 | grep -qi 'denied'; then
        die "kill $pid 被拒绝（原始输出见上）"
    fi
    sleep 1
    if dev_pid_alive "$pid"; then
        red "进程 $pid 仍在运行，未强杀（避免影响其它实例）"
        return 1
    fi
    adb_ shell "rm -f '$FRIDA_PIDFILE' '$FRIDA_PORTFILE'" >/dev/null 2>&1
    green "已停止本脚本启动的 frida-server（pid=$pid，端口 ${port:-?}）"
    if adb_ shell "netstat -tlnp 2>/dev/null | grep -q ':$RESERVED_FRIDA_PORT '" 2>/dev/null; then
        green "27042（宿主自带实例）未受影响，仍在运行"
    fi
    return 0
}

cmd_frida_status() {
    ensure_device
    local pid port
    pid=$(frida_read_pid); port=$(frida_read_port)
    say "pid 文件: ${FRIDA_PIDFILE} = ${pid:-<无>}"
    say "端口记录: ${FRIDA_PORTFILE} = ${port:-<无>}"
    if [ -n "$pid" ] && dev_pid_alive "$pid"; then
        green "进程存活: pid=$pid"
    else
        yel "进程未运行（或 pid 文件过期）"
    fi
    say "设备 27042/27043 监听情况:"
    adb_ shell "netstat -tlnp 2>/dev/null | grep -E ':(27042|27043) '" 2>&1 | sed 's/^/  /'
    if [ -n "$port" ] && frida_client_ok; then
        if timeout 12 frida-ps -H "127.0.0.1:$port" >/tmp/.adbdev-fridaps.$$ 2>&1; then
            green "frida-ps -H 127.0.0.1:$port 连通，前几行："
            head -8 /tmp/.adbdev-fridaps.$$
            rm -f /tmp/.adbdev-fridaps.$$
            return 0
        fi
        red "frida-ps -H 127.0.0.1:${port} 不通，原始输出：$(head -3 /tmp/.adbdev-fridaps.$$ 2>/dev/null)"
        rm -f /tmp/.adbdev-fridaps.$$
        return 1
    fi
    red "未记录端口或 proot 内缺 frida-ps，无法验证连通性"
    return 1
}

# ── tcpdump ───────────────────────────────────────────────────────────────
cmd_tcpdump() {
    local sub="${1:-}"; shift || true
    case "$sub" in
        start)  cmd_tcpdump_start "$@" ;;
        stop)   cmd_tcpdump_stop ;;
        pull)   cmd_tcpdump_pull "$@" ;;
        *)      die "用法: adb_device.sh tcpdump start [-i any] [--out PATH] | stop | pull <本地路径>" ;;
    esac
}

cmd_tcpdump_start() {
    local iface="any" out="$TD_OUT_DEFAULT"
    while [ $# -gt 0 ]; do
        case "$1" in
            -i)       shift; iface="${1:-}"; [ -n "$iface" ] || die "-i 需要一个网卡名（any/lo/wlan0）" ;;
            --out)    shift; out="${1:-}"; [ -n "$out" ] || die "--out 需要一个设备端路径" ;;
            *) die "tcpdump start 未知参数: $1" ;;
        esac
        shift
    done
    ensure_root
    adb_ shell "[ -x '$TD_BIN' ]" >/dev/null 2>&1 \
        || die "设备端没有 $TD_BIN → 真机抓包依赖系统自带 tcpdump，先确认机型/系统"

    local oldpid
    oldpid=$(dev_read_file "$TD_PIDFILE")
    if [ -n "$oldpid" ] && dev_pid_alive "$oldpid"; then
        die "已有本脚本的抓包进程在跑（pid=$oldpid, out=$(dev_read_file "$TD_OUTFILE")），先 tcpdump stop"
    fi

    say "开始抓包: $TD_BIN -i $iface -w $out"
    local pid
    pid=$(adb_ shell "rm -f '$out'; nohup '$TD_BIN' -i '$iface' -w '$out' > '$TD_LOG' 2>&1 & echo \$!" 2>&1 \
          | tr -d '\r\n' | grep -Eo '[0-9]+' | head -1)
    [ -n "$pid" ] || die "tcpdump 启动命令没有返回 pid"
    adb_ shell "echo '$pid' > '$TD_PIDFILE'; echo '$out' > '$TD_OUTFILE'; echo '$iface' > '$TD_IFACEFILE'" >/dev/null 2>&1
    sleep 1
    if ! dev_pid_alive "$pid"; then
        red "tcpdump 启动后立即退出，日志："
        adb_ shell "cat '$TD_LOG' 2>/dev/null | tail -20" 2>&1
        die "抓包失败"
    fi
    green "抓包中（pid=$pid）: -i $iface -w $out"
    say "设备日志: $(adb_ shell "head -3 '$TD_LOG' 2>/dev/null" 2>/dev/null | tr -d '\r' | tr '\n' ' ')"
    say "停止: bash scripts/adb_device.sh tcpdump stop"
    say "拉回: bash scripts/adb_device.sh tcpdump pull /tmp/cap.pcap"
    return 0
}

# 安全兜底：只 kill“cmdline 含本脚本输出路径”的 tcpdump 进程，避免误伤其它 tcpdump。
# 用 ps 的 comm 列筛 tcpdump（不匹配发命令的 shell 自己），再核对 /proc/<pid>/cmdline。
kill_tcpdump_by_out() {             # kill_tcpdump_by_out <out> [skip_pid]
    local out="$1" skip="${2:-}" pids p c
    pids=$(adb_ shell "ps -A 2>/dev/null | awk '\$2 ~ /tcpdump/ {print \$1}'" 2>/dev/null | tr -d '\r')
    for p in $pids; do
        [ -n "$skip" ] && [ "$p" = "$skip" ] && continue
        c=$(adb_ shell "tr '\\0' ' ' < /proc/$p/cmdline 2>/dev/null" 2>/dev/null | tr -d '\r')
        case "$c" in
            *"$out"*) adb_ shell "kill '$p'" >/dev/null 2>&1; yel "已按输出路径清理残留 tcpdump: pid=$p" ;;
        esac
    done
}

cmd_tcpdump_stop() {
    ensure_device
    local pid out
    pid=$(dev_read_file "$TD_PIDFILE"); out=$(dev_read_file "$TD_OUTFILE")
    out="${out:-$TD_OUT_DEFAULT}"
    if [ -z "$pid" ] || ! dev_pid_alive "$pid"; then
        yel "没有存活的 pid 记录（$TD_PIDFILE=${pid:-<无>}）"
        kill_tcpdump_by_out "$out"
        adb_ shell "rm -f '$TD_PIDFILE' '$TD_IFACEFILE'" >/dev/null 2>&1
        yel "已清理（pcap 路径记录保留在 $TD_OUTFILE，便于 tcpdump pull）"
        return 0
    fi
    local cmdline
    cmdline=$(adb_ shell "tr '\\0' ' ' < /proc/$pid/cmdline 2>/dev/null" 2>&1 | tr -d '\r')
    case "$cmdline" in
        *"$TD_BIN"*"$out"*) ;;
        *)
            red "拒绝 kill pid=$pid：cmdline 不含 $TD_BIN + $out"
            say "  实际 cmdline: $cmdline"
            return 1 ;;
    esac
    adb_ shell "kill '$pid'" >/dev/null 2>&1
    sleep 1
    if dev_pid_alive "$pid"; then
        red "进程 $pid 仍在运行（未强杀）"
        return 1
    fi
    kill_tcpdump_by_out "$out" "$pid"
    adb_ shell "rm -f '$TD_PIDFILE' '$TD_IFACEFILE'" >/dev/null 2>&1
    local size
    size=$(adb_ shell "ls -l '$out' 2>/dev/null | awk '{print \$5}'" 2>/dev/null | tr -d '\r\n')
    green "已停止抓包（pid=$pid），pcap: $out（${size:-?} 字节）"
    say "拉回: bash scripts/adb_device.sh tcpdump pull <本地路径>"
    return 0
}

cmd_tcpdump_pull() {
    local local_path="${1:-}"
    [ -n "$local_path" ] || die "用法: adb_device.sh tcpdump pull <本地路径>，例如 /tmp/cap.pcap"
    ensure_device
    local remote
    remote=$(dev_read_file "$TD_OUTFILE")
    remote="${remote:-$TD_OUT_DEFAULT}"
    adb_ shell "[ -s '$remote' ]" >/dev/null 2>&1 \
        || die "设备端 $remote 不存在或为空（先 tcpdump start 抓包再 stop）"
    run_adb "adb pull $remote" pull "$remote" "$local_path" || exit 1
    [ -s "$local_path" ] || die "拉回后本地文件为空: $local_path"
    green "已拉回: $local_path（$(du -h "$local_path" | cut -f1)）"
    if command -v tcpdump >/dev/null 2>&1; then
        say "本地 tcpdump 解析前几包:"
        tcpdump -r "$local_path" -nn 2>&1 | head -8
    else
        yel "本地没有 tcpdump，跳过解析（apt-get install -y tcpdump）"
    fi
    return 0
}

# ── logcat ────────────────────────────────────────────────────────────────
cmd_logcat() {
    local lines=300 re='AndroidRuntime|FATAL|Exception|ANR|am_crash|backtrace|signal [0-9]|crash'
    local clear=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --lines) shift; lines="${1:-300}" ;;
            --grep)  shift; re="${1:-}" ;;
            --clear) clear=1 ;;
            *) die "logcat 未知参数: $1" ;;
        esac
        shift
    done
    ensure_device
    if [ "$clear" -eq 1 ]; then
        run_adb "adb logcat -c（清空缓冲）" logcat -c || exit 1
        green "logcat 缓冲已清空（现在复现问题，再跑一次不带 --clear）"
    fi
    local out rc
    out=$(adb_ shell "logcat -d -t $lines" 2>&1); rc=$?
    if [ "$rc" -ne 0 ]; then
        red "✗ 读取 logcat 失败 (rc=$rc)，原始输出："
        printf '%s\n' "$out"
        return 1
    fi
    if [ -n "$re" ]; then
        local hit
        hit=$(printf '%s\n' "$out" | grep -E -- "$re" | tail -n "$lines")
        if [ -n "$hit" ]; then
            cyan_head "匹配 '$re' 的最近日志（最多 $lines 行）："
            printf '%s\n' "$hit"
        else
            yel "最近 $lines 行里没有匹配 '$re' 的日志"
            say "→ 复现问题后再跑；要看全部用 --grep ''"
        fi
    else
        printf '%s\n' "$out" | tail -n "$lines"
    fi
    return 0
}
cyan_head() { printf '\033[36m%s\033[0m\n' "$*"; }

# ── 安装 / 卸载 / 清理 / 启停 / 信息 ─────────────────────────────────────
# 系统包黑名单（前缀）
is_system_pkg() {
    case "$1" in
        android|com.android|com.android.*|com.google.android.*|com.google.*|com.oplus.*|com.oppo.*|com.coloros.*|com.heytap.*|com.oneplus.*|com.realme.*|com.miui.*|com.samsung.android.*|com.sec.android.*|com.huawei.*|com.hihonor.*|com.vivo.*|com.bbk.*|com.qti.*|com.qualcomm.*|com.mediatek.*|org.codeaurora.*|com.android.cts.*|com.transsion.*|com.innopeast.*)
            return 0 ;;
        *) return 1 ;;
    esac
}

# 分区在系统分区的应用也拒绝
pkg_is_system_by_path() {
    local pkg="$1" path
    path=$(adb_ shell "pm path '$pkg' 2>/dev/null" 2>/dev/null | head -1 | tr -d '\r')
    case "$path" in
        /system/*|/product/*|/vendor/*|/system_ext/*|/odm/*|/apex/*) return 0 ;;
        *) return 1 ;;
    esac
}

cmd_install() {
    local apk="" dry=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --dry-run) dry=1 ;;
            -*) die "install 未知参数: $1" ;;
            *) [ -z "$apk" ] || die "install 只能接一个 apk"; apk="$1" ;;
        esac
        shift
    done
    [ -n "$apk" ] || die "用法: adb_device.sh install <apk> [--dry-run]"
    [ -f "$apk" ] || die "找不到 APK: $apk"
    ensure_device
    if [ "$dry" -eq 1 ]; then
        say "[dry-run] 将执行: adb -s $SERIAL install -r -d $apk"
        return 0
    fi
    local out rc
    out=$(adb_ install -r -d "$apk" 2>&1); rc=$?
    printf '%s\n' "$out"
    if [ "$rc" -ne 0 ] || ! printf '%s' "$out" | grep -q '^Success'; then
        red "✗ 安装失败 (rc=$rc)（上方为 adb 原始输出）"
        return 1
    fi
    green "安装成功: $apk"
    return 0
}

cmd_uninstall_or_clear() {
    local action="$1"; shift
    local pkg="" yes=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --yes|-y) yes=1 ;;
            -*) die "$action 未知参数: $1" ;;
            *) [ -z "$pkg" ] || die "$action 只能接一个包名"; pkg="$1" ;;
        esac
        shift
    done
    [ -n "$pkg" ] || die "用法: adb_device.sh $action <包名> --yes"
    [ "$yes" -eq 1 ] || die "危险操作必须显式加 --yes：$action $pkg"
    ensure_device
    if is_system_pkg "$pkg"; then
        die "拒绝：$pkg 命中系统/厂商包黑名单，禁止 $action"
    fi
    if pkg_is_system_by_path "$pkg"; then
        die "拒绝：$pkg 位于系统分区（$(adb_ shell "pm path '$pkg'" 2>/dev/null | head -1 | tr -d '\r')），禁止 $action"
    fi
    local out rc
    if [ "$action" = "uninstall" ]; then
        out=$(adb_ shell "pm uninstall '$pkg'" 2>&1); rc=$?
    else
        out=$(adb_ shell "pm clear '$pkg'" 2>&1); rc=$?
    fi
    printf '%s\n' "$out"
    if [ "$rc" -ne 0 ] || ! printf '%s' "$out" | grep -q 'Success'; then
        red "✗ $action $pkg 失败 (rc=$rc)（上方为 adb 原始输出）"
        return 1
    fi
    green "$action 成功: $pkg"
    return 0
}

cmd_start() {
    local pkg="${1:-}"
    [ -n "$pkg" ] || die "用法: adb_device.sh start <包名>"
    ensure_device
    local line
    line=$(adb_ shell "cmd package resolve-activity --brief '$pkg' 2>/dev/null | tail -n 1" 2>&1 | tr -d '\r')
    if printf '%s' "$line" | grep -q '/'; then
        say "启动: am start -n $line"
        run_adb "am start" shell "am start -n '$line'" || return 1
    else
        yel "resolve-activity 未拿到，退回 monkey 启动"
        run_adb "monkey 启动" shell "monkey -p '$pkg' -c android.intent.category.LAUNCHER 1" || return 1
    fi
    green "已请求启动: $pkg"
    return 0
}

cmd_force_stop() {
    local pkg="${1:-}"
    [ -n "$pkg" ] || die "用法: adb_device.sh stop <包名>"
    ensure_device
    run_adb "am force-stop $pkg" shell "am force-stop '$pkg'" >/dev/null || return 1
    green "已强制停止: $pkg"
    return 0
}

cmd_info() {
    local pkg="${1:-}"
    [ -n "$pkg" ] || die "用法: adb_device.sh info <包名>"
    ensure_device
    say "── pm path $pkg"
    adb_ shell "pm path '$pkg'" 2>&1 | sed 's/^/  /'
    say "── dumpsys package $pkg（关键字段）"
    adb_ shell "dumpsys package '$pkg' 2>/dev/null | grep -E 'versionName=|versionCode=|firstInstallTime=|lastUpdateTime=|installerPackageName=|pkgFlags=' | head -12" 2>&1 | sed 's/^/  /'
    return 0
}

# ── screencap / push / pull ──────────────────────────────────────────────
cmd_screencap() {
    local local_png="${1:-}"
    [ -n "$local_png" ] || die "用法: adb_device.sh screencap <本地.png>"
    ensure_device
    local remote="/data/local/tmp/shot-$$-$(date +%s).png"
    run_adb "设备端截图" shell "screencap -p '$remote'" >/dev/null || exit 1
    adb_ shell "[ -s '$remote' ]" >/dev/null 2>&1 || die "设备端截图文件为空: $remote"
    run_adb "adb pull 截图" pull "$remote" "$local_png" || { adb_ shell "rm -f '$remote'" >/dev/null 2>&1; exit 1; }
    adb_ shell "rm -f '$remote'" >/dev/null 2>&1
    [ -s "$local_png" ] || die "截图拉回后为空: $local_png"
    green "截图已保存: $local_png（$(du -h "$local_png" | cut -f1)）"
    return 0
}

cmd_push() {
    local src="${1:-}" dst="${2:-}"
    [ -n "$src" ] && [ -n "$dst" ] || die "用法: adb_device.sh push <本地文件> <设备端路径>"
    [ -e "$src" ] || die "本地不存在: $src"
    ensure_device
    run_adb "adb push" push "$src" "$dst" || return 1
    green "已推送: $src → $dst"
    return 0
}

cmd_pull() {
    local src="${1:-}" dst="${2:-}"
    [ -n "$src" ] && [ -n "$dst" ] || die "用法: adb_device.sh pull <设备端路径> <本地路径>"
    ensure_device
    run_adb "adb pull" pull "$src" "$dst" || return 1
    [ -e "$dst" ] || die "拉取后本地不存在: $dst"
    green "已拉取: $src → $dst"
    return 0
}

# ── 分发 ─────────────────────────────────────────────────────────────────
case "$CMD" in
    check)      cmd_check ;;
    frida)      cmd_frida "$@" ;;
    tcpdump)    cmd_tcpdump "$@" ;;
    logcat)     cmd_logcat "$@" ;;
    install)    cmd_install "$@" ;;
    uninstall)  cmd_uninstall_or_clear uninstall "$@" ;;
    clear)      cmd_uninstall_or_clear clear "$@" ;;
    start)      cmd_start "$@" ;;
    stop)       cmd_force_stop "$@" ;;
    info)       cmd_info "$@" ;;
    screencap)  cmd_screencap "$@" ;;
    push)       cmd_push "$@" ;;
    pull)       cmd_pull "$@" ;;
    -h|--help|help) usage; exit 0 ;;
    *)  red "未知子命令: $CMD"; usage; exit 2 ;;
esac
