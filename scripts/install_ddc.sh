#!/usr/bin/env bash
# install_ddc.sh — 安装 ddc（DEX → Java 反编译器，Rust 实现，MIT）
# 项目: https://github.com/ejfkdev/ddc
# 版本与 SHA256 钉死；下载走 GitHub API（api.github.com），不走 github.com 网页
# 用法: bash scripts/install_ddc.sh            # 安装/升级到钉死版本
#       bash scripts/install_ddc.sh --check    # 只检查是否已安装
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/safe_rm.sh"
VER="0.1.35"
ASSET_ID="700957278"          # aarch64-unknown-linux-musl（静态，手机 ARM64 可用）
SHA256="15cea25b77b4aba1ed128db41892e52de4cc7bea310216b6460c77f0aab32904"
DEST="${DEST:-/usr/local/bin/ddc}"
API="https://api.github.com/repos/ejfkdev/ddc/releases/assets/${ASSET_ID}"

if [ "${1:-}" = "--check" ]; then
  if command -v ddc >/dev/null 2>&1; then
    echo "ddc 已安装: $(ddc --version 2>/dev/null | head -1)"
  else
    echo "ddc 未安装"
  fi
  exit 0
fi

TMP=$(mktemp -d); trap 'safe_rm_tree "$TMP" /tmp' EXIT
echo "== 下载 ddc ${VER}（aarch64-musl）=="
if command -v curl >/dev/null 2>&1; then
  curl -sSL --max-time 180 -H 'Accept: application/octet-stream' "$API" -o "$TMP/ddc" || { echo "下载失败：api.github.com 不可达，可手动到项目 Releases 下载 aarch64-unknown-linux-musl"; exit 1; }
else
  wget -q --timeout=180 --header='Accept: application/octet-stream' "$API" -O "$TMP/ddc" || { echo "下载失败（无 curl/wget）"; exit 1; }
fi

GOT=$(sha256sum "$TMP/ddc" | awk '{print $1}')
if [ "$GOT" != "$SHA256" ]; then
  echo "✗ SHA256 不匹配"; echo "  期望: $SHA256"; echo "  实际: $GOT"; exit 1
fi
chmod +x "$TMP/ddc"
if [ -w "$(dirname "$DEST")" ]; then
  mv "$TMP/ddc" "$DEST"
else
  sudo mv "$TMP/ddc" "$DEST" 2>/dev/null || { echo "安装到 $DEST 失败（需要写权限）"; exit 1; }
fi
echo "✓ 已安装: $DEST"
"$DEST" --version | head -1
echo ""
echo "用法:"
echo "  ddc app.apk out/            # 反编译 DEX → Java"
echo "  ddc serve --addr 127.0.0.1:8080  # HTTP REST + OpenAPI"
echo "  ddc mcp stdio               # MCP 工具服务"
