#!/usr/bin/env bash
# 输入法安全打字（手机自动化）：检测输入法（拼音/双拼/九键）、免打字开网址、临时切英文键盘。
#
# 背景：AI 用 `type` 往输入框打网址/英文时，中文输入法（拼音/双拼/九键）会把
# 英文组合成中文、回车变上屏，导致打不出来、页面卡死。本脚本提供安全路径。
#
# 用法:
#   bash scripts/device_input.sh [--serial SERIAL] <子命令> [参数]   # serial 省略时自动发现
#
#   detect                     检测 adb/root、当前输入法、可用输入法、英文键盘候选、双拼方案线索
#   url <网址> [--dry-run]     直接 am start VIEW 打开（不碰键盘，首选）
#   type <文本> [--switch-ime] [--dry-run]
#                              安全打字：当前是中文输入法时默认拒绝并提示走剪贴板；
#                              加 --switch-ime 会临时切英文键盘，打完自动切回
#   ascii list|on|off          列出英文键盘候选 / 切到英文键盘 / 切回原输入法
#   ime list|get|set <id>      查看/设置输入法
#   state                      查看上次保存的原输入法（用于恢复）
#
# 示例：中文输入法常见包名 com.sohu.inputmethod.sogou 等。
# 没有 adb 时的替代路径见 references/ime-typing.md（剪贴板粘贴 / mcp__phone__open）。
set -u

# 共享 adb 自动发现（无线调试端口随机：扫描监听端口并自动 connect）
HERE_DIR=$(cd "$(dirname "$0")" && pwd)
[ -f "$HERE_DIR/adb_common.sh" ] && . "$HERE_DIR/adb_common.sh"

# ── 自动发现在线 adb 设备（无线调试端口是随机的，不一定是 5555）──────────
resolve_serial() { adb_resolve_serial "${ADB_BIN:-adb}" "${SERIAL_DEFAULT:-127.0.0.1:5555}"; }
list_devices() { "$ADB_BIN" devices 2>/dev/null | sed -n '2,$p' | sed '/^$/d'; }

ADB_BIN="${ADB_BIN:-adb}"
SERIAL_DEFAULT="127.0.0.1:5555"     # 旧 tcpip 固定端口：仅作自动发现候选（无线调试端口随机）
SERIAL="${ADB_SERIAL:-}"
STATE_FILE="/tmp/device_input_prev_ime"
DRY=0
SWITCH=0
SUB=""

# 先解析全局 --serial（可出现在最前）
while [ $# -gt 0 ]; do
    case "$1" in
        --serial) shift; SERIAL="${1:-$SERIAL_DEFAULT}" ;;
        *) break ;;
    esac
    shift
done
SUB="${1:-}"; [ $# -gt 0 ] && shift
if [ -z "${SERIAL:-}" ]; then SERIAL="$(resolve_serial)"; fi
[ -n "${SERIAL:-}" ] || SERIAL="${SERIAL_DEFAULT}"

args=("$@")

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
yel()   { printf '\033[33m%s\033[0m\n' "$*"; }
adb_s() { "$ADB_BIN" -s "$SERIAL" shell "$@"; }
need_dev() {
    if ! "$ADB_BIN" -s "$SERIAL" get-state 2>/dev/null | grep -q device; then
        red "adb 设备不可用（$SERIAL）。"
        echo "→ 先确认无线调试在线：adb connect $SERIAL；或看 scripts/adb_device.sh check"
        echo "→ adb 不可用时改用 MCP：mcp__phone__open(url=...) / mcp__phone__clipboard(set=...)"
        return 1
    fi
}

esc_sq() { printf '%s' "$1" | sed "s/'/'\\\\''/g"; }

get_ime() { adb_s settings get secure default_input_method 2>/dev/null | tr -d '\r' | head -1; }

is_chinese_ime() {
    case "$1" in
        *sogou*|*baidu*|*iflytek*|*xunfei*|*qqlatin*|*qq*|*sohu*|*bopomofo*|*pinyin*|*ime.zh*|*iFlytek*) return 0 ;;
        *) return 1 ;;
    esac
}

ascii_candidates() {
    adb_s ime list -s 2>/dev/null | tr -d '\r' | grep -iE 'latin|gboard|aosp|ascii' | grep -viE 'sogou|baidu|iflytek|qq'
}



case "$SUB" in
  detect)
    need_dev || exit 1
    echo "══════ 输入法检测 ══════"
    DEVUID=$(adb_s id -u 2>/dev/null | tr -d '\r')
    echo "设备: $SERIAL  root: uid=${DEVUID:-?}"
    CUR=$(get_ime)
    echo "当前输入法: ${CUR:-未知}"
    if is_chinese_ime "$CUR"; then
        yel "→ 中文输入法。直接 type 英文/网址有被组合成中文的风险。"
    else
        green "→ 看起来是中性/英文键盘，type ASCII 相对安全（仍建议短文本）"
    fi
    echo
    echo "已启用/可用输入法:"
    adb_s ime list -s 2>/dev/null | tr -d '\r' | sed 's/^/  /'
    echo
    echo "英文键盘候选（可临时切）:"
    cand=$(ascii_candidates)
    if [ -n "$cand" ]; then echo "$cand" | sed 's/^/  /'; else yel "  （没有可用英文键盘，别硬打；走剪贴板/URL 直开）"; fi
    echo
    if [ "${DEVUID:-x}" = "0" ] && is_chinese_ime "$CUR"; then
        PKG=$(printf '%s' "$CUR" | cut -d/ -f1)
        echo "root 可用，查输入法方案线索（$PKG）:"
        adb_s "grep -ilr 'xiaohe\|shuangpin\|双拼\|九键\|pinyin\|方案' /data/data/$PKG/shared_prefs/ 2>/dev/null | head -5" 2>/dev/null | tr -d '\r' | sed 's/^/  /'
        adb_s "grep -rhoi 'xiaohe\|shuangpin\|双拼\|九键\|全拼' /data/data/$PKG/shared_prefs/ 2>/dev/null | sort -u | head -5" 2>/dev/null | tr -d '\r' | sed 's/^/  关键词: /'
        echo "  （具体的双拼方案名若读不到，直接问用户一句：拼音 / 双拼 / 九键？）"
    fi
    ;;
  url)
    URL="${args[0]:-}"
    [ -n "$URL" ] || { red "用法: device_input.sh url <网址> [--dry-run]"; exit 2; }
    for a in "${args[@]:1}"; do [ "$a" = "--dry-run" ] && DRY=1; done
    if [ "$DRY" = 1 ]; then echo "adb -s $SERIAL shell am start -a android.intent.action.VIEW -d '$URL'"; exit 0; fi
    need_dev || exit 1
    adb_s am start -a android.intent.action.VIEW -d "'$(esc_sq "$URL")'" >/dev/null 2>&1 \
      && green "已在设备上打开: $URL（没经过输入法）" \
      || { red "打开失败，检查网址是否合法/有无浏览器"; exit 1; }
    ;;
  type)
    TEXT="${args[0]:-}"
    [ -n "$TEXT" ] || { red "用法: device_input.sh type <文本> [--switch-ime] [--dry-run]"; exit 2; }
    for a in "${args[@]:1}"; do
        [ "$a" = "--switch-ime" ] && SWITCH=1
        [ "$a" = "--dry-run" ] && DRY=1
    done
    REMOTE=$(printf '%s' "$TEXT" | sed 's/ /%s/g')
    if [ "$DRY" = 1 ]; then echo "adb -s $SERIAL shell input text '$(esc_sq "$REMOTE")'"; exit 0; fi
    need_dev || exit 1
    CUR=$(get_ime)
    if is_chinese_ime "$CUR" && [ "$SWITCH" = 0 ]; then
        red "当前是中文输入法（$CUR），拒绝直接打字（会被组合成中文）。"
        echo "  选择：① 用剪贴板：mcp__phone__clipboard(set=...) 然后长按粘贴"
        echo "        ② 用 URL 直开：bash scripts/device_input.sh url <网址>"
        echo "        ③ 临时切英文键盘：bash scripts/device_input.sh type '<文本>' --switch-ime"
        exit 2
    fi
    if [ "$SWITCH" = 1 ]; then
        CAND=$(ascii_candidates | head -1)
        [ -n "$CAND" ] || { red "没有英文键盘可切；改用剪贴板/URL 直开"; exit 1; }
        printf '%s' "$CUR" > "$STATE_FILE"
        adb_s ime set "$CAND" >/dev/null 2>&1
        sleep 0.6
        green "临时切到: $CAND（原输入法已记到 $STATE_FILE）"
    fi
    adb_s input text "'$(esc_sq "$REMOTE")'" >/dev/null 2>&1 && green "已输入: $TEXT" || { red "输入失败"; exit 1; }
    if [ "$SWITCH" = 1 ] && [ -s "$STATE_FILE" ]; then
        adb_s ime set "$(cat "$STATE_FILE")" >/dev/null 2>&1 && green "已切回原输入法: $(cat "$STATE_FILE")"
    fi
    ;;
  ascii)
    MODE="${args[0]:-list}"
    case "$MODE" in
      list) need_dev || exit 1; local_c=$(ascii_candidates); if [ -n "$local_c" ]; then echo "$local_c" | sed 's/^/  /'; else yel "（没有英文键盘候选）"; fi ;;
      on)
        need_dev || exit 1
        CAND=$(ascii_candidates | head -1)
        [ -n "$CAND" ] || { red "没有英文键盘可切"; exit 1; }
        CUR=$(get_ime); printf '%s' "$CUR" > "$STATE_FILE"
        adb_s ime set "$CAND" >/dev/null 2>&1 && green "已切到英文键盘: $CAND（原输入法: $CUR）"
        ;;
      off)
        need_dev || exit 1
        [ -s "$STATE_FILE" ] || { red "没有记录原输入法（$STATE_FILE 为空）"; exit 1; }
        adb_s ime set "$(cat "$STATE_FILE")" >/dev/null 2>&1 && green "已切回: $(cat "$STATE_FILE")"
        ;;
      *) red "用法: ascii list|on|off"; exit 2 ;;
    esac
    ;;
  ime)
    MODE="${args[0]:-get}"
    case "$MODE" in
      list) need_dev || exit 1; adb_s ime list -s 2>/dev/null | tr -d '\r' | sed 's/^/  /' ;;
      get) need_dev || exit 1; get_ime ;;
      set)
        ID="${args[1]:-}"; [ -n "$ID" ] || { red "用法: ime set <ime-id>"; exit 2; }
        need_dev || exit 1; adb_s ime set "$ID" >/dev/null 2>&1 && green "已设置: $ID" ;;
      *) red "用法: ime list|get|set <id>"; exit 2 ;;
    esac
    ;;
  state)
    if [ -s "$STATE_FILE" ]; then echo "原输入法记录: $(cat "$STATE_FILE")"; else echo "没有记录（未切换过，或已清理）"; fi
    ;;
  -h|--help|"")
    sed -n '2,26p' "$0" 2>/dev/null || true
    ;;
  *)
    red "未知子命令: $SUB"; echo "看帮助: bash scripts/device_input.sh --help"; exit 2 ;;
esac
