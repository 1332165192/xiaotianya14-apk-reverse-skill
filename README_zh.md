<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/avatar-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/avatar-light.svg">
    <img src="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/avatar-dark.svg" alt="apk-reverse" width="140" />
  </picture>
</p>

<h1 align="center">apk-reverse · 手机版逆向skill</h1>
<h3 align="center">Android APK 逆向研究技能包</h3>

<p align="center"><em style="font-family: Georgia, serif; font-size: 1.15em; color: #888;">拆开它、看懂它、改对它、再证明它能跑。</em></p>

<p align="center">
  <a href="https://github.com/xiaotianya14/apk-reverse-skill/releases"><img src="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/badges/version-0.6.3.svg" alt="version"></a>
  <a href="LICENSE"><img src="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/badges/license.svg" alt="license"></a>
  <img src="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/badges/android.svg" alt="android">
  <a href="https://github.com/xiaotianya14/apk-reverse-skill/actions"><img src="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/badges/ci.svg" alt="CI"></a>
</p>

<p align="center">
  <a href="#关于">关于</a> ·
  <a href="#能力">能力</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#使用">使用</a> ·
  <a href="#仓库结构">仓库结构</a> ·
  <a href="#文档">文档</a> ·
  <a href="#校验">校验</a> ·
  <a href="#贡献">贡献</a> ·
  <a href="#许可">许可</a>
</p>

<p align="center">
  🌐 <a href="README.md">English</a> · <strong>中文</strong>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/banner-dark-v3.webp">
    <source media="(prefers-color-scheme: light)" srcset="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/banner-light-v3.webp">
    <img src="https://cdn.jsdelivr.net/gh/xiaotianya14/apk-reverse-skill@main/assets/banner-dark-v3.webp" alt="apk-reverse banner" width="100%">
  </picture>
</p>

<br/>

<a id="about"></a>

## 关于

> **如果你是 AI Agent**，先打开 [`SKILL.md`](SKILL.md)，按里面的路由、授权边界与补丁规则执行。

一个在 Android 手机上跑的 APK 逆向作业规范：把“我有个 APK”变成一套可重复的流程，而不是瞎试命令。

```text
APK
  → toolcheck / install_tools        （工具链齐不齐）
  → decode + manifest_summary        （解包、反编译、摸组件）
  → scan_premium / find_api_calls    （找逻辑、找广告）
  → patch smali / manifest / .so     （改最小的那一处）
  → build_sign                       （重打包、对齐、签名）
  → device verify                    （装上、打开、看行为）
  → field-journal                    （记下 根因 → 修法）
```

**为什么要做这个**

- APK 任务和普通写代码不是同一套打法
- jadx / apktool / Frida / IDA 装起来容易，用错也容易
- 纯手机环境（proot Ubuntu on ARM64）有自己的坑
- “重打包后为什么闪退”这类问题不该被反复踩

### 一眼看完

| 版本 | 脚本 | 专题文档 | CI | 许可 |
|---:|---:|---:|---|---|
| v0.6.3 | 32 + 12 Frida | 24 | GitHub Actions | MIT |

<p align="center">
  ⭐ <a href="https://github.com/xiaotianya14/apk-reverse-skill/stargazers">Star this repo</a> ·
  🍴 <a href="https://github.com/xiaotianya14/apk-reverse-skill/forks">Fork</a> ·
  🐛 <a href="https://github.com/xiaotianya14/apk-reverse-skill/issues">Report an issue</a>
</p>

<p align="right">(<a href="#关于">返回顶部</a>)</p>

<a id="能力"></a>

## 能力

| 方向 | 具体做什么 |
|---|---|
| 反编译 | jadx 源码、apktool 资源与 smali、smali3、CFR |
| 组件与广告 | SDK 特征、清单 / 布局 / 资源定位 |
| 逻辑分析 | 付费与权益判定、数值逻辑、存档（SharedPreferences / SQLite） |
| 补丁 | smali 定点补丁、静态字段、原生 `.so` 指令补丁 |
| 保护分析 | 加固壳、签名校验、完整性校验 |
| 动态与抓包 | Frida、objection、mitmproxy、证书固定适配 |
| 交付 | 重打包、对齐、签名、真机安装验证 |

<p align="right">(<a href="#关于">返回顶部</a>)</p>

<a id="install-dshgo"></a>

## 安装到 DSH Go / DeepSeek Harness

| 方式 | 操作 |
|---|---|
| **DSH Go 商城**（推荐） | App → 插件市场 → 搜 `apk-reverse` → 安装；重启内核生效 |
| **插件命令** | `dsh plugin --profile web add github:xiaotianya14/apk-reverse-skill` |
| **手动包** | 下载 Release 的 zip → 解压 → `dsh plugin --profile web add <目录>` |

- 技能名：`apk-reverse`；装好后在对话里说「逆向这个 APK / 分析广告组件 / 看付费逻辑」即可触发。
- 手机端不需要 adb：DSH Go 自带手机操控工具（`screen`/`tap`/`type`/`open`/`key`/`handoff`）可做真机验证。
- 电脑端（Linux/WSL）同样可装，命令与工具链一致。
- **手动包要解压**：`dsh plugin add` 只接受「本地目录 / npm 包名 / github:owner/repo」，不收 zip；所以离线包要先解压成文件夹，再 `dsh plugin --profile web add <那个文件夹>`。商城安装与插件命令都不用解压。

<p align="right">(<a href="#关于">返回顶部</a>)</p>

<a id="快速开始"></a>

## 快速开始

```sh
SK=/path/to/apk-reverse

bash $SK/scripts/toolcheck.sh                 # 工具自检
bash $SK/scripts/install_tools.sh             # 自动安装缺失工具

bash $SK/scripts/decode.sh app.apk --out ./work      # 解码
python3 $SK/scripts/manifest_summary.py ./work       # 清单摘要
python3 $SK/scripts/scan_premium.py ./work           # 付费/权益候选
python3 $SK/scripts/find_api_calls.py ./work         # 接口线索
bash $SK/scripts/build_sign.sh ./work out.apk        # 重打包 + 签名
```

工具下载会按 `scripts/download-sha256.txt` 校验 SHA256：不一致直接中止安装；未钉版本的会打印
实际哈希并 WARN，方便补表。

<p align="right">(<a href="#关于">返回顶部</a>)</p>

<a id="使用"></a>

## 使用

- 流程规则与补丁模式都在 [`SKILL.md`](SKILL.md)，每一步的细节在 [`references/`](references/)。
- 全部命令在 proot Ubuntu（ARM64）实测可用，普通 Linux 也能跑。
- 打发行包：`bash scripts/make_release.sh --name apk-reverse --public` → zip（+ 本地 `.sha256`；发布附件只传 `SHA256SUMS`），并解压复检。
- 校验发行包：`bash scripts/verify_release.sh <zip>`（读 `.sha256` 或 `SHA256SUMS`）。
- 发布到 GitHub：`bash scripts/publish_github.sh --tag v<版本> --release`；令牌从 `$GITHUB_TOKEN`
  或 `~/.config/dsh-go/github-token` 读，不写入仓库。

<p align="right">(<a href="#关于">返回顶部</a>)</p>

<a id="仓库结构"></a>

## 仓库结构

```text
apk-reverse/
├── SKILL.md          # 路由 / 工作流 / 补丁模式 / 规则
├── references/       # 专题文档
├── scripts/          # 可执行工具
├── field-journal/    # 可复用的过程记录（现象 → 根因 → 解决）
├── assets/           # 横幅、图标、分享图
├── AGENTS.md         # Agent 激活与同意边界
├── SECURITY.md       # 信任模型与安全问题报告
├── CONTRIBUTING.md   # 贡献规范
├── CHANGELOG.md      # 变更记录
├── VERSION           # 版本号（唯一来源）
└── LICENSE           # MIT
```

<p align="right">(<a href="#关于">返回顶部</a>)</p>

<a id="文档"></a>

## 文档

- [`references/identity-check.md`](references/identity-check.md) — 本地身份卡，不联网查应用
- [`references/mobile-toolchain.md`](references/mobile-toolchain.md) — 工具链与安装
- [`references/patch-patterns.md`](references/patch-patterns.md) — smali / 清单 / 布局补丁
- [`references/protection-map.md`](references/protection-map.md) — 加固 / 完整性 / 抓包
- [`references/device-verify.md`](references/device-verify.md)、[`references/device-control.md`](references/device-control.md) — 真机验证与操控
- [`references/security-audit.md`](references/security-audit.md) — 导出组件、WebView、密钥
- [`docs/STAGES.md`](docs/STAGES.md) — 六阶段总控：每阶段入口 / 产物 / 过门条件
- [`docs/REPORT-TEMPLATE.md`](docs/REPORT-TEMPLATE.md) — 分析报告模板（结论先行 + 证据链）
- [`docs/MCP-INTEGRATION.md`](docs/MCP-INTEGRATION.md) — JADX / Ghidra / IDA / Burp MCP 接入说明
- [`scripts/frida/README.md`](scripts/frida/README.md) — Frida 脚本库（SSL unpinning / 反调试 / 退出拦截 / root 伪装 / Frida 隐藏 / 返回值替换）
- [`tests/routing_cases.json`](tests/routing_cases.json) — 路由回归用例（CI 用 `scripts/check_routing.py` 校验）
- [`docs/ENVIRONMENTS.md`](docs/ENVIRONMENTS.md) — 本机 proot / Termux / 桌面 Agent 三种环境对比与定位
- [`references/kotlin-r8-recovery.md`](references/kotlin-r8-recovery.md) — R8/ProGuard 混淆与 Kotlin 名称恢复
- [`references/api-extraction.md`](references/api-extraction.md) — 接口 / 鉴权头 / 第三方域名提取
- [`references/on-device-tooling.md`](references/on-device-tooling.md) — 手机 GUI 工具链：MT 管理器 / NP 管理器 / LSPosed / Termux 与脚本分工
- [`references/lsposed-modules.md`](references/lsposed-modules.md) — 重打包被拒时的 LSPosed 模块备选
- [`references/decompilers.md`](references/decompilers.md) — 反编译器选型：jadx / Fernflower / ddc（含手机安装）
- [`references/triage-playbook.md`](references/triage-playbook.md) — 15 分钟分诊清单
- [`docs/EVIDENCE.md`](docs/EVIDENCE.md) — 证据分级与台账纪律（`scripts/ledger.py`）
- [`docs/APP-INTEGRATION.md`](docs/APP-INTEGRATION.md) — 在手机 App 里使用本技能
- [`references/native-fuzzing.md`](references/native-fuzzing.md) — 原生层模糊测试（AFL++/ASan）可行性
- 完整索引见 [`SKILL.md`](SKILL.md) 末尾

<p align="right">(<a href="#关于">返回顶部</a>)</p>

<a id="校验"></a>

## 校验

对外分发 zip 时配套 `SHA256SUMS`（一个文件即可），接收方执行：

```sh
sha256sum -c SHA256SUMS
# 或
bash scripts/verify_release.sh apk-reverse.zip SHA256SUMS
```

<p align="right">(<a href="#关于">返回顶部</a>)</p>

<a id="贡献"></a>


## 联系方式

- 邮箱：<xiaotianya14@gmail.com>
- QQ 群：**258605008**
- 问题反馈：[GitHub Issues](https://github.com/xiaotianya14/apk-reverse-skill/issues)

## 贡献

欢迎提 issue、补补丁模式、补充专题文档、写 field-journal 记录。

1. Fork 这个仓库
2. `git checkout -b feature/你的想法`
3. 提交改动（`git commit -m 'Add your idea'`）
4. `git push origin feature/你的想法`
5. 开一个 Pull Request

请遵守 [`AGENTS.md`](AGENTS.md) 与 [`SECURITY.md`](SECURITY.md) 里的授权与同意边界。

### 贡献者

<a href="https://github.com/xiaotianya14/apk-reverse-skill/graphs/contributors">Contributors</a> — PRs welcome.

<p align="right">(<a href="#关于">返回顶部</a>)</p>

<a id="技术栈"></a>

## 技术栈

<p align="left">
  <code>jadx</code> · <code>apktool</code> · <code>Frida</code> · <code>IDA Pro</code> · <code>Ghidra</code>
</p>

<a id="致谢"></a>

## 致谢

感谢 jadx、apktool、Frida、radare2、Ghidra 等开源工具的作者。本项目是在这些工具之上的一层工作流。

<a id="许可"></a>

## 许可

MIT，见 [`LICENSE`](LICENSE)。使用前请阅读下面的免责声明。

> **免责声明**：本项目仅用于学习研究与**自己拥有或已获授权**应用的逆向分析；
> 使用者自行承担数据丢失、设备与法律风险；不得用于攻击他人设备、未授权修改他人应用或违反平台条款。
> 不提供任何担保，作者不对使用后果负责。

<p align="right">(<a href="#关于">返回顶部</a>)</p>

## 许可证与素材

- **代码与文档**：MIT（见 [`LICENSE`](LICENSE)）。
- **视觉素材不在 MIT 授权范围**：`assets/` 里的头像、横幅、图标、分享图和徽章样式版权归作者所有，
  保留所有权利——**不可商用、不可再分发、不可换名发布**。
- **私有包**（游戏修改资料、过程记录等）不公开、不授权。
- 第三方工具、SDK、商标按其各自条款，详见 [`NOTICE`](NOTICE)。

