#!/usr/bin/env python3
"""按需工具管理器（默认不下载任何东西）。

设计目标：
- 先检测、再给出清单、再由用户选择；没有 --yes 绝不安装。
- 区分 third_party / self；thirdparty 模式默认禁用自研同名工具。
- 注册表只放元数据与下载/安装入口，不把第三方二进制打进技能包。

用法（示例）：
  python3 scripts/tool_manager.py status
  python3 scripts/tool_manager.py plan --task decode
  python3 scripts/tool_manager.py plan --profile minimal
  python3 scripts/tool_manager.py install --profile minimal --yes
  python3 scripts/tool_manager.py install --ids jadx,apktool --yes
  python3 scripts/tool_manager.py mode thirdparty
  python3 scripts/tool_manager.py resolve --capability dynamic
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "tools" / "registry.json"
DEFAULT_STATE = Path.home() / ".dsh" / "apk-reverse" / "tool-state.json"


def load_registry() -> dict[str, Any]:
    with REGISTRY.open(encoding="utf-8") as f:
        return json.load(f)


def load_state(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"mode": "unset", "first_run_completed": False, "installed": []}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def detect(tool: dict[str, Any]) -> dict[str, Any]:
    d = tool.get("detect") or {}
    if "command" in d:
        cmd = d["command"]
        found = shutil.which(cmd)
        version = ""
        if found and d.get("version"):
            try:
                p = subprocess.run(d["version"], capture_output=True, text=True, timeout=5)
                version = (p.stdout or p.stderr).strip().splitlines()[0] if (p.stdout or p.stderr) else ""
            except Exception:
                version = ""
        return {"installed": bool(found), "where": found or "", "version": version}
    if "python_module" in d:
        mod = d["python_module"]
        spec = importlib.util.find_spec(mod)
        return {"installed": spec is not None, "where": "python module" if spec else "", "version": ""}
    if "path" in d:
        p = Path(d["path"])
        if not p.is_absolute():
            p = ROOT / p
        return {"installed": p.exists(), "where": str(p) if p.exists() else "", "version": ""}
    return {"installed": False, "where": "", "version": ""}


def tool_rows(reg: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for t in reg.get("tools", []):
        d = detect(t)
        rows.append({**t, **d})
    return rows


def selected_tools(reg: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    tools = reg.get("tools", [])
    by_id = {t["id"]: t for t in tools}
    if args.ids:
        return [by_id[x.strip()] for x in args.ids.split(",") if x.strip() in by_id]
    if args.task:
        return [t for t in tools if args.task in (t.get("required_for") or []) or args.task in (t.get("recommended_for") or [])]
    profile = args.profile or reg.get("policy", {}).get("default_profile", "minimal")
    ids = (reg.get("profiles") or {}).get(profile, [])
    return [by_id[x] for x in ids if x in by_id]


def type_label(r: dict[str, Any]) -> str:
    return "自研" if r.get("type") == "self" else "第三方"


def print_table(rows: list[dict[str, Any]], state: dict[str, Any]) -> None:
    mode = state.get("mode", "unset")
    mode_text = "未设置（建议 thirdparty）" if mode == "unset" else mode
    print(f"模式: {mode_text}")
    print("默认启用第三方成熟工具（自研工具还未完善，thirdparty 模式下不调用自研同名工具）。")
    print(f"{'ID':<22} {'类型':<6} {'状态':<6} {'大小':>7}  {'许可证':<26} 说明")
    print("-" * 120)
    for r in rows:
        st = "已装" if r.get("installed") else "缺"
        size = f"{r.get('size_mb', 0)}MB"
        note = r.get("name", "")
        if r.get("type") == "self":
            note += f"（{r.get('completeness','experimental')}）"
        print(f"{r['id']:<22} {type_label(r):<6} {st:<6} {size:>7}  {r.get('license',''):<26} {note}")
    print("-" * 120)
    print("只装你选中的；没有 --yes 不会下载。第三方工具不打包在本技能里，只保存来源/许可证/校验入口。")


def print_recommendation(rows: list[dict[str, Any]], task: str) -> None:
    third = [r for r in rows if r.get("type") != "self"]
    self_tools = [r for r in rows if r.get("type") == "self"]
    print(f"\n本次 APK 任务「{task or '通用'}」需要的工具：")
    if third:
        print("  推荐第三方成熟工具：" + "、".join(f"{r['id']}（{r.get('size_mb',0)}MB，{r.get('license','')}）" + ("[组安装]" if r.get("install_group") else "") for r in third))
    if self_tools:
        print("  自研工具（未完善，默认不启用）：" + "、".join(r["id"] for r in self_tools))
    print("  建议：默认用第三方成熟工具；自研工具想试再切 `mode self` 或 `mode hybrid`。")


def cmd_status(args: argparse.Namespace) -> int:
    reg = load_registry()
    state = load_state(args.state)
    rows = tool_rows(reg)
    if args.json:
        print(json.dumps({"mode": state.get("mode"), "tools": rows}, ensure_ascii=False, indent=2))
        return 0
    print_table(rows, state)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    reg = load_registry()
    state = load_state(args.state)
    rows = [r for r in tool_rows(reg) if any(r["id"] == t["id"] for t in selected_tools(reg, args))]
    missing = [r for r in rows if not r.get("installed")]
    total = sum(int(r.get("size_mb", 0)) for r in missing if r.get("type") != "self")
    if args.json:
        print(json.dumps({"tools": rows, "missing": missing, "estimated_mb": total, "mode": state.get("mode")}, ensure_ascii=False, indent=2))
        return 0
    print_table(rows, state)
    print_recommendation(rows, args.task or args.profile or "通用")
    print(f"\n本次缺失: {len(missing)} 项；预计下载约 {total} MB。")
    grouped = [r for r in missing if r.get("install_group")]
    if grouped:
        print("其中这些是组安装（默认不执行，避免顺带装同组其它工具）：" + "、".join(f"{r['id']}[{r.get('install_group')}]" for r in grouped))
        print("如接受同组安装，执行时加 --allow-group；或只选非组工具。")
    if any(r.get("type") == "self" and not r.get("installed") for r in rows):
        print("注意：自研工具缺失时不应从网络下载；它们是本技能脚本，检查安装目录是否完整。")
    print("下一步：把清单给用户看，让用户选「只装本次必需 / 推荐集 / 整套 / 自己挑」；确认后再加 --yes 执行。")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    reg = load_registry()
    state = load_state(args.state)
    chosen = selected_tools(reg, args)
    if not chosen:
        print("没有选中的工具。用 --task / --profile / --ids 指定。", file=sys.stderr)
        return 2
    rows = []
    for t in chosen:
        d = detect(t)
        rows.append({**t, **d})
    missing = [r for r in rows if not r.get("installed")]
    third = [r for r in missing if r.get("type") != "self" and r.get("install_cmd")]
    grouped = [r for r in third if r.get("install_group")]
    if grouped and not args.allow_group:
        third = [r for r in third if not r.get("install_group")]
        print("\n以下属于组安装，默认不执行（避免顺带装同组其它工具）：" + ", ".join(f"{r['id']}[{r.get('install_group')}]" for r in grouped))
        print("如接受同组安装，加 --allow-group；或只选非组工具。")
    self_missing = [r for r in missing if r.get("type") == "self"]
    if args.json:
        print(json.dumps({"chosen": rows, "missing": missing, "will_run": third}, ensure_ascii=False, indent=2))
        if not args.yes:
            return 3
    if not missing:
        print("选中的工具都已安装，无需下载。")
        return 0
    print_table(rows, state)
    if self_missing:
        print("\n以下自研工具缺失（不会联网下载）：" + ", ".join(r["id"] for r in self_missing))
    if not third:
        if not args.yes:
            print("\n没有可执行的第三方下载项；当前未下载任何东西。")
            return 3
        print("没有可执行的第三方下载项；选中项仍未安装。")
        return 4
    print_recommendation(rows, args.task or args.profile or "通用")
    print("\n将执行（只针对选中的缺失项）：")
    for r in third:
        print(f"  - {r['id']} ({r.get('size_mb',0)}MB, {r.get('license','')}): {r['install_cmd']}")
    if not args.yes:
        print("\n需要用户确认后再执行；确认后加 --yes。当前未下载任何东西。")
        return 3
    failed = []
    for r in third:
        print(f"\n>>> 安装 {r['id']} ...")
        p = subprocess.run(r["install_cmd"], shell=True, cwd=ROOT)
        if p.returncode != 0:
            failed.append(r["id"])
    state.setdefault("installed", [])
    for r in third:
        if r["id"] not in state["installed"] and detect(r).get("installed"):
            state["installed"].append(r["id"])
    save_state(args.state, state)
    if failed:
        print("\n失败项: " + ", ".join(failed) + "（可重试；未完成前不要宣称已装好）")
        return 1
    print("\n选中项安装完成；用 `tool_manager.py status` 复核。")
    return 0


def cmd_mode(args: argparse.Namespace) -> int:
    if args.mode not in {"thirdparty", "self", "hybrid"}:
        print("mode 必须是 thirdparty / self / hybrid", file=sys.stderr)
        return 2
    state = load_state(args.state)
    state["mode"] = args.mode
    state["first_run_completed"] = True
    save_state(args.state, state)
    print(f"已切换模式: {args.mode}")
    if args.mode == "thirdparty":
        print("第三方模式：优先用成熟开源工具；自研同名工具（如 hook_gen）默认不调用，避免冲突。")
    elif args.mode == "self":
        print("自研模式：使用本技能脚本；它们是实验性的，失败时再切 thirdparty。")
    else:
        print("混合模式：稳定的自研工具（如 build_sign）优先，实验性的用第三方。")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    reg = load_registry()
    state = load_state(args.state)
    mode = state.get("mode", "unset")
    rows = [r for r in tool_rows(reg) if args.capability in (r.get("capability") or [])]
    if mode == "self":
        rows.sort(key=lambda r: 0 if r.get("type") == "self" else 1)
    elif mode == "hybrid":
        rows.sort(key=lambda r: (0 if r.get("type") == "self" and r.get("completeness") == "stable" else 1 if r.get("type") == "self" else 2))
    else:
        rows.sort(key=lambda r: 0 if r.get("type") != "self" else 1)
    if not rows:
        print(f"没有能力 {args.capability} 的工具", file=sys.stderr)
        return 2
    r = rows[0]
    print(f"mode={mode} capability={args.capability} -> {r['id']} ({r.get('type')})")
    if r.get("type") == "self" and mode == "thirdparty":
        print("注意：当前 thirdparty 模式，不建议调用自研工具；请切换到 self/hybrid。")
    print(f"source: {r.get('source','')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="apk-reverse 按需工具管理器")
    p.add_argument("--state", type=Path, default=DEFAULT_STATE, help="状态文件路径")
    sub = p.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("status", help="检测所有工具")
    st.add_argument("--json", action="store_true")
    st.set_defaults(func=cmd_status)

    pl = sub.add_parser("plan", help="列出某任务/配置需要什么（不下载）")
    pl.add_argument("--task", default="")
    pl.add_argument("--profile", choices=["minimal", "recommended", "full"], default="")
    pl.add_argument("--ids", default="")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_plan)

    ins = sub.add_parser("install", help="只装选中的缺失工具（需 --yes）")
    ins.add_argument("--task", default="")
    ins.add_argument("--profile", choices=["minimal", "recommended", "full"], default="")
    ins.add_argument("--ids", default="")
    ins.add_argument("--yes", action="store_true", help="用户已确认；没有它不会下载")
    ins.add_argument("--allow-group", action="store_true", help="允许组安装（会连带同组工具，仍只执行选中项对应的组）")
    ins.add_argument("--json", action="store_true")
    ins.set_defaults(func=cmd_install)

    mo = sub.add_parser("mode", help="切换 thirdparty / self / hybrid")
    mo.add_argument("mode")
    mo.set_defaults(func=cmd_mode)

    re_ = sub.add_parser("resolve", help="按能力选择工具（不下载）")
    re_.add_argument("--capability", required=True)
    re_.set_defaults(func=cmd_resolve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
