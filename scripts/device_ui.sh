#!/usr/bin/env bash
# adb 界面操控前端（混合操控：adb 在线就自动用 adb，不绕开去用纯视觉）
#
# 背景：真机 root 通道可用时，AI 应优先用 adb 操控界面——比纯视觉截图点屏更可靠、可断言、可复现。
# 只有 adb 离线时才提示用户开（bash scripts/device_adb_guard.sh open-hint）。
#
# 用法:
#   bash scripts/device_ui.sh [--serial SERIAL] <子命令> [参数]   # serial 省略时自动发现
#
#   foreground                          当前焦点 Activity（package/activity）
#   launch <pkg|pkg/act>                启动应用 / 指定 Activity
#   dump [--texts] [--limit N]          uiautomator dump，简洁列出 text/bounds/clickable
#   tap <文本正则> | <X> <Y>            按文本找节点点其中心；或直接点坐标
#   swipe <X1> <Y1> <X2> <Y2> [ms]      滑动（默认 300ms）
#   key <back|home|enter|...|键码>       按键（back/home/enter/recents/menu/delete/tab/power/音量/方向键）
#   text <文本> [--switch-ime]          安全打字（转调 device_input.sh，中文输入法下默认拒绝）
#   screen [本地.png]                   截图并拉回（供视觉确认；默认 /tmp/device_ui_screen.png）
#   wait <文本正则> [超时秒]            轮询 dump 等文本出现（默认 10s）
#   apps [过滤] [--user|--system]       包列表（默认全部，过滤为子串/正则）
#
# 说明:
#   - serial 自动发现（ADB_SERIAL/--serial > 5555 在线 > adb devices 首个真机，跳过 emulator-*）；所有 adb 命令都显式 -s。
#   - adb 失败会打印原始输出（stdout+stderr），不静默吞错。
#   - tap / wait 的文本匹配是正则（python re.search），同时匹配 text 和 content-desc。
#   - dump 的 XML 缓存到 /tmp/device_ui_dump.xml，供解析；每次命令重新 dump。
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
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
DUMP_XML="${DUMP_XML:-/tmp/device_ui_dump.xml}"
UI_PARSE_PY="/tmp/device_ui_parse_$$.py"
MAX_LIMIT_DEFAULT=200

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
yel()   { printf '\033[33m%s\033[0m\n' "$*"; }
cya()   { printf '\033[36m%s\033[0m\n' "$*"; }
die()   { red "错误: $*"; exit 1; }
say()   { printf '%s\n' "$*"; }

usage() { sed -n '2,24p' "$0"; }

cleanup() { rm -f "$UI_PARSE_PY" 2>/dev/null; }
trap cleanup EXIT

# ── 全局 --serial（可出现在任意位置）─────────────────────────────────────
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
    usage
    exit 2
fi
SUB="${1:-}"; shift || true
if [ -z "${SERIAL:-}" ]; then SERIAL="$(resolve_serial)"; fi
[ -n "${SERIAL:-}" ] || SERIAL="${SERIAL_DEFAULT}"


# ── 通用 helper ─────────────────────────────────────────────────────────
adb_() { "$ADB_BIN" -s "$SERIAL" "$@"; }

need_adb() {
    command -v "$ADB_BIN" >/dev/null 2>&1 \
        || die "找不到 adb（$ADB_BIN）→ apt-get install -y android-tools-adb"
}

ensure_device() {
    need_adb
    local out st rc
    out=$(timeout 15 "$ADB_BIN" -s "$SERIAL" get-state 2>&1); rc=$?
    st=$(printf '%s' "$out" | tr -d '\r\n')
    if [ "$rc" -ne 0 ] || [ "$st" != "device" ]; then
        red "adb 设备不可用（$SERIAL，状态='${st:-?}', rc=$rc）"
        say "  原始输出: $out"
        say "  → adb 离线：让用户开调试（bash scripts/device_adb_guard.sh open-hint）；"
        say "    恢复后本脚本自动用 adb 操控，不要绕开去用纯视觉。"
        exit 1
    fi
}

# run_adb <描述> <args...>：失败打印原始输出
run_adb() {
    local desc="$1"; shift
    local out rc
    out=$(timeout 60 "$ADB_BIN" -s "$SERIAL" "$@" 2>&1); rc=$?
    if [ "$rc" -ne 0 ]; then
        red "✗ $desc 失败 (rc=$rc)，原始输出："
        printf '%s\n' "$out"
        return "$rc"
    fi
    [ -n "$out" ] && printf '%s\n' "$out"
    return 0
}

# devsh <描述> <shell 命令串>：成功时打印设备端输出
devsh() {
    local desc="$1" cmd="$2"
    local out rc
    out=$(timeout 60 "$ADB_BIN" -s "$SERIAL" shell "$cmd" 2>&1); rc=$?
    if [ "$rc" -ne 0 ]; then
        red "✗ $desc 失败 (rc=$rc)，原始输出："
        printf '%s\n' "$out"
        return "$rc"
    fi
    printf '%s' "$out"
    return 0
}

# ── XML 解析器（uiautomator dump 结果）：list / find / texts ──────────────
ensure_parser() {
    [ -s "$UI_PARSE_PY" ] && return 0
    cat > "$UI_PARSE_PY" <<'PY'
import sys, re
import xml.etree.ElementTree as ET

BOUNDS_RE = re.compile(r'\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]')

def clean(s):
    return re.sub(r'[\t\r\n]+', ' ', (s or '')).strip()

def walk(path):
    root = ET.parse(path).getroot()
    for n in root.iter('node'):
        if n.get('visible-to-user') == 'false':
            continue
        text = clean(n.get('text'))
        desc = clean(n.get('content-desc'))
        click = n.get('clickable') == 'true'
        m = BOUNDS_RE.match(n.get('bounds') or '')
        if not m:
            continue
        x1, y1, x2, y2 = map(int, m.groups())
        yield {'text': text, 'desc': desc, 'clickable': click,
               'bounds': '[%d,%d][%d,%d]' % (x1, y1, x2, y2),
               'cx': (x1 + x2) // 2, 'cy': (y1 + y2) // 2,
               'cls': (n.get('class') or '').split('.')[-1]}

def main():
    if len(sys.argv) < 2:
        print('usage: parser list|find|texts ...', file=sys.stderr); sys.exit(2)
    mode = sys.argv[1]
    if mode == 'list':
        path, texts_only, limit = sys.argv[2], sys.argv[3] == '1', int(sys.argv[4])
        shown = total = 0
        for nd in walk(path):
            has_text = bool(nd['text'] or nd['desc'])
            if texts_only and not has_text:
                continue
            if not texts_only and not (has_text or nd['clickable']):
                continue
            total += 1
            if limit and shown >= limit:
                continue
            shown += 1
            label = nd['text'] or nd['desc']
            tag = 'text=' + repr(label) if label else '(无文字)'
            click = ' clickable' if nd['clickable'] else ''
            print('%d. %s @%s center=(%d,%d)%s' % (shown, tag, nd['bounds'], nd['cx'], nd['cy'], click))
        if limit and total > shown:
            print('… 共 %d 个节点，已截断到 %d（--limit 0 显示全部）' % (total, shown))
        if shown == 0:
            print('（没有匹配的可见节点）')
    elif mode == 'find':
        path, pat, ignore_case = sys.argv[2], sys.argv[3], sys.argv[4] == '1'
        flags = re.IGNORECASE if ignore_case else 0
        try:
            rx = re.compile(pat, flags)
        except re.error as e:
            print('正则无效: %s' % e, file=sys.stderr); sys.exit(3)
        for nd in walk(path):
            for field in (nd['text'], nd['desc']):
                if field and rx.search(field):
                    print('FOUND\t%s\t%s\t%s\t%d\t%d' % (
                        field.replace('\t', ' '), nd['bounds'], 'true' if nd['clickable'] else 'false', nd['cx'], nd['cy']))
                    sys.exit(0)
        sys.exit(1)
    elif mode == 'texts':
        path, limit = sys.argv[2], int(sys.argv[3])
        out = []
        for nd in walk(path):
            if nd['text'] or nd['desc']:
                out.append(nd['text'] or nd['desc'])
            if limit and len(out) >= limit:
                break
        for t in out:
            print('  · ' + t)
    else:
        print('unknown mode: ' + mode, file=sys.stderr); sys.exit(2)

if __name__ == '__main__':
    main()
PY
    [ -s "$UI_PARSE_PY" ] || die "无法生成 XML 解析器: $UI_PARSE_PY"
}

# ui_dump：设备端 dump + pull 到 $DUMP_XML，失败打印 adb 原始输出
ui_dump() {
    ensure_device
    ensure_parser
    local remote="/data/local/tmp/device_ui_dump.xml"
    local out rc
    out=$(timeout 30 "$ADB_BIN" -s "$SERIAL" shell "uiautomator dump '$remote'" 2>&1); rc=$?
    if [ "$rc" -ne 0 ] || ! printf '%s' "$out" | grep -qi 'dumped to'; then
        red "✗ uiautomator dump 失败 (rc=$rc)，原始输出："
        printf '%s\n' "$out"
        say "  → 可能原因：屏幕锁定/无窗口/动画未停；可 screen 截图看看，或重试一次。"
        return 1
    fi
    out=$(timeout 30 "$ADB_BIN" -s "$SERIAL" pull "$remote" "$DUMP_XML" 2>&1); rc=$?
    if [ "$rc" -ne 0 ] || [ ! -s "$DUMP_XML" ]; then
        red "✗ 拉取 UI dump 失败 (rc=$rc)，原始输出："
        printf '%s\n' "$out"
        return 1
    fi
    return 0
}

# ── foreground ───────────────────────────────────────────────────────────
cmd_foreground() {
    ensure_device
    local out line focus=""
    out=$(timeout 30 "$ADB_BIN" -s "$SERIAL" shell \
        "dumpsys window 2>/dev/null | grep -m1 -E 'mCurrentFocus|mFocusedApp'; dumpsys activity activities 2>/dev/null | grep -m1 -E 'topResumedActivity|ResumedActivity'" 2>&1)
    line=$(printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | head -1)
    if [ -z "$line" ]; then
        yel "未能取到前台 Activity（锁屏/黑屏/无窗口？）原始输出："
        printf '%s\n' "$out"
        exit 1
    fi
    focus=$(printf '%s' "$line" | grep -oE '[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+' | head -1)
    if [ -n "$focus" ]; then
        green "当前焦点: $focus"
    else
        green "当前焦点: $line"
    fi
    printf '%s\n' "$line" | sed 's/^/  原始: /'
    return 0
}

# ── launch ───────────────────────────────────────────────────────────────
cmd_launch() {
    local target="${1:-}"
    [ -n "$target" ] || die "用法: device_ui.sh launch <pkg|pkg/act>"
    ensure_device
    case "$target" in
        */*)
            say "启动 Activity: $target"
            run_adb "am start" shell "am start -n '$target'" || exit 1
            ;;
        *)
            local line
            line=$(timeout 30 "$ADB_BIN" -s "$SERIAL" shell \
                "cmd package resolve-activity --brief '$target' 2>/dev/null | tail -n 1" 2>&1 | tr -d '\r')
            if printf '%s' "$line" | grep -q '/'; then
                say "启动: am start -n $line"
                run_adb "am start" shell "am start -n '$line'" || exit 1
            else
                yel "resolve-activity 未拿到（${line:-空}），退回 monkey 启动"
                run_adb "monkey 启动" shell "monkey -p '$target' -c android.intent.category.LAUNCHER 1" || exit 1
            fi
            ;;
    esac
    green "已请求启动: $target"
    return 0
}

# ── dump ─────────────────────────────────────────────────────────────────
cmd_dump() {
    local texts_only=0 limit="$MAX_LIMIT_DEFAULT"
    while [ $# -gt 0 ]; do
        case "$1" in
            --texts) texts_only=1 ;;
            --limit) shift; limit="${1:-$MAX_LIMIT_DEFAULT}" ;;
            --limit=*) limit="${1#*=}" ;;
            *) die "dump 未知参数: $1（用法: dump [--texts] [--limit N]）" ;;
        esac
        shift
    done
    case "$limit" in ''|*[!0-9]*) die "--limit 需要数字（0=全部）" ;; esac
    ui_dump || exit 1
    cya "══════ UI dump（$SERIAL）══════"
    python3 "$UI_PARSE_PY" list "$DUMP_XML" "$texts_only" "$limit" || { red "解析 UI dump 失败"; exit 1; }
    say "  （XML 缓存: $DUMP_XML）"
    return 0
}

# ── tap ──────────────────────────────────────────────────────────────────
cmd_tap() {
    local ic=0
    local -a pos=()
    while [ $# -gt 0 ]; do
        case "$1" in
            -i|--ignore-case) ic=1 ;;
            *) pos+=("$1") ;;
        esac
        shift
    done
    [ "${#pos[@]}" -gt 0 ] || die "用法: device_ui.sh tap <文本正则> | tap <X> <Y>"
    ensure_device
    # 坐标模式
    if [ "${#pos[@]}" -eq 2 ] && [[ "${pos[0]}" =~ ^[0-9]+$ ]] && [[ "${pos[1]}" =~ ^[0-9]+$ ]]; then
        say "点击坐标 (${pos[0]},${pos[1]})"
        run_adb "input tap" shell "input tap ${pos[0]} ${pos[1]}" >/dev/null || exit 1
        green "已点击: (${pos[0]},${pos[1]})"
        return 0
    fi
    local pattern="${pos[0]}"
    ui_dump || exit 1
    local res rc
    res=$(python3 "$UI_PARSE_PY" find "$DUMP_XML" "$pattern" "$ic" 2>&1); rc=$?
    if [ "$rc" -eq 3 ]; then
        red "正则无效: $pattern"; say "$res"; exit 1
    fi
    if [ "$rc" -ne 0 ] || [ -z "$res" ]; then
        red "未找到文本匹配: $pattern"
        say "当前可见文本（供调整正则）："
        python3 "$UI_PARSE_PY" texts "$DUMP_XML" 15 2>/dev/null
        say "  → 可先 dump 看完整节点，或换更宽的正则；也可直接 tap X Y。"
        exit 1
    fi
    local tag mtext mbounds mclick mcx mcy
    IFS=$'\t' read -r tag mtext mbounds mclick mcx mcy <<< "$res"
    green "匹配: \"$mtext\" @$mbounds clickable=$mclick center=($mcx,$mcy)"
    run_adb "input tap" shell "input tap $mcx $mcy" >/dev/null || exit 1
    green "已点击: ($mcx,$mcy)"
    return 0
}

# ── swipe ────────────────────────────────────────────────────────────────
cmd_swipe() {
    [ $# -ge 4 ] || die "用法: device_ui.sh swipe <X1> <Y1> <X2> <Y2> [ms]"
    local x1="$1" y1="$2" x2="$3" y2="$4" ms="${5:-300}"
    local v
    for v in "$x1" "$y1" "$x2" "$y2" "$ms"; do
        [[ "$v" =~ ^[0-9]+$ ]] || die "坐标/时长必须是数字: $v"
    done
    ensure_device
    run_adb "input swipe" shell "input swipe $x1 $y1 $x2 $y2 $ms" >/dev/null || exit 1
    green "已滑动: ($x1,$y1) → ($x2,$y2)，${ms}ms"
    return 0
}

# ── key ──────────────────────────────────────────────────────────────────
cmd_key() {
    local name="${1:-}"
    [ -n "$name" ] || die "用法: device_ui.sh key <back|home|enter|...|键码>"
    local code
    case "$name" in
        back) code=4 ;;
        home) code=3 ;;
        enter|return) code=66 ;;
        menu) code=82 ;;
        recents|appswitch|overview) code=187 ;;
        power) code=26 ;;
        volume_up|volup) code=24 ;;
        volume_down|voldown) code=25 ;;
        delete|del|backspace) code=67 ;;
        tab) code=61 ;;
        space) code=62 ;;
        escape|esc) code=111 ;;
        dpad_up|up) code=19 ;;
        dpad_down|down) code=20 ;;
        dpad_left|left) code=21 ;;
        dpad_right|right) code=22 ;;
        dpad_center|center|ok) code=23 ;;
        camera) code=27 ;;
        notification|notifications) code=83 ;;
        *[!0-9]*) die "未知按键: $name（可用: back home enter menu recents power volume_up/down delete tab space escape up/down/left/right center，或直接给数字键码）" ;;
        *) code="$name" ;;
    esac
    ensure_device
    run_adb "input keyevent" shell "input keyevent $code" >/dev/null || exit 1
    green "已按键: $name (keycode=$code)"
    return 0
}

# ── text（安全打字，转调 device_input.sh）────────────────────────────────
cmd_text() {
    local txt="${1:-}"; shift || true
    [ -n "$txt" ] || die "用法: device_ui.sh text <文本> [--switch-ime] [--dry-run]"
    [ -f "$SCRIPT_DIR/device_input.sh" ] || die "找不到 $SCRIPT_DIR/device_input.sh"
    ensure_device
    ADB_BIN="$ADB_BIN" bash "$SCRIPT_DIR/device_input.sh" --serial "$SERIAL" type "$txt" "$@"
}

# ── screen（截屏并拉回，供视觉确认）─────────────────────────────────────
cmd_screen() {
    local local_png="${1:-/tmp/device_ui_screen.png}"
    ensure_device
    local remote="/data/local/tmp/device_ui_screen.png"
    local out rc
    out=$(timeout 40 "$ADB_BIN" -s "$SERIAL" shell "screencap -p '$remote'" 2>&1); rc=$?
    if [ "$rc" -ne 0 ]; then
        red "✗ screencap 失败 (rc=$rc)，原始输出："; printf '%s\n' "$out"; exit 1
    fi
    out=$(timeout 40 "$ADB_BIN" -s "$SERIAL" pull "$remote" "$local_png" 2>&1); rc=$?
    if [ "$rc" -ne 0 ] || [ ! -s "$local_png" ]; then
        red "✗ 拉取截图失败 (rc=$rc)，原始输出："; printf '%s\n' "$out"; exit 1
    fi
    timeout 20 "$ADB_BIN" -s "$SERIAL" shell "rm -f '$remote'" >/dev/null 2>&1
    green "截图已保存: $local_png（$(du -h "$local_png" | cut -f1)）"
    say "  → 可用视觉确认：read_image $local_png"
    return 0
}

# ── wait（轮询等文本出现）────────────────────────────────────────────────
cmd_wait() {
    local pattern="${1:-}"; local timeout_s="${2:-10}"
    [ -n "$pattern" ] || die "用法: device_ui.sh wait <文本正则> [超时秒]"
    [[ "$timeout_s" =~ ^[0-9]+$ ]] || die "超时秒必须是数字: $timeout_s"
    ensure_device
    ensure_parser
    local start=$SECONDS deadline=$((SECONDS + timeout_s))
    local last_err="" res rc
    say "等待文本出现（最多 ${timeout_s}s）: $pattern"
    while [ "$SECONDS" -lt "$deadline" ]; do
        if ui_dump >/dev/null 2>&1; then
            res=$(python3 "$UI_PARSE_PY" find "$DUMP_XML" "$pattern" 0 2>&1); rc=$?
            if [ "$rc" -eq 0 ] && [ -n "$res" ]; then
                local tag mtext mbounds mclick mcx mcy
                IFS=$'\t' read -r tag mtext mbounds mclick mcx mcy <<< "$res"
                green "已出现（$((SECONDS - start))s）: \"$mtext\" @$mbounds center=($mcx,$mcy)"
                return 0
            fi
        else
            last_err="ui_dump 失败（见上方错误）"
        fi
        sleep 1
    done
    red "等待超时（${timeout_s}s）未出现: $pattern"
    [ -n "$last_err" ] && yel "  最后一次 dump 错误: $last_err"
    if ui_dump >/dev/null 2>&1; then
        say "当前可见文本（供调整正则）："
        python3 "$UI_PARSE_PY" texts "$DUMP_XML" 15 2>/dev/null
    fi
    exit 1
}

# ── apps ─────────────────────────────────────────────────────────────────
cmd_apps() {
    local filter="" mode=""
    while [ $# -gt 0 ]; do
        case "$1" in
            --user|-3) mode="-3" ;;
            --system|-s) mode="-s" ;;
            *) filter="$1" ;;
        esac
        shift
    done
    ensure_device
    local cmd="pm list packages"
    [ -n "$mode" ] && cmd="pm list packages $mode"
    local out rc
    out=$(timeout 40 "$ADB_BIN" -s "$SERIAL" shell "$cmd" 2>&1); rc=$?
    if [ "$rc" -ne 0 ]; then
        red "✗ pm list packages 失败 (rc=$rc)，原始输出："; printf '%s\n' "$out"; exit 1
    fi
    out=$(printf '%s\n' "$out" | sed 's/^package://' | tr -d '\r')
    if [ -n "$filter" ]; then
        out=$(printf '%s\n' "$out" | grep -iE -- "$filter" || true)
    fi
    printf '%s\n' "$out" | grep -v '^[[:space:]]*$' | sort
    local n
    n=$(printf '%s\n' "$out" | grep -vc '^[[:space:]]*$' || true)
    say "── 共 $n 个包${filter:+（过滤: $filter）}"
    return 0
}

# ── 分发 ─────────────────────────────────────────────────────────────────


case "$SUB" in
    foreground) cmd_foreground ;;
    launch)     cmd_launch "$@" ;;
    dump)       cmd_dump "$@" ;;
    tap)        cmd_tap "$@" ;;
    swipe)      cmd_swipe "$@" ;;
    key)        cmd_key "$@" ;;
    text)       cmd_text "$@" ;;
    screen)     cmd_screen "$@" ;;
    wait)       cmd_wait "$@" ;;
    apps)       cmd_apps "$@" ;;
    -h|--help|help|"") usage; exit 0 ;;
    *) red "未知子命令: $SUB"; usage; exit 2 ;;
esac
