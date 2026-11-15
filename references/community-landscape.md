# 社区同类逆向 skill 对标与命名/元数据规范

> **社区资料，仅作参考。** 以下仓库与描述核对于 2026-11-13 的 GitHub 页面；只做摘要 + 链接，不搬运原文，也**不代表对第三方仓库安全性的背书**。
> 第三方脚本先读源码、在本机验证再用，风险自担。
> 本技能只服务**自己拥有、已购买或已获授权修改**的应用（见 `SKILL.md`「必读」与 §10 联网边界）。

## 一、结论：我们现在怎么对齐

| 维度 | 社区常见做法 | 我们怎么做 |
|---|---|---|
| 技能入口 | `SKILL.md` + frontmatter（`name` / `description` 必备；社区项目还会加 `version` / `allowed-tools` 等） | 已用：frontmatter `name: apk-reverse` / `description` / `whenToUse`（宿主用来做触发路由） |
| 插件/市场元数据 | `.claude-plugin/marketplace.json`（可 `/plugin marketplace add` + `/plugin install`） | **不发布市场**：本环境从 skills 目录直接加载，无 marketplace 需求 |
| 仓库门面 | README + 徽章（License / Version / 平台 / 工具）+ `LICENSE` + social preview | 已用：`README.md` 徽章 + `LICENSE`（MIT）；social preview 属托管平台能力，本地项目不需要 |
| 文档组织 | `references/` 专题 wiki + 根 `SKILL.md` 路由表 | 已用：`SKILL.md` §0 路由 + 参考文档索引 + `references/` 专题文档 |
| 执行层 | `scripts/` 放可运行工具，文档只写"命令 → 章节" | 已用：`scripts/` 可执行脚本 + `field-journal/` 实战与维护日志 |
| 多技能合集 | 按语言/领域拆多个技能包（中文仓库常用中文目录名） | **不拆**：本技能聚焦"手机端 APK 逆向"一条线，避免用户选择困难 |
| Agent 定义 | `.kilo/agent/reverser.md` 之类角色文件 + skill 决策树 | **不照搬**：本环境里由 `SKILL.md` + 系统技能目录承担，不额外维护 agent 文件 |

## 二、仓库清单（摘要 + 链接）

| 仓库 | 形态 | 一句话 | 我们借鉴什么 |
|---|---|---|---|
| [incogbyte/android-reverse-engineering-claude-skill](https://github.com/incogbyte/android-reverse-engineering-claude-skill) | Claude Code plugin：`.claude-plugin/marketplace.json` + `plugins/.../SKILL.md` + `scripts/` | jadx/Fernflower 反编译 + Retrofit/OkHttp/GraphQL 接口提取 + 安全审计（含 Fragment Injection）+ Frida 自适应适配 | 接口线索提取、安全审计清单、按静态发现生成针对性 hook 的思路 |
| [index-login/MobileRE-Skill](https://github.com/index-login/MobileRE-Skill) | Kilo Agent：`.kilo/agent/reverser.md` + `.kilo/skill/*/SKILL.md` + `references/` wiki + `tools/` | Frida hook、一键解包还原、内存 DEX dump、反检测、Ghidra MCP 符号恢复；中英双语 README + 徽章 | 文档分层（agent / 技能 / 手册 / 工具）、合规检测项、README 门面规范 |
| [NoraStory/reverse-SKILL](https://github.com/NoraStory/reverse-SKILL) | 51 个技能包的合集，**中文目录名**组织 | 覆盖 Android 解包还原 / DEX 内存解包还原 / OLLVM 反混淆 / VMP 虚拟化还原 / Frida 脚本集等 | 按专题拆目录、按专题拆目录（工具清单见 `tool-inventory.md`）；**不采纳**其中「越权/破限」类内容（见 §四） |
| [darbra/awesome-ai-reverse](https://github.com/darbra/awesome-ai-reverse) | 分类 awesome 清单（约 1k stars） | 分四类：JS 逆向、二进制/原生逆向（IDA/Ghidra MCP）、Android/iOS 安全、浏览器自动化/抓包 | 看社区工具全景、做选型参考；不照单全收 |

### awesome 清单里与 Android 相关的条目

| 项目 | 方向 | 一句话 |
|---|---|---|
| [apk-reverse](https://github.com/newliver666/apk-reverse) | APK 逆向 skill | 面向 Android APK 去臃肿/广告组件清理/dex 补丁/重打包（**同名项目，定位相近**） |
| [Android RE Skill](https://github.com/SimoneAvogadro/android-reverse-engineering-skill) | APK 反编译 | 反编译 APK/XAPK/JAR/AAR，提取 Retrofit/OkHttp/硬编码 URL |
| [JADX-AI-MCP](https://github.com/zinja-coder/jadx-ai-mcp) | 反编译 MCP | MCP + JADX 插件，让 LLM 直接读反编译代码 |
| [Frida MCP Server](https://github.com/zhizhuodemao/frida-mcp) | 动态分析 MCP | 让 AI 通过 Frida 做 Android 动态分析 |
| [ADB MCP Server](https://github.com/zhizhuodemao/adb-mcp) | 设备管理 MCP | 把 ADB 设备管理暴露给 AI（安装/启动/日志等） |
| [Android Proxy MCP](https://github.com/zhizhuodemao/android_proxy_mcp) | 抓包 MCP | AI 侧抓取和分析 Android HTTP/HTTPS 流量 |

> **关于 MCP**：这些服务通常跑在桌面端/独立进程；本机是手机 proot，**优先用本技能的 CLI 脚本**
> （`decode.sh` / `find_api_calls.py` / `adb_device.sh`），不额外起 MCP 进程。想接 MCP 时按
> `references/mobile-toolchain.md` 的现状评估，别为"看起来高级"硬装。

## 三、我们已采纳 / 不采纳

| 项 | 状态 | 说明 |
|---|---|---|
| 脚本 + 文档分层 | ✅ 已采纳 | `scripts/` 可执行、`references/` 只写方法与路由，避免文档里塞大段代码 |
| 接口/URL/凭据线索提取 | ✅ 已采纳 | `scripts/find_api_calls.py`（见 `SKILL.md` §0 / §2） |
| 安全审计清单 | ✅ 已采纳 | `references/security-audit.md`（pinning/导出组件/Fragment Injection/WebView/密钥…） |
| 抓包三路径（mitmproxy / apk-mitm / Frida） | ✅ 已采纳 | `references/protection-map.md` §六 |
| 真机 adb root 通道 | ✅ 已采纳 | `scripts/adb_device.sh` + `references/device-verify.md`（自动发现端口） |
| 命名 / README / 徽章 / License 规范 | ✅ 已采纳 | `README.md` + `LICENSE`（MIT） |
| 按专题拆目录（中文目录名） | ⚠️ 部分采纳 | 保持单一技能 + `references/` 分专题，不拆 51 个包 |
| MCP 全家桶（JADX/Frida/ADB MCP） | ⚠️ 参考不照搬 | 手机 proot 起 MCP 收益低；CLI 脚本更稳、更可复现 |
| 越权 / 破限 / 越权 prompt | ❌ 不采纳 | AI 模型越权黑话，不是 APK 技术（见 §四） |
| 修改成品 / 加载器 / 第三方修改 | ❌ 不采纳 | 法律与安全红线；只做自有/授权 App 的技术分析与改包 |
| 闭源收费工具 | ❌ 不采纳 | 不可审计、不可复现；只用 apt/pip/GitHub 官方源工具 |

## 四、特别说明：越权 / 破限不是 APK 逆向

社区里有仓库把「越权」「破限」这类目录混进逆向技能合集（如 NoraStory/reverse-SKILL 里的
「deepseek-v4-pro越权」「海鸥破限」）。**这些是 AI 模型越权 / 提示词动态加载黑话，与解包还原、广告组件清理、改包无关。**

- 本技能**不提供、不分析、不生成**越权 prompt / 提示词动态加载内容；
- 用户说"越权 / 破限 / 越权"时，先确认是不是在说 App 的加固/修改（那走正常逆向流程，且仍需授权），
  否则直接说明不在范围；
- 只引用社区里**技术类**内容（解包还原、Hook、混淆还原、抓包），越权类一律不采纳。

## 五、命名与元数据规范（本技能当前值）

| 项 | 当前值 | 备注 |
|---|---|---|
| 项目目录 | `~/skills/apk-reverse` | 原名 `reverse-skill`，改名见 `CHANGELOG.md` |
| 技能名（frontmatter `name`） | `apk-reverse` | 与目录一致，便于 `~/skills/<name>` 定位 |
| 显示名 | 逆向技能 | 给用户看的中文名，写在 `SKILL.md` 标题与 README |
| 触发描述 | `description` + `whenToUse` | 含"给这个 APK 广告组件清理/权益/改数值/逆向/重打包"等口语句式 |
| 版本 | README 徽章 `version-v12` | 与技能内容同步；暂无 `CHANGELOG.md`，变更用 `CHANGELOG.md` 记录 |
| License | MIT | 见 `LICENSE` |
| 文档索引 | `SKILL.md` §参考文档索引 | 新增文档必须挂到索引，避免孤儿文件 |
| 打包交付 | `cd ~/skills && zip -qr /sdcard/Download/逆向技能-手机版.zip apk-reverse` | 见 `SKILL.md` §11 |

## 六、免责声明

- 本技能仅用于用户**自己拥有、已购买或已获授权**修改的应用；遵守当地法律、应用许可与服务条款。
- 不适配他人线上付费服务、不修改第三方权益、不分发未授权副本、不提供修改成品/加载器/第三方修改。
- 社区链接与描述仅作方法参考，**不代表背书**；第三方脚本先读再用，风险自担。

> 关联：`tool-inventory.md`（社区工具清单/按需安装）、`security-audit.md`（审计清单）、`SKILL.md` §0 路由。
