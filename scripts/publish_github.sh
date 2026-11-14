#!/usr/bin/env bash
# publish_github.sh — 手机版一键发布到 GitHub（git-only，无需 gh CLI）
#
# 功能：提交 → 建仓（可选，走 API）→ push → 打 tag → 建 Release（可选，附件需网页补）
# 安全：Token 只经 GIT_ASKPASS 传给 git，不写入 remote、不写进仓库、不回显；
#       绝不 force-push、不删远程。
#
# 用法:
#   bash scripts/publish_github.sh --repo https://github.com/<owner>/<repo>.git
#   bash scripts/publish_github.sh --create-repo --name apk-reverse
#   bash scripts/publish_github.sh --dry-run
#
# Token（任选其一）:
#   export GITHUB_TOKEN=...
#   或写入文件（0600）: ~/.config/dsh-go/github-token
set -uo pipefail

DIR="."; REPO=""; NAME=""; CREATE=0; PRIVATE=0; DRY=0
TAG=""; RELEASE=0; USER_OVERRIDE=""; BRANCH="main"

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="${2:?}"; shift 2 ;;
    --repo) REPO="${2:?}"; shift 2 ;;
    --name) NAME="${2:?}"; shift 2 ;;
    --branch) BRANCH="${2:?}"; shift 2 ;;
    --tag) TAG="${2:?}"; shift 2 ;;
    --release) RELEASE=1; shift ;;
    --create-repo) CREATE=1; shift ;;
    --private) PRIVATE=1; shift ;;
    --user) USER_OVERRIDE="${2:?}"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "未知参数: $1"; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$*"; }
bad()  { printf '\033[31m✗ %s\033[0m\n' "$*"; }
warn() { printf '\033[33m! %s\033[0m\n' "$*"; }
run()  { if [ "$DRY" = 1 ]; then echo "  [dry-run] $*"; else "$@"; fi; }

cd "$DIR" || { bad "目录不存在: $DIR"; exit 1; }
[ -d .git ] || { bad "不是 git 仓库: $DIR（先 git init）"; exit 1; }
git config --global --add safe.directory "$PWD" 2>/dev/null || true

TOKEN="${GITHUB_TOKEN:-}"
if [ -z "$TOKEN" ] && [ -f "$HOME/.config/dsh-go/github-token" ]; then
  TOKEN=$(tr -d ' \r\n' < "$HOME/.config/dsh-go/github-token")
fi
[ -n "$TOKEN" ] || [ "$DRY" = 1 ] || {
  bad "缺 GITHUB_TOKEN"
  cat <<'TIP'
  设置方式（二选一）：
    export GITHUB_TOKEN=ghp_xxx
    或：mkdir -p ~/.config/dsh-go && printf '%s' 'ghp_xxx' > ~/.config/dsh-go/github-token
        chmod 600 ~/.config/dsh-go/github-token
  Token 权限：经典 token 勾 repo；fine-grained 勾 Contents: Read and write（建仓还需 Administration: Read and write）。
TIP
  exit 1
}

API="https://api.github.com"
OWNER=""
if [ -n "$REPO" ]; then
  OWNER=$(printf '%s' "$REPO" | sed -E 's#^.*github\.com[:/]([^/]+)/[^/]+$#\1#')
fi
if [ -z "$OWNER" ] && [ -n "$USER_OVERRIDE" ]; then OWNER="$USER_OVERRIDE"; fi
if [ -z "$OWNER" ] && [ -n "$TOKEN" ] && [ "$DRY" = 0 ]; then
  OWNER=$(curl -fsSL --max-time 20 -H "Authorization: Bearer $TOKEN" "$API/user" 2>/dev/null \
    | python3 -c 'import json,sys;print(json.load(sys.stdin).get("login",""))' 2>/dev/null || true)
fi
[ -n "$OWNER" ] || [ "$DRY" = 1 ] || { bad "无法确定 GitHub 用户名，用 --repo 或 --user 指定"; exit 1; }

say "== 1/5 提交 =="
if [ -z "$(git config user.name)" ]; then
  run git config user.name "${OWNER:-apk-reverse}"
fi
if [ -z "$(git config user.email)" ]; then
  run git config user.email "${OWNER:-apk-reverse}@users.noreply.github.com"
fi
run git add -A
if [ "$DRY" = 1 ]; then echo "  [dry-run] git commit -m 'publish'（如有改动）"; else
  if ! git diff --cached --quiet; then git commit -m "publish $(date +%F)"; ok "已提交"; else warn "没有新改动，跳过提交"; fi
fi
run git branch -M "$BRANCH"

say "== 2/5 远程 =="
if ! git remote get-url origin >/dev/null 2>&1; then
  if [ -n "$REPO" ]; then
    run git remote add origin "$REPO"
    ok "已设置 origin: $REPO"
  elif [ "$CREATE" = 1 ]; then
    REPO_NAME="${NAME:-$(basename "$PWD")}"
    [ "$DRY" = 1 ] || {
      PRIV=$([ "$PRIVATE" = 1 ] && echo true || echo false)
      code=$(curl -sS -o /tmp/.gh_create.json -w '%{http_code}' --max-time 30 \
        -X POST -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
        "$API/user/repos" -d "{\"name\":\"$REPO_NAME\",\"private\":$PRIV,\"auto_init\":false}")
      if [ "$code" = "201" ]; then ok "已创建仓库 $OWNER/$REPO_NAME"; else
        bad "建仓失败（HTTP $code）"; sed -n '1,5p' /tmp/.gh_create.json 2>/dev/null; exit 1
      fi
    }
    REPO="https://github.com/$OWNER/$REPO_NAME.git"
    run git remote add origin "$REPO"
  else
    bad "没有 origin：用 --repo <url> 或 --create-repo"
    exit 1
  fi
else
  REPO=$(git remote get-url origin)
  warn "已有 origin: $REPO"
fi

say "== 3/5 推送 =="
ASKPASS=$(mktemp); trap 'rm -f "$ASKPASS"' EXIT
cat > "$ASKPASS" <<AP
#!/bin/sh
case "\$1" in
  *Username*) printf '%s\n' "x-access-token" ;;
  *)          printf '%s\n' "\${GITHUB_TOKEN:-}" ;;
esac
AP
chmod 700 "$ASKPASS"
if [ "$DRY" = 1 ]; then
  echo "  [dry-run] GIT_ASKPASS=<token> git push -u origin $BRANCH"
else
  if GIT_ASKPASS="$ASKPASS" GITHUB_TOKEN="$TOKEN" git push -u origin "$BRANCH"; then ok "推送成功"; else bad "推送失败（检查 token/仓库/网络）"; exit 1; fi
fi

if [ -n "$TAG" ]; then
  say "== 4/5 标签 =="
  run git tag "$TAG" 2>/dev/null || warn "本地标签 $TAG 已存在，保留原标签"
  if [ "$DRY" = 1 ]; then echo "  [dry-run] git push origin $TAG"; else
    GIT_ASKPASS="$ASKPASS" GITHUB_TOKEN="$TOKEN" git push origin "$TAG" && ok "标签 $TAG 已推送" || warn "标签推送失败（可能已存在）"
  fi
else
  say "== 4/5 标签 =="; say "  ！（未指定 --tag，跳过）"
fi

if [ "$RELEASE" = 1 ] && [ -n "$TAG" ]; then
  say "== 5/5 Release =="
  RJSON=$(python3 -c 'import json,sys;print(json.dumps({"tag_name":sys.argv[1],"name":sys.argv[1],"body":"release "+sys.argv[1]}))' "$TAG")
  if [ "$DRY" = 1 ]; then echo "  [dry-run] POST $API/repos/$OWNER/<repo>/releases"; else
    RCODE=$(curl -sS -o /tmp/.gh_rel.json -w '%{http_code}' --max-time 30 \
      -X POST -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
      "$API/repos/$OWNER/$(basename "$REPO" .git)/releases" -d "$RJSON")
    if [ "$RCODE" = "201" ]; then ok "Release 已创建"; else warn "Release 创建失败（HTTP $RCODE），可网页手动创建"; fi
  fi
  say "  ！附件（zip/.sha256）请到网页 Release 上传（上传域名在部分网络不可达）"
else
  say "== 5/5 Release =="; say "  ！（未指定 --release --tag，跳过）"
fi

say ""
ok "完成。仓库: ${REPO:-$PWD}"
[ -n "$TOKEN" ] && say "（token 未写入仓库/remote，可随时在 GitHub 撤销）"
