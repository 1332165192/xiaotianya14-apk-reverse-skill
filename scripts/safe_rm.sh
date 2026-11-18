#!/usr/bin/env bash
# 安全删除辅助：拒绝危险路径，用 find -delete 代替 rm -rf，避免误删系统目录。
# 用法：source scripts/safe_rm.sh 后调用 safe_rm_tree <目录>
#   safe_rm_tree 会拒绝：空路径、"/"、"."、".."、"$HOME"、含 ".." 的路径；
#   可选第二个参数做前缀限制：safe_rm_tree "$TMP" /tmp
safe_rm_tree() {
    local target="${1:-}" prefix="${2:-}"
    case "${target:-}" in
        ""|"/"|"."|"..")
            printf 'safe_rm_tree: 拒绝删除危险路径: %s\n' "${target:-<空>}" >&2
            return 1
            ;;
    esac
    case "$target" in
        *..*)
            printf 'safe_rm_tree: 拒绝删除含 .. 的路径: %s\n' "$target" >&2
            return 1
            ;;
    esac
    if [ -n "${HOME:-}" ] && [ "$target" = "$HOME" ]; then
        printf 'safe_rm_tree: 拒绝删除 HOME: %s\n' "$target" >&2
        return 1
    fi
    if [ -n "$prefix" ]; then
        case "$target" in
            "$prefix"/*) : ;;
            *)
                printf 'safe_rm_tree: 只允许删除 %s 下的路径: %s\n' "$prefix" "$target" >&2
                return 1
                ;;
        esac
    fi
    [ -e "$target" ] || return 0
    if [ ! -d "$target" ]; then
        rm -f -- "$target" 2>/dev/null || return 1
        return 0
    fi
    find "$target" -mindepth 1 -delete 2>/dev/null
    rmdir "$target" 2>/dev/null
    return 0
}
