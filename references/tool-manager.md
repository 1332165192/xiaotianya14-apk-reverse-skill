# 工具链：按需下载 / 第三方 vs 自研

> 目标：技能包**不打包第三方二进制**，只在需要时下载；先问用户，再按选择安装；第三方成熟工具与内部自研工具**不混用**。

## 1. 默认策略（用户已确认）

| 项 | 默认 |
|---|---|
| 模式 | `thirdparty`（默认；自研未完善，先启用第三方成熟工具） |
| 首次安装 | `minimal`（只装本次必需） |
| 下载 | 必须用户确认；没有 `--yes` 不下载 |
| 自研工具 | 实验性；thirdparty 模式下不调用同名自研工具 |
| 第三方工具 | 不打包、不静默下载、保留来源/许可证/校验 |

## 2. 首次使用流程（AI 必须按这个顺序）

1. 读注册表：`python3 scripts/tool_manager.py plan --task <任务>`
2. 把清单给用户看：缺什么、多大、许可证、哪些是第三方/自研。
3. 问用户三件事（先说默认推荐）：
   - **本次 APK 任务需要这些工具，推荐这几款**；默认用**第三方成熟工具**（自研未完善），问用户是否改用内部自研（实验性）？
   - 只装**本次必需** / **推荐集** / **整套** / **自己挑**？
   - 是否同意下载（需要联网、占空间）。
4. 用户确认后才执行：
   ```bash
   python3 scripts/tool_manager.py install --task decode --yes
   # 或
   python3 scripts/tool_manager.py install --ids jadx,apktool --yes
   ```
5. 设置模式：
   ```bash
   python3 scripts/tool_manager.py mode thirdparty   # 默认
   python3 scripts/tool_manager.py mode self
   python3 scripts/tool_manager.py mode hybrid
   ```
6. 复核：`python3 scripts/tool_manager.py status`。

**组安装**：`cfr` / `smali` / `baksmali` / `dex2jar` / `bundletool` / `mitmproxy` 目前仍复用 `install_tools.sh` 的组参数；默认跳过，需 `--allow-group`。单工具（jadx/apktool/aapt2/apksigner/zipalign/adb/frida）走 `--only <id>`。

**禁止**：不先问就 `install_tools.sh` 全装；不把 `--profile full` 当默认；不在用户不知情时下载。

## 3. 三种模式

| 模式 | 行为 | 适用 |
|---|---|---|
| `thirdparty` | 用 jadx/apktool/Frida 等成熟工具；自研同名工具不调用 | 想要稳定、少踩坑 |
| `self` | 用本技能自研脚本；明确标实验性；失败可切回 | 想测试/改进自研工具 |
| `hybrid` | 稳定的自研工具（如 `build_sign.sh`）优先；实验性的用第三方 | 折中 |

切换只写本地状态（`~/.dsh/apk-reverse/tool-state.json`），不改技能包文件，不删任何工具。

## 4. 注册表 `tools/registry.json`

每个工具只存元数据，不存二进制：

```json
{
  "id": "jadx",
  "type": "third_party",
  "capability": ["decompile", "analyze"],
  "license": "Apache-2.0",
  "size_mb": 35,
  "tasks": ["decode", "analyze"],
  "detect": { "command": "jadx", "version": ["jadx", "--version"] },
  "install_cmd": "bash scripts/install_tools.sh --jadx",
  "source": "https://github.com/skylot/jadx",
  "conflicts": []
}
```

字段：
- `type`：`third_party` 或 `self`
- `capability`：能力标签（decompile / dynamic / network / sign / dump / device…）
- `license` / `size_mb` / `source`：给用户看，避免侵权与空间浪费
- `detect`：命令、Python 模块、或仓库内路径
- `install_cmd`：只有用户确认后才执行
- `completeness`（自研）：`stable` / `experimental`
- `conflicts`：同名/同能力冲突项

## 5. 许可证规则

- **MIT / Apache-2.0**：可以作为第三方工具使用；保留版权与 NOTICE（如分发）。
- **BSD-3-Clause**：可用，保留版权声明。
- **GPL / AGPL**：不打包、不混入；只作为用户自行安装的外部工具，避免传染。
- **无 LICENSE / 许可不明**：不打包、不默认下载；只学思路。
- 本技能自身是 **MIT**；从第三方借鉴的接口/思路在 `NOTICE` / `references/third-party-provenance.md` 说明。

## 6. 自研工具优先级

1. `dex_dump`（内存 DEX / 脱壳）——手机端替代少，优先补强
2. `hook_gen`（生成 + 自动注入）
3. `build_sign` / `decode` 封装（稳定）
4. `scan_premium` / `find_api_calls` / `manifest_summary`
5. `call_graph` / `find_framework_apis`
6. `il2cpp_meta`（内部版）

成熟第三方（jadx/apktool/Frida/mitmproxy）不重复造轮子，优先第三方。

## 6.1 “不推荐自研” ≠ “禁用自研”

`thirdparty` 模式只在**有同类第三方工具**时优先第三方；如果某个能力第三方根本没有（例如手机内存 DEX dump），`resolve` 会回退到自研工具，并明确打印：

```text
第三方没有同类工具 → 回退自研（实验性）
```

所以不是“永远不能用自研”，而是：

- 有成熟第三方 → 先用第三方，避免自研未完善导致误判；
- 第三方没有 → 用自研，但标实验性，先小样本/dry-run；
- 用户坚持自研 → `mode self` 或 `mode hybrid`。

## 7. 从 REA 吸收的原则（不复制代码）

REA（Reverse Engineer Anything，MIT）的做法值得借鉴：

- **适配层**：agent 指令与工具实现分离；工具负责“怎么分析”，skill 负责“先做什么、怎么问用户”。
- **不打包引擎**：使用用户已有的 Ghidra/Hopper/IDA/JADX，降低体积与许可证风险。
- **本地分析 + 证据/限制**：结论要带证据与局限，不把“看起来像”说成“确定”。
- **可选安装**：setup 只注册，不静默装大工具。
- **按能力路由**：按“要分析二进制 / 应用 / 网页”选择工具，而不是固定一条命令链。

对应到本项目：`registry.json` + `tool_manager.py` 就是“适配层”；`SKILL.md` 只做路由与询问；不把第三方二进制放进包。

## 8. 风险提示（同步到 README / 主页）

使用本技能可能对手机有风险，部分功能需要 **root / ADB / Shizuku** 等高风险权限；请先备份，勿在主力机/生产环境使用。第三方工具由各自作者提供，请自行确认来源与许可证；本技能不提供盗版、破解付费、绕过服务器校验或分发改装包。
