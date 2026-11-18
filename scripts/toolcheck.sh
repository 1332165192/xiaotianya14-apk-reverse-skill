#!/usr/bin/env bash
# 工具自检：新会话开工前跑一次，确认逆向工具链齐不齐。
# 用法: bash scripts/toolcheck.sh
# 退出码: 0 = 必需工具齐；1 = 缺必需工具（按提示补装）
set -u

HERE_DIR=$(cd "$(dirname "$0")" && pwd)
[ -f "$HERE_DIR/adb_common.sh" ] && . "$HERE_DIR/adb_common.sh"

ok=0; miss=0; warn=0
green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
yel()   { printf '\033[33m%s\033[0m\n' "$*"; }

need() {                # need <说明> <命令> [版本参数...]
    local desc="$1" cmd="$2"; shift 2
    if command -v "$cmd" >/dev/null 2>&1; then
        local v
        v=$("$cmd" "$@" 2>&1 | head -1)
        green "  [OK]   $desc: $v"
        ok=$((ok+1))
    else
        red "  [缺]   $desc ($cmd)"; miss=$((miss+1))
    fi
}

need_opt() {
    local desc="$1" cmd="$2"; shift 2
    if command -v "$cmd" >/dev/null 2>&1; then
        local v
        v=$("$cmd" "$@" 2>&1 | head -1)
        green "  [OK]   $desc: $v"
        ok=$((ok+1))
    else
        yel "  [可选缺] $desc ($cmd)"; warn=$((warn+1))
    fi
}

pymod() {               # pymod <模块> <显示名>
    if python3 -c "import $1" >/dev/null 2>&1; then
        green "  [OK]   python: $2"
        ok=$((ok+1))
    else
        red "  [缺]   python: $2  →  pip install $3 -i https://pypi.org/simple"
        miss=$((miss+1))
    fi
}

echo "══════ APK 逆向工具链自检 ══════"
echo "环境: $(uname -m) / $(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-?}") / python $(python3 -V 2>&1 | awk '{print $2}')"
echo

echo "[解码/打包]"
need "java"        java -version
need "apktool"     apktool --version
need "jadx"        jadx --version
need "aapt"        aapt version
need "aapt2"       aapt2 version
need "apksigner"   apksigner --version
need "zipalign"    zipalign
need "smali"       smali --version
need "baksmali"    baksmali --version
echo

echo "[Python 库]"
pymod androguard      androguard        androguard
pymod frida           "frida (Python 端)" frida
pymod lief            lief              lief
pymod blackboxprotobuf blackboxprotobuf blackboxprotobuf
echo

echo "[动态/分析/存档]"
need "frida 客户端"   frida --version
need "frida-ps"       frida-ps --version
need "sqlite3"        sqlite3 --version
need "radare2"        r2 -v
need "strings"        strings --version
need_opt "xxd(十六进制)" xxd -v
need_opt "jq(JSON)"    jq --version
need "xz"             xz --version
need "unzip"          unzip -v
need "zip"            zip -v
echo

echo "[frida-server（设备端；可用 adb root 自动启动）]"
fs_ver="17.26.2"
fs="/root/tools/frida-server-${fs_ver}-android-arm64"
if [ -f "$fs" ]; then
    green "  [OK]   $fs ($(du -h "$fs" | cut -f1))"
    python3 -c "import frida,sys; v=frida.__version__; sys.exit(0 if v=='$fs_ver' else 1)" 2>/dev/null \
        && green "         版本与 pip frida 一致 ($fs_ver)" \
        || yel "         注意：pip frida 版本与 frida-server $fs_ver 不一致，连接会失败"
else
    yel "  [可选缺] $fs（需要时按 protection-map.md §七 下载同版本）"
    warn=$((warn+1))
fi
echo

# 真机 adb root 通道：全部为可选增强，缺失只黄色提示，不影响退出码。
echo "[真机 adb root 通道（可选：AI 可直接驱动 frida/tcpdump）]"
ADB_SERIAL="${ADB_SERIAL:-}"
if ! command -v adb >/dev/null 2>&1; then
    yel "  [可选缺] adb（apt-get install -y android-tools-adb）→ adb_device.sh 一键通道不可用"
    warn=$((warn+1))
else
    green "  [OK]   adb: $(adb version 2>&1 | head -1)"
    ok=$((ok+1))
    # 自动发现：ADB_SERIAL > 5555（旧 tcpip 端口，在线才用）> adb devices 首个真机（跳过 emulator-*）
    [ -n "$ADB_SERIAL" ] || ADB_SERIAL=$(adb_resolve_serial adb 2>/dev/null || true)
    if [ -z "$ADB_SERIAL" ]; then
        yel "  [可选缺] 没有在线的真机 adb 设备（无线调试端口随机：看无线调试页或 adb devices）"
        warn=$((warn+1))
    else
    adb_uid=$(adb -s "$ADB_SERIAL" shell id -u 2>/dev/null | tr -d '\r\n')
    if [ "$adb_uid" = "0" ]; then
        adb_ctx=$(adb -s "$ADB_SERIAL" shell 'id | grep -o "context=[^ ]*"' 2>/dev/null | tr -d '\r')
        green "  [OK]   真机 root 通道: $ADB_SERIAL (id -u=0${adb_ctx:+, $adb_ctx})"
        ok=$((ok+1))
        if adb -s "$ADB_SERIAL" shell "[ -x /data/local/tmp/frida-server ]" >/dev/null 2>&1; then
            adb_fsv=$(adb -s "$ADB_SERIAL" shell '/data/local/tmp/frida-server --version' 2>/dev/null | tr -d '\r' | head -1)
            green "  [OK]   真机 frida-server: /data/local/tmp/frida-server (${adb_fsv:-version ?})"
            ok=$((ok+1))
        else
            yel "  [可选缺] 真机 frida-server → bash scripts/adb_device.sh frida start"
            warn=$((warn+1))
        fi
        if adb -s "$ADB_SERIAL" shell "[ -x /system/bin/tcpdump ]" >/dev/null 2>&1; then
            adb_tdv=$(adb -s "$ADB_SERIAL" shell '/system/bin/tcpdump --version 2>&1' 2>/dev/null | tr -d '\r' | head -1)
            green "  [OK]   真机 tcpdump: /system/bin/tcpdump (${adb_tdv:-version ?})"
            ok=$((ok+1))
        else
            yel "  [可选缺] 真机 tcpdump (/system/bin/tcpdump)"
            warn=$((warn+1))
        fi
    else
        yel "  [可选缺] 真机 root 通道 $ADB_SERIAL 不可用（id -u='${adb_uid:-?}'）→ 看无线调试页端口 / adb devices / adb root"
        warn=$((warn+1))
    fi
    fi
fi
echo

echo "[其它]"
[ -f /root/mod.ks ] && green "  [OK]   签名用 keystore: /root/mod.ks" || yel "  [可选缺] keystore /root/mod.ks（首次 build_sign.sh 会自动生成）"
echo

# 可选增强工具：缺了只记"可选缺失"（黄色），不影响退出码。
echo "[可选工具：深度逆向 / 抓包]"
need_opt "protoc(protobuf)"  protoc --version
need_opt "yara"               yara --version
need_opt "tcpdump"            tcpdump --version
need_opt "ngrep"              ngrep -V
if command -v apk-mitm >/dev/null 2>&1; then
    v=$(npm list -g apk-mitm --depth=0 --json 2>/dev/null | grep -o '"version": *"[^"]*"' | head -1 | grep -o '[0-9][^"]*')
    green "  [OK]   apk-mitm: ${v:-已安装（$(command -v apk-mitm)）}"
    ok=$((ok+1))
else
    yel "  [可选缺] apk-mitm (npm install -g apk-mitm)  →  bash scripts/install_tools.sh --re"
    warn=$((warn+1))
fi
need_opt "apkid"              apkid -v
if command -v binwalk >/dev/null 2>&1 && binwalk --help >/dev/null 2>&1; then
    green "  [OK]   binwalk: $(binwalk --help 2>&1 | grep -v '^[[:space:]]*$' | head -1)"
    ok=$((ok+1))
elif [ -x /usr/bin/binwalk ] && /usr/bin/binwalk --help >/dev/null 2>&1; then
    green "  [OK]   binwalk: $(/usr/bin/binwalk --help 2>&1 | grep -v '^[[:space:]]*$' | head -1)  (/usr/bin/binwalk)"
    ok=$((ok+1))
else
    yel "  [可选缺] binwalk（不可运行；apt-get install -y binwalk 后重跑 --re）"
    warn=$((warn+1))
fi
need_opt "hermes-dec"         hbc-decompiler -V
need_opt "objection"          objection version
need_opt "mitmproxy"          mitmproxy --version
if [ -f /root/tools/jars/cfr.jar ] && java -jar /root/tools/jars/cfr.jar --version >/dev/null 2>&1; then
    green "  [OK]   cfr.jar: $(java -jar /root/tools/jars/cfr.jar --version 2>&1 | head -1)  (/root/tools/jars/cfr.jar)"
    ok=$((ok+1))
else
    yel "  [可选缺] cfr.jar (/root/tools/jars/cfr.jar)  →  bash scripts/install_tools.sh --re"
    warn=$((warn+1))
fi
if command -v smali3 >/dev/null 2>&1 && command -v baksmali3 >/dev/null 2>&1; then
    green "  [OK]   smali3/baksmali3: $(smali3 --version 2>&1 | head -1) / $(baksmali3 --version 2>&1 | head -1)"
    ok=$((ok+1))
else
    yel "  [可选缺] smali3/baksmali3 (3.0.9 fat jar 包装)  →  bash scripts/install_tools.sh --re"
    warn=$((warn+1))
fi
echo

echo "[可选工具：社区按需（install_tools.sh --community）]"
if [ -s /root/tools/jars/vineflower.jar ]; then
    green "  [OK]   Vineflower: $(java -jar /root/tools/jars/vineflower.jar --help 2>&1 | head -1)"
    ok=$((ok+1))
else
    yel "  [可选缺] Vineflower（install_tools.sh --community）"; warn=$((warn+1))
fi
if [ -x /root/tools/dex2jar/d2j-dex2jar.sh ]; then
    green "  [OK]   dex2jar: /root/tools/dex2jar/d2j-dex2jar.sh"; ok=$((ok+1))
else
    yel "  [可选缺] dex2jar（install_tools.sh --community）"; warn=$((warn+1))
fi
if [ -s /root/tools/jars/bundletool.jar ]; then
    green "  [OK]   bundletool: $(java -jar /root/tools/jars/bundletool.jar version 2>&1 | head -1)"; ok=$((ok+1))
else
    yel "  [可选缺] bundletool（install_tools.sh --community）"; warn=$((warn+1))
fi
need_opt "unicorn" python3 -c "import unicorn,capstone;print('unicorn',unicorn.__version__,'capstone',capstone.__version__)"

echo "══════ 结果: OK=$ok  缺失=$miss  可选缺失=$warn ══════"
if [ "$miss" -gt 0 ]; then
    red "缺少必需工具：先跑 bash scripts/install_tools.sh（自动下载/安装，装完自检），"
    red "或按 references/mobile-toolchain.md 的链接手动装。"
    exit 1
fi
green "工具链可用。"

echo
# 按需工具清单（不下载）：交给 tool_manager，默认 thirdparty + minimal。
echo "[按需工具清单 / 不下载]"
python3 "$HERE_DIR/tool_manager.py" plan --task "${TOOL_TASK:-decode}" 2>/dev/null || true
