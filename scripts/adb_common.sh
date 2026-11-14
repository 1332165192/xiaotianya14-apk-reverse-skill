#!/usr/bin/env bash
# adb 共享小工具：自动发现在线设备（无线调试端口每次可能变，靠扫描本机监听端口 + connect 找回来）。
# 被 device_adb_guard.sh / device_ui.sh / device_input.sh / adb_device.sh / toolcheck.sh source。
# 用法: . adb_common.sh; s=$(adb_resolve_serial adb 127.0.0.1:5555)

ADB_SERIAL_CACHE="${ADB_SERIAL_CACHE:-/tmp/.dsh_adb_serial}"
ADB_SERIAL_CACHE_TTL="${ADB_SERIAL_CACHE_TTL:-600}"

# 已知不是 adb 的本机服务端口（宿主 web/inspector/内部端口等）
ADB_SKIP_PORTS="3080 5037 8326 9230 10150 10152 10156 10157 10162 12121 64660 46888"

_adb_list_online() {  # _adb_list_online <adb>
    "$1" devices 2>/dev/null | awk 'NR>1 && $2=="device" && $1 !~ /^emulator-/ {print $1}'
}

_adb_try_connect_port() {  # _adb_try_connect_port <adb> <port> → 成功打印 serial
    local adb="$1" p="$2" s
    timeout 3 "$adb" connect "127.0.0.1:$p" >/dev/null 2>&1 || true
    s=$("$adb" devices 2>/dev/null | awk -v want="127.0.0.1:$p" '$1==want && $2=="device" {print $1; exit}')
    [ -n "$s" ] && { printf '%s' "$s"; return 0; }
    return 1
}

# 扫描本机监听的 TCP 端口，逐个 adb connect，找到第一个可用设备
_adb_scan_connect() {  # _adb_scan_connect <adb>
    local adb="$1" ports p s
    ports=$(python3 - "$ADB_SKIP_PORTS" <<'PY' 2>/dev/null
import sys
skip=set(int(x) for x in sys.argv[1].split())
seen=set()
for f in ('/proc/net/tcp','/proc/net/tcp6'):
    try: lines=open(f).read().splitlines()[1:]
    except OSError: continue
    for l in lines:
        p=l.split()
        if len(p)>3 and p[3]=='0A':          # LISTEN
            port=int(p[1].split(':')[1],16)
            if port>1024 and port not in skip: seen.add(port)
print(' '.join(str(x) for x in sorted(seen)))
PY
)
    for p in $ports; do
        s=$(_adb_try_connect_port "$adb" "$p") && { printf '%s' "$s"; return 0; }
    done
    return 1
}

# adb_resolve_serial <adb> [候选默认 serial]
# 顺序：ADB_SERIAL 环境变量 → 已在线设备 → 缓存（未过期且仍在线）→ 候选(5555) → 扫描监听端口 reconnect
adb_resolve_serial() {
    local adb="${1:-adb}" fallback="${2:-127.0.0.1:5555}" s
    [ -n "${ADB_SERIAL:-}" ] && { printf '%s' "$ADB_SERIAL"; return 0; }
    s=$(_adb_list_online "$adb" | head -1)
    [ -n "$s" ] && { printf '%s' "$s"; return 0; }
    if [ -s "$ADB_SERIAL_CACHE" ]; then
        s=$(cat "$ADB_SERIAL_CACHE" 2>/dev/null)
        if [ -n "$s" ] && "$adb" -s "$s" get-state 2>/dev/null | grep -q device; then
            printf '%s' "$s"; return 0
        fi
    fi
    if "$adb" -s "$fallback" get-state 2>/dev/null | grep -q device; then
        printf '%s' "$fallback"; printf '%s' "$fallback" > "$ADB_SERIAL_CACHE"; return 0
    fi
    s=$(_adb_scan_connect "$adb")
    if [ -n "$s" ]; then
        printf '%s' "$s" > "$ADB_SERIAL_CACHE"
        printf '%s' "$s"; return 0
    fi
    return 1
}
