#!/usr/bin/env bash
# 工具自动安装器：缺什么装什么（本地缓存优先 → 镜像/官方源下载）。不需要人盯着。
#
# 用法:
#   bash scripts/install_tools.sh            # 补齐必需工具 + 深度逆向（apt + pip + frida-server + jadx + re）
#   bash scripts/install_tools.sh --check    # 只检查缺什么，给出下载链接，不动手
#   bash scripts/install_tools.sh --apt      # 只补 apt 类系统工具
#   bash scripts/install_tools.sh --pip      # 只补 pip 类 Python 工具
#   bash scripts/install_tools.sh --frida    # 只补 frida-server
#   bash scripts/install_tools.sh --jadx     # 只补 jadx
#   bash scripts/install_tools.sh --re       # 深度逆向：apkid/binwalk/hermes-dec/objection + apk-mitm +
#                                            # CFR 0.152 + smali/baksmali 3.0.9（jar + smali3/baksmali3 包装）
#   bash scripts/install_tools.sh --net      # 抓包编译链 + mitmproxy（体积大、耗时长，单独跑）
#   bash scripts/install_tools.sh --community # 社区工具按需装：Vineflower + dex2jar + bundletool + unicorn/capstone
#                                            # （用到才装；不要一次全装，体积约 60MB）
#
# --all = 必需项 + --re；默认不含 --net / --community（按需显式跑）。
#
# 下载源（可被环境变量覆盖）:
#   PIP_INDEX   默认 https://mirrors.aliyun.com/pypi/simple（实测能下 frida 的 aarch64 wheel；
#               清华镜像对 frida wheel 返回 403，失败时自动退回 https://pypi.org/simple）
#   NPM_REGISTRY 默认 https://registry.npmmirror.com（apk-mitm 走国内 npm 镜像）
#   GH_PROXY    默认 https://gh-proxy.com/（GitHub 直连常超时）
#   TOOLCACHE   默认 /root/tools/toolcache（有离线包先用，没有再下载）
#
# 环境限定：aarch64 · proot Ubuntu 24.04 · Python 3.12（本 skill 的目标手机环境）。
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
PIP_INDEX="${PIP_INDEX:-https://mirrors.aliyun.com/pypi/simple}"
PIP_HOST="${PIP_INDEX#https://}"; PIP_HOST="${PIP_HOST%%/*}"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"
GH_PROXY="${GH_PROXY:-https://gh-proxy.com/}"
TOOLCACHE="${TOOLCACHE:-/root/tools/toolcache}"
TOOLS="/root/tools"
JARS="$TOOLS/jars"
JADX_VER="1.5.1"
FRIDA_VER_DEFAULT="17.26.2"
CFR_VER="0.152"
SMALI_VER="3.0.9"

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
yel()   { printf '\033[33m%s\033[0m\n' "$*"; }
has()   { command -v "$1" >/dev/null 2>&1; }

# ── 安全清理（不执行 rm -rf 绝对路径；先移入临时回收站，退出时再删）──────
TRASH_LIST=()
cleanup_trash() {
    local t
    for t in "${TRASH_LIST[@]:-}"; do
        [ -n "$t" ] || continue
        [ -d "$t" ] && find "$t" -mindepth 1 -delete 2>/dev/null
        rmdir "$t" 2>/dev/null
    done
}
trap cleanup_trash EXIT

# 只允许清理 $TOOLS 下的子目录；禁止 $TOOLS 本身、空路径与 ".."
_safe_trash_path() {  # <路径> [allow_nested]
    local target="${1:-}" nested="${2:-}"
    case "$target" in
        "$TOOLS"/*) : ;;
        *) red "拒绝清理：只允许 $TOOLS 下的子目录（收到: ${target:-<空>}）"; return 1 ;;
    esac
    case "$target" in
        *..*) red "拒绝清理可疑路径: $target"; return 1 ;;
    esac
    if [ "$nested" != "1" ]; then
        case "${target#"$TOOLS"/}" in
            */*|"") red "拒绝清理：只允许 $TOOLS 的直接子目录（收到: $target）"; return 1 ;;
        esac
    fi
    return 0
}

# 把目标目录移入 /tmp 回收站（原子 mv，不动用 rm -rf）
safe_reset_dir() {  # <$TOOLS 的直接子目录>
    local target="${1:-}" trash
    [ -e "$target" ] || return 0
    _safe_trash_path "$target" || return 1
    trash=$(mktemp -d "${TMPDIR:-/tmp}/dsh-trash.XXXXXX") || return 1
    if mv -- "$target" "$trash/old" 2>/dev/null; then
        TRASH_LIST+=("$trash")
        return 0
    fi
    rmdir "$trash" 2>/dev/null
    red "清理失败（目录被占用？）: $target"
    return 1
}

# 删除本次解压产生的内层临时目录（允许嵌套，仍限制在 $TOOLS 内）
safe_remove_path() {  # <$TOOLS 下任意深度的目录>
    local target="${1:-}" trash
    [ -e "$target" ] || return 0
    _safe_trash_path "$target" 1 || return 1
    trash=$(mktemp -d "${TMPDIR:-/tmp}/dsh-trash.XXXXXX") || return 1
    if mv -- "$target" "$trash/old" 2>/dev/null; then
        TRASH_LIST+=("$trash")
        return 0
    fi
    rmdir "$trash" 2>/dev/null
    return 1
}

# ── 下载校验（SHA256 固定表 scripts/download-sha256.txt）────────────────
SHA_MANIFEST="$HERE/download-sha256.txt"

expected_sha256() {  # <文件名> → 清单中的 sha256（无则空）
    [ -f "$SHA_MANIFEST" ] || return 0
    awk -v n="$1" '$1==n {print $2; exit}' "$SHA_MANIFEST"
}

verify_sha256() {  # <文件> <标签> <期望值> [quiet]
    local f="$1" label="${2:-$(basename "$1")}" exp="${3:-}" quiet="${4:-}" got
    if [ ! -f "$f" ]; then red "校验失败: 文件不存在 $f"; return 1; fi
    if has sha256sum; then
        got=$(sha256sum "$f" 2>/dev/null | awk '{print $1}')
    elif has shasum; then
        got=$(shasum -a 256 "$f" 2>/dev/null | awk '{print $1}')
    else
        red "校验失败: 缺 sha256sum/shasum，无法验证 $label"; return 1
    fi
    [ -z "$got" ] && { red "校验失败: 读不到 $label 的哈希"; return 1; }
    if [ -n "$exp" ]; then
        if [ "$got" = "$exp" ]; then
            [ "$quiet" = quiet ] || green "校验通过: $label"
            return 0
        fi
        red "SHA256 不匹配: $label"
        echo "  期望: $exp"
        echo "  实际: $got"
        return 1
    fi
    if [ "$quiet" != quiet ]; then
        yel "WARN 未钉哈希: $label（实际值可补进 scripts/download-sha256.txt）"
        echo "  实际 sha256: $got"
    fi
    return 0
}
pymod() { python3 -c "import $1" >/dev/null 2>&1; }
jar_ok() { [ -s "$1" ] && has java && java -jar "$1" --version >/dev/null 2>&1; }

MODE="all"
case "${1:-}" in
    --check) MODE="check" ;;
    --apt) MODE="apt" ;;
    --pip) MODE="pip" ;;
    --frida) MODE="frida" ;;
    --jadx) MODE="jadx" ;;
    --re) MODE="re" ;;
    --net) MODE="net" ;;
    --community|--extra) MODE="community" ;;
    --all|"") MODE="all" ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) red "未知参数: $1"; exit 2 ;;
esac

echo "══════ 工具自动安装 ══════"
echo "环境: $(uname -m) / Python $(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo '?') / 缓存: $TOOLCACHE"
echo

# 缺件清单
MISS_APT=(); MISS_PIP=()
for c in sqlite3 r2 xxd jq xz strings; do has "$c" || MISS_APT+=("$c"); done
[ -f "/root/tools/frida-server-${FRIDA_VER_DEFAULT}-android-arm64" ] || has frida || true
for m in frida frida_tools androguard lief blackboxprotobuf; do pymod "$m" || MISS_PIP+=("$m"); done
FRIDA_VER=$(python3 -c "import frida;print(frida.__version__)" 2>/dev/null || echo "$FRIDA_VER_DEFAULT")
FS_PLAIN="$TOOLS/frida-server-${FRIDA_VER}-android-arm64"
JADX_BIN="/root/jadx/bin/jadx"

# --re 缺件（可选增强项）：apkid/binwalk/hermes-dec/objection/apk-mitm + CFR/smali jar
re_missing() {
    local miss=()
    has apkid || miss+=(apkid)
    has hbc-decompiler || miss+=(hermes-dec)
    has objection || miss+=(objection)
    binwalk_ok || miss+=(binwalk)
    has apk-mitm || miss+=(apk-mitm)
    jar_ok "$JARS/cfr.jar" || miss+=(cfr.jar)
    if has smali3 && smali3 --version >/dev/null 2>&1 && has baksmali3 && baksmali3 --version >/dev/null 2>&1; then :; else
        miss+=(smali3/baksmali3)
    fi
    echo "${miss[*]:-无}"
}

# binwalk 2.1.0 的 pip 包在 Python 3 上 import 就崩（缺 binwalk.core），能跑才算有
binwalk_ok() { { has binwalk && binwalk --help >/dev/null 2>&1; } || { [ -x /usr/bin/binwalk ] && /usr/bin/binwalk --help >/dev/null 2>&1; }; }

# --net 缺件（编译链；mitmproxy 单独判断）
net_apt_missing() {
    local miss=()
    has gcc || miss+=(build-essential)
    has cmake || miss+=(cmake)
    has pkg-config || miss+=(pkg-config)
    dpkg -s python3-dev >/dev/null 2>&1 || miss+=(python3-dev)
    dpkg -s libssl-dev >/dev/null 2>&1 || miss+=(libssl-dev)
    dpkg -s libffi-dev >/dev/null 2>&1 || miss+=(libffi-dev)
    echo "${miss[*]:-无}"
}

if [ "$MODE" = "check" ]; then
    echo "[apt 缺失] ${MISS_APT[*]:-无}"
    echo "[pip 缺失] ${MISS_PIP[*]:-无}"
    [ -x "$FS_PLAIN" ] && echo "[frida-server] 已就绪: $FS_PLAIN" || echo "[frida-server] 缺（版本 $FRIDA_VER）"
    [ -x "$JADX_BIN" ] && echo "[jadx] 已就绪: $JADX_BIN" || echo "[jadx] 缺（$JADX_VER）"
    echo "[re 缺失] $(re_missing)"
    echo "[net 缺失] $(net_apt_missing)；mitmproxy $(has mitmproxy && echo 已就绪 || echo 缺)"
    echo
    echo "下载源："
    echo "  frida-server: ${GH_PROXY}https://github.com/frida/frida/releases/download/${FRIDA_VER}/frida-server-${FRIDA_VER}-android-arm64.xz"
    echo "  jadx:         ${GH_PROXY}https://github.com/skylot/jadx/releases/download/v${JADX_VER}/jadx-${JADX_VER}.zip"
    echo "  pip:          pip install frida frida-tools androguard lief blackboxprotobuf -i $PIP_INDEX"
    echo "  apt:          apt-get install -y sqlite3 radare2 binutils xxd jq xz-utils"
    echo "  cfr:          ${GH_PROXY}https://github.com/leibnitz27/cfr/releases/download/${CFR_VER}/cfr-${CFR_VER}.jar → $JARS/cfr.jar"
    echo "  smali3:       ${GH_PROXY}https://github.com/baksmali/smali/releases/download/${SMALI_VER}/smali-${SMALI_VER}-fat.jar"
    echo "  baksmali3:    ${GH_PROXY}https://github.com/baksmali/smali/releases/download/${SMALI_VER}/baksmali-${SMALI_VER}-fat.jar"
    echo "  re pip:       pip install apkid hermes-dec objection -i $PIP_INDEX   （binwalk 优先 apt-get install -y binwalk）"
    echo "  apk-mitm:     npm install -g apk-mitm --registry=$NPM_REGISTRY"
    echo "  net:          apt-get install -y build-essential cmake python3-dev pkg-config libssl-dev libffi-dev"
    echo "                && pip install mitmproxy -i $PIP_INDEX（编译重，--all 不含，需 --net 单独跑）"
    exit 0
fi

# 基础工具（解压/下载）
for c in curl unzip; do has "$c" || apt-get install -y --no-install-recommends "$c" >/dev/null 2>&1 || true; done

apt_group() {
    local miss=()
    for c in sqlite3 r2 xxd jq xz strings; do has "$c" || miss+=("$c"); done
    if [ ${#miss[@]} -eq 0 ]; then green "apt 工具已齐"; return; fi
    echo "apt 安装: ${miss[*]}"
    apt-get update -qq 2>&1 | tail -1
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        sqlite3 radare2 binutils xxd jq xz-utils 2>&1 | tail -2
    green "apt 工具完成"
}

pip_group() {
    local need=(frida frida-tools androguard lief blackboxprotobuf)
    local miss=()
    pymod frida || miss+=(frida)
    pymod frida_tools || miss+=(frida-tools)
    pymod androguard || miss+=(androguard)
    pymod lief || miss+=(lief)
    pymod blackboxprotobuf || miss+=(blackboxprotobuf)
    if [ ${#miss[@]} -eq 0 ]; then
        green "pip 工具已齐（frida $(python3 -c 'import frida;print(frida.__version__)' 2>/dev/null)）"
        link_bins; return
    fi
    echo "pip 安装: ${miss[*]}"
    if [ -d "$TOOLCACHE/wheels" ] && ls "$TOOLCACHE"/wheels/*.whl >/dev/null 2>&1; then
        echo "  用本地缓存轮子: $TOOLCACHE/wheels"
        pip install --no-index --find-links "$TOOLCACHE/wheels" "${need[@]}" 2>&1 | tail -2
    else
        echo "  从 $PIP_INDEX 下载"
        pip install --index-url "$PIP_INDEX" --trusted-host "$PIP_HOST" --retries 4 --timeout 60 "${need[@]}" 2>&1 | tail -2 \
          || pip install --index-url https://pypi.org/simple --retries 4 --timeout 60 "${need[@]}" 2>&1 | tail -2
    fi
    link_bins
    green "pip 工具完成"
}

link_bins() {
    for b in frida frida-ps frida-trace frida-ls-devices; do
        local src=""
        src=$(command -v "$b" 2>/dev/null || true)
        [ -z "$src" ] && [ -x "/opt/python/bin/$b" ] && src="/opt/python/bin/$b"
        [ -n "$src" ] && ln -sf "$src" "/usr/local/bin/$b" 2>/dev/null || true
    done
}

# 缓存优先下载：目标已存在则跳过；缓存有离线包先用；否则按 URL 顺序回退（gh-proxy → 直连）
fetch_to() {            # fetch_to <目标文件> <缓存文件> <url...>（下载/缓存后校验 SHA256）
    local dest="$1" cache="$2"; shift 2
    local exp; exp=$(expected_sha256 "$(basename "$cache")")
    [ -z "$exp" ] && exp=$(expected_sha256 "$(basename "$dest")")
    if [ -s "$dest" ]; then
        if verify_sha256 "$dest" "$(basename "$dest")" "$exp" quiet; then return 0; fi
        red "已有文件哈希不一致，删除后重下: $dest"
        rm -f "$dest"
    fi
    if [ -s "$cache" ]; then
        if cp -f "$cache" "$dest" 2>/dev/null && [ -s "$dest" ]; then
            if verify_sha256 "$dest" "$(basename "$dest")" "$exp"; then return 0; fi
            rm -f "$dest"
            return 1
        fi
        rm -f "$dest"
    fi
    local u
    for u in "$@"; do
        echo "  下载 $(basename "$dest") ← $u"
        if curl -fL --max-time 1800 -o "$dest.part" "$u" && [ -s "$dest.part" ]; then
            mv -f "$dest.part" "$dest"
            if ! verify_sha256 "$dest" "$(basename "$dest")" "$exp"; then
                rm -f "$dest"
                red "校验失败，已删除: $(basename "$dest")"
                return 1
            fi
            cp -f "$dest" "$cache" 2>/dev/null || true
            return 0
        fi
        rm -f "$dest.part"
    done
    return 1
}

pip_install_log() {     # pip_install_log <包...>：aliyun 失败自动回退 pypi（用日志文件保住真实退出码）
    local log; log=$(mktemp)
    if pip install --index-url "$PIP_INDEX" --trusted-host "$PIP_HOST" --retries 4 --timeout 120 "$@" >"$log" 2>&1; then
        tail -2 "$log"; rm -f "$log"; return 0
    fi
    yel "  aliyun 镜像失败，回退 pypi.org"
    tail -3 "$log"
    pip install --index-url https://pypi.org/simple --retries 4 --timeout 120 "$@" >"$log" 2>&1
    local rc=$?
    tail -2 "$log"; rm -f "$log"
    return $rc
}

# ---- --re：深度逆向 / 反编译增强（apkid、binwalk、hermes-dec、objection、apk-mitm、CFR、smali 3.x）----
re_pip_group() {
    local miss=() pkgs=()
    has apkid || { miss+=(apkid); pkgs+=(apkid); }
    has hbc-decompiler || { miss+=(hermes-dec); pkgs+=(hermes-dec); }   # pip 包 hermes-dec 的 CLI 叫 hbc-decompiler
    has objection || { miss+=(objection); pkgs+=(objection); }
    if [ ${#pkgs[@]} -eq 0 ]; then
        green "re pip 工具已齐（apkid / hermes-dec / objection）"
    else
        echo "pip 安装 re 工具: ${miss[*]}"
        pip_install_log "${pkgs[@]}" || red "pip 安装失败：${miss[*]}（网络或编译依赖，稍后重跑 --re）"
        local still=()
        has apkid || still+=(apkid)
        has hbc-decompiler || still+=(hermes-dec)
        has objection || still+=(objection)
        [ ${#still[@]} -eq 0 ] && green "re pip 工具完成" || red "re pip 仍缺: ${still[*]}"
    fi
    # binwalk：Ubuntu 源有 2.3.4（apt 快、无需编译）；pip 的 2.1.0 在 Python 3 上
    # import 即崩（缺 binwalk.core），只作最后兜底，且装好 apt 版后指回它。
    if binwalk_ok; then
        green "binwalk 已就绪"
    else
        echo "安装 binwalk（优先 apt 2.3.4，失败再 pip）"
        apt-get install -y --no-install-recommends binwalk >/dev/null 2>&1 || true
        if [ -x /usr/bin/binwalk ] && /usr/bin/binwalk --help >/dev/null 2>&1; then
            # pip 装过的坏 shim 在 /usr/local/bin，会优先于 /usr/bin，覆盖指向 apt 版
            binwalk --help >/dev/null 2>&1 || ln -sf /usr/bin/binwalk /usr/local/bin/binwalk 2>/dev/null || true
            green "binwalk 完成（apt $(/usr/bin/binwalk --help 2>&1 | grep -v '^[[:space:]]*$' | head -1)）"
        elif pip_install_log binwalk && binwalk_ok; then
            green "binwalk 完成（pip）"
        else
            red "binwalk 安装失败：可 apt-get install -y binwalk，或先 --net 装编译链再重跑 --re"
        fi
    fi
}

apk_mitm_group() {
    if has apk-mitm; then green "apk-mitm 已就绪: $(command -v apk-mitm)"; return; fi
    if ! has npm; then red "缺 npm（node 环境），无法安装 apk-mitm；请先确认 node/npm 可用"; return; fi
    echo "npm 安装 apk-mitm（registry=$NPM_REGISTRY）"
    npm install -g --registry="$NPM_REGISTRY" apk-mitm 2>&1 | tail -3
    has apk-mitm && green "apk-mitm 完成: $(command -v apk-mitm)" \
      || red "apk-mitm 安装失败（npm 网络），可稍后重跑 --re"
}

jars_group() {
    mkdir -p "$JARS" "$TOOLCACHE"
    if ! has java; then red "缺 java，jar 工具无法运行（apt-get install -y openjdk-21-jre-headless）"; return; fi

    # CFR 0.152：单文件 jar，反编译大 dex 比 jadx 稳
    if jar_ok "$JARS/cfr.jar"; then
        green "CFR 已就绪: $JARS/cfr.jar ($(java -jar "$JARS/cfr.jar" --version 2>&1 | head -1))"
    else
        fetch_to "$JARS/cfr.jar" "$TOOLCACHE/cfr-${CFR_VER}.jar" \
          "${GH_PROXY}https://github.com/leibnitz27/cfr/releases/download/${CFR_VER}/cfr-${CFR_VER}.jar" \
          "https://github.com/leibnitz27/cfr/releases/download/${CFR_VER}/cfr-${CFR_VER}.jar"
        if jar_ok "$JARS/cfr.jar"; then
            green "CFR 已安装: $JARS/cfr.jar ($(java -jar "$JARS/cfr.jar" --version 2>&1 | head -1))"
        else
            rm -f "$JARS/cfr.jar"
            red "CFR 下载失败（网络），稍后重跑 --re"
        fi
    fi

    # smali / baksmali 3.x：v3 只发 thin jar（无 Main-Class，不能直接 java -jar）；
    # google/smali 的 3.0.9 release 没有二进制附件，可运行的是 baksmali/smali 仓库的
    # *-fat.jar（toolsmith 实测通过）。故这里固定用 fat jar，多地址回退。
    local sdst="$JARS/smali-${SMALI_VER}-fat.jar"
    local bdst="$JARS/baksmali-${SMALI_VER}-fat.jar"
    if jar_ok "$sdst"; then
        green "smali3 已就绪: $sdst"
    else
        fetch_to "$sdst" "$TOOLCACHE/smali-${SMALI_VER}-fat.jar" \
          "${GH_PROXY}https://github.com/baksmali/smali/releases/download/${SMALI_VER}/smali-${SMALI_VER}-fat.jar" \
          "https://github.com/baksmali/smali/releases/download/${SMALI_VER}/smali-${SMALI_VER}-fat.jar" \
          "${GH_PROXY}https://github.com/baksmali/smali/releases/download/${SMALI_VER}/smali-${SMALI_VER}-fat-release.jar"
        jar_ok "$sdst" && green "smali3 jar 已安装: $sdst" \
          || { rm -f "$sdst"; red "smali jar 下载失败（网络），稍后重跑 --re"; }
    fi
    if jar_ok "$bdst"; then
        green "baksmali3 已就绪: $bdst"
    else
        fetch_to "$bdst" "$TOOLCACHE/baksmali-${SMALI_VER}-fat.jar" \
          "${GH_PROXY}https://github.com/baksmali/smali/releases/download/${SMALI_VER}/baksmali-${SMALI_VER}-fat.jar" \
          "https://github.com/baksmali/smali/releases/download/${SMALI_VER}/baksmali-${SMALI_VER}-fat.jar" \
          "${GH_PROXY}https://github.com/baksmali/smali/releases/download/${SMALI_VER}/baksmali-${SMALI_VER}-fat-release.jar"
        jar_ok "$bdst" && green "baksmali3 jar 已安装: $bdst" \
          || { rm -f "$bdst"; red "baksmali jar 下载失败（网络），稍后重跑 --re"; }
    fi

    # 生成 smali3 / baksmali3 包装脚本（幂等：每次都按当前版本路径重写）
    if jar_ok "$sdst" && jar_ok "$bdst"; then
        write_jar_wrapper /usr/local/bin/smali3 "$sdst"
        write_jar_wrapper /usr/local/bin/baksmali3 "$bdst"
        green "smali3/baksmali3 已就绪: $(smali3 --version 2>&1 | head -1) / $(baksmali3 --version 2>&1 | head -1)"
    fi
}

write_jar_wrapper() {    # write_jar_wrapper <包装脚本路径> <jar 路径>
    local out="$1" jar="$2"
    cat > "$out" <<EOF
#!/usr/bin/env bash
# 由 install_tools.sh --re 生成：smali/baksmali 3.x fat jar 包装（$SMALI_VER）
exec java -jar "$jar" "\$@"
EOF
    chmod +x "$out" 2>/dev/null || true
}

re_group() {
    re_pip_group
    apk_mitm_group
    jars_group
}

# ---- --net：抓包编译链 + mitmproxy（体积大，单独跑；不进 --all）----
net_group() {
    local apts=(build-essential cmake python3-dev pkg-config libssl-dev libffi-dev)
    echo "apt 安装编译链: ${apts[*]}（mitmproxy 及原生依赖编译用）"
    apt-get update -qq 2>&1 | tail -1
    local log; log=$(mktemp)
    if DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${apts[@]}" >"$log" 2>&1; then
        tail -2 "$log"; green "编译链就绪"
    else
        tail -6 "$log"; rm -f "$log"
        red "apt 安装编译链失败（网络/源），检查 apt 源后重跑 --net"; return
    fi
    rm -f "$log"

    if has mitmproxy; then green "mitmproxy 已就绪: $(mitmproxy --version 2>&1 | head -1)"; return; fi
    echo "pip 安装 mitmproxy（超时 300s/包，aarch64 一般有 wheel）…"
    local t0 t1 log2; log2=$(mktemp); t0=$(date +%s)
    if pip install --index-url "$PIP_INDEX" --trusted-host "$PIP_HOST" --retries 3 --timeout 300 mitmproxy >"$log2" 2>&1; then
        t1=$(date +%s); tail -2 "$log2"
        green "mitmproxy 完成（耗时 $((t1-t0))s）"
    else
        t1=$(date +%s); tail -4 "$log2"
        yel "pip 安装失败（耗时 $((t1-t0))s），回退 pypi.org 重试"
        if pip install --index-url https://pypi.org/simple --retries 3 --timeout 300 mitmproxy >"$log2" 2>&1; then
            tail -2 "$log2"; green "mitmproxy 完成（pypi 回退）"
        else
            tail -4 "$log2"
            red "mitmproxy 安装失败：可试 apt-get install -y mitmproxy（8.1.1，功能较旧）；或稍后重跑 --net"
        fi
    fi
    rm -f "$log2"
    has mitmproxy && green "mitmproxy 已就绪: $(mitmproxy --version 2>&1 | head -1)" \
      || red "仍缺 mitmproxy（抓包可先用 Frida Hook 代替）"
}

frida_group() {
    FRIDA_VER=$(python3 -c "import frida;print(frida.__version__)" 2>/dev/null || echo "$FRIDA_VER_DEFAULT")
    FS_PLAIN="$TOOLS/frida-server-${FRIDA_VER}-android-arm64"
    if [ -x "$FS_PLAIN" ]; then green "frida-server 已就绪: $FS_PLAIN"; return; fi
    mkdir -p "$TOOLS"
    local xz="$TOOLCACHE/frida-server-${FRIDA_VER}-android-arm64.xz"
    if [ ! -f "$xz" ]; then
        echo "下载 frida-server $FRIDA_VER（约 24MB 压缩）…"
        curl -fL --max-time 1800 -o "$xz" \
          "${GH_PROXY}https://github.com/frida/frida/releases/download/${FRIDA_VER}/frida-server-${FRIDA_VER}-android-arm64.xz" \
          || curl -fL --max-time 1800 -o "$xz" \
             "https://github.com/frida/frida/releases/download/${FRIDA_VER}/frida-server-${FRIDA_VER}-android-arm64.xz" \
          || { red "frida-server 下载失败（网络），稍后重跑 --frida"; return; }
    fi
    if ! verify_sha256 "$xz" "frida-server-${FRIDA_VER}-android-arm64.xz" "$(expected_sha256 "$(basename "$xz")")"; then
        rm -f "$xz"
        red "frida-server 校验失败：已删除不一致的下载，稍后重跑 --frida"
        return
    fi
    if ! has xz; then apt-get install -y --no-install-recommends xz-utils >/dev/null 2>&1 || true; fi
    xz -dc "$xz" > "$FS_PLAIN" && chmod +x "$FS_PLAIN" && green "frida-server 已放好: $FS_PLAIN"
}

# ── 社区工具组（按需装，不默认装）─────────────────────────────────────────
latest_tag() {  # latest_tag <owner/repo> → tag（如 v2.4 / 1.11.1）
    local repo="$1" eff tag
    eff=$(curl -4 -fsSL --max-time 15 -o /dev/null -w '%{url_effective}' "https://github.com/${repo}/releases/latest" 2>/dev/null) || return 1
    tag="${eff##*/tag/}"; tag="${tag%%\?*}"
    [ -n "$tag" ] && [ "$tag" != "$eff" ] && printf '%s' "$tag"
}

fetch_gh() {  # fetch_gh <缓存文件> <相对路径>：先 ghfast 再 gh-proxy，下载后校验 SHA256
    local out="$1" rel="$2" exp u
    [ -s "$out" ] && return 0
    exp=$(expected_sha256 "$(basename "$out")")
    for u in "https://ghfast.top/${rel}" "https://gh-proxy.com/${rel}"; do
        rm -f "$out.part"
        curl -4 -fL --max-time 1800 -o "$out.part" "$u" 2>/dev/null || continue
        [ -s "$out.part" ] || continue
        mv -f "$out.part" "$out"
        if verify_sha256 "$out" "$(basename "$out")" "$exp"; then return 0; fi
        rm -f "$out"; return 1
    done
    rm -f "$out"; return 1
}

community_group() {
    echo "── 社区工具组（按需，约 60MB）──"
    # 1) unicorn + capstone（MobileRE-Skill 的离线模拟执行基础）
    pymod unicorn || pip_install_log unicorn
    pymod capstone || pip_install_log capstone
    # 2) Vineflower（incogbyte：jadx 之外的第二反编译器）
    local vf_jar="/root/tools/jars/vineflower.jar" tag
    if has java && [ -s "$vf_jar" ] && java -jar "$vf_jar" --version >/dev/null 2>&1; then
        green "Vineflower 已就绪: $vf_jar"
    else
        tag=$(latest_tag Vineflower/vineflower || true)
        [ -n "$tag" ] || tag="1.11.1"   # 固定回退版本
        if [ -n "$tag" ]; then
            echo "下载 Vineflower $tag …"
            mkdir -p /root/tools/jars
            if fetch_gh "$TOOLCACHE/vineflower-${tag}.jar" "https://github.com/Vineflower/vineflower/releases/download/${tag}/vineflower-${tag}.jar"; then
                cp -f "$TOOLCACHE/vineflower-${tag}.jar" "$vf_jar"
                write_jar_wrapper /usr/local/bin/vineflower "$vf_jar"
                green "Vineflower 已装: $vf_jar"
            else
                yel "Vineflower 下载失败（网络），稍后重跑 --community"
            fi
        else
            yel "取不到 Vineflower 最新 release（网络），跳过"
        fi
    fi
    # 3) dex2jar（DEX→JAR，再喂 Vineflower）
    if [ -x /root/tools/dex2jar/d2j-dex2jar.sh ]; then
        green "dex2jar 已就绪: /root/tools/dex2jar"
    else
        tag=$(latest_tag pxb1988/dex2jar || true)
        [ -n "$tag" ] || tag="v2.4"     # 固定回退版本
        if [ -n "$tag" ]; then
            echo "下载 dex2jar $tag …"
            if fetch_gh "$TOOLCACHE/dex-tools-${tag}.zip" "https://github.com/pxb1988/dex2jar/releases/download/${tag}/dex-tools-${tag}.zip"; then
                safe_reset_dir "$TOOLS/dex2jar"
                mkdir -p /root/tools/dex2jar
                unzip -oq "$TOOLCACHE/dex-tools-${tag}.zip" -d /root/tools/dex2jar
                # zip 内常带一层目录（dex-tools-v2.4/），拍平到 /root/tools/dex2jar
                if [ ! -f /root/tools/dex2jar/d2j-dex2jar.sh ]; then
                    inner=$(find /root/tools/dex2jar -maxdepth 2 -name d2j-dex2jar.sh -printf '%h\n' | head -1)
                    [ -n "$inner" ] && cp -a "$inner"/. "$TOOLS/dex2jar"/ && safe_remove_path "$inner"
                fi
                chmod +x /root/tools/dex2jar/*.sh 2>/dev/null || true
                green "dex2jar 已装: /root/tools/dex2jar/d2j-dex2jar.sh"
            else
                yel "dex2jar 下载失败（网络），稍后重跑 --community"
            fi
        else
            yel "取不到 dex2jar 最新 release（网络），跳过"
        fi
    fi
    # 4) bundletool（AAB→APK）
    local bt_jar="/root/tools/jars/bundletool.jar" btag
    if [ -s "$bt_jar" ] && has java && java -jar "$bt_jar" version >/dev/null 2>&1; then
        green "bundletool 已就绪: $bt_jar"
    else
        btag=$(latest_tag google/bundletool || true)
        [ -n "$btag" ] || btag="1.18.3"   # 固定回退版本
        if [ -n "$btag" ]; then
            local ver="${btag#v}"
            echo "下载 bundletool $btag …"
            mkdir -p /root/tools/jars
            if fetch_gh "$TOOLCACHE/bundletool-${ver}.jar" "https://github.com/google/bundletool/releases/download/${btag}/bundletool-all-${ver}.jar"; then
                cp -f "$TOOLCACHE/bundletool-${ver}.jar" "$bt_jar"
                write_jar_wrapper /usr/local/bin/bundletool "$bt_jar"
                green "bundletool 已装: $bt_jar"
            else
                yel "bundletool 下载失败（网络），稍后重跑 --community"
            fi
        else
            yel "取不到 bundletool 最新 release（网络），跳过"
        fi
    fi
    green "社区工具组完成（用到再装，不占默认空间）"
}

jadx_group() {
    if [ -x "$JADX_BIN" ]; then
        ln -sf "$JADX_BIN" /usr/local/bin/jadx 2>/dev/null || true
        green "jadx 已就绪: $($JADX_BIN --version 2>&1 | head -1)"; return
    fi
    local zipf="$TOOLCACHE/jadx-${JADX_VER}.zip"
    if [ ! -f "$zipf" ]; then
        echo "下载 jadx $JADX_VER（解压后约 122MB）…"
        curl -fL --max-time 1800 -o "$zipf" \
          "${GH_PROXY}https://github.com/skylot/jadx/releases/download/v${JADX_VER}/jadx-${JADX_VER}.zip" \
          || curl -fL --max-time 1800 -o "$zipf" \
             "https://github.com/skylot/jadx/releases/download/v${JADX_VER}/jadx-${JADX_VER}.zip" \
          || { red "jadx 下载失败（网络），稍后重跑 --jadx"; return; }
    fi
    if ! verify_sha256 "$zipf" "jadx-${JADX_VER}.zip" "$(expected_sha256 "$(basename "$zipf")")"; then
        rm -f "$zipf"
        red "jadx 校验失败：已删除不一致的下载，稍后重跑 --jadx"
        return
    fi
    unzip -oq "$zipf" -d /root/jadx && chmod +x "$JADX_BIN" \
      && ln -sf "$JADX_BIN" /usr/local/bin/jadx 2>/dev/null && green "jadx 已安装: $($JADX_BIN --version 2>&1 | head -1)"
}

main() {
    case "$MODE" in
        apt) apt_group ;;
        pip) pip_group ;;
        frida) frida_group ;;
        jadx) jadx_group ;;
        re) re_group ;;
        net) net_group ;;
        community) community_group ;;
        all) apt_group; pip_group; frida_group; jadx_group; re_group ;;
    esac

    echo
    bash "$HERE/toolcheck.sh"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then main; fi
