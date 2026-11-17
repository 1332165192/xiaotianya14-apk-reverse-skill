# Changelog

All notable changes to **apk-reverse** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.14] - 2026-11-17

### Added

- **支持 DSH Go 手机端**：SKILL.md 增加安装/使用说明（商城搜索、插件命令、手动包三种装法；重启内核生效；可直接用 DSH Go 内置手机操控工具做真机验证）
- README_zh / README 增加「安装到 DSH Go / DeepSeek Harness」小节（含技能名 `apk-reverse`、触发词、电脑端同样可用）
- package.json：description 补充 DSH Go，keywords 增加 `dsh-go`、`dsh-skill`、`mobile`
- 仓库 topics 补齐 `dsh-plugin`、`dsh-go`、`dsh-skill`，用于 dshfind 等自动索引

### Marketplaces

- awesome-dsh-plugin：已有收录条目（DSH Go 默认商城），等待每日 10:23 索引刷新
- dsh.so：自动爬取，无需提交
- dshfind.com：按 GitHub topic `dsh-plugin` 自动聚合，收录有 1–2 天延迟
- npm：本地无 token，暂未发布 npm 包


## [0.5.13] - 2026-11-16

### Added

- 可作为 DeepSeek Harness 技能插件安装：`dsh plugin --profile web add github:xiaotianya14/apk-reverse-skill`
- 新增 `lib/index.js`、`cordis.patch.yml`、`package.json`（`dsh.bundle`），把本技能注册为 DeepSeek Harness skill provider

## [0.5.12] - 2026-11-16

### Added

- `NOTICE`：授权边界说明（代码/文档 MIT；头像/横幅/图标/分享图等视觉素材**不授权**，不可商用/再分发；私有资料不公开；第三方按各自条款）
- README / README_zh 增加「许可证与素材」段
- CONTRIBUTING 增加「素材与授权」规则（不搬运他人作品、未验证能力不得写成已支持、一 PR 一事）

## [0.5.11] - 2026-11-15

### Fixed

- 横幅改用新版设计图（WebP，明暗两版），与用户确认的样式一致；文件名 `-v3` 防缓存
- 删除之前的 SVG 横幅

## [0.5.10] - 2026-11-15

### Fixed

- 横幅 SVG 换成新版（居中排版，与新版 PNG 设计一致）；旧版左对齐 SVG 删除
- 文件名改为 `banner-*-v2.svg`，避免 CDN/浏览器缓存旧图

## [0.5.9] - 2026-11-15

### Changed

- README 图片（头像/横幅/徽章）改走 jsDelivr CDN（`cdn.jsdelivr.net/gh/...`），
  国内加载明显加快；仓库内 SVG 仍是源文件
- 参考同类项目做法（图片走 CDN，不直接依赖 GitHub raw）

## [0.5.8] - 2026-11-15

### Changed

- 删除旧的 PNG 横幅/头像（`banner-*.png`、`avatar-*.png`），仓库只保留新版 SVG，避免误用旧图
- README 继续使用 `assets/banner-*.svg` / `assets/avatar-*.svg`（明暗两版）

## [0.5.7] - 2026-11-15

### Changed

- 发布附件合并：Release 只传「zip + SHA256SUMS」两个文件（不再单独传 `<zip>.sha256`）
- 本地仍生成 `.sha256` 方便校验；README/指南说明同步

## [0.5.6] - 2026-11-15

### Added

- README / README_zh 新增「联系方式」：邮箱、官方 QQ 群 258605008、GitHub Issues 反馈入口
- 隐私扫描放行以上公开联系方式（仅这些，其他个人信息仍会被拦）

## [0.5.5] - 2026-11-15

### Added

- `references/native-fuzzing.md`：原生层模糊测试（AFL++/ASan）适用场景与手机端可行性（吸收社区项目思路，不内置重型 fuzz）
- `references/community-landscape.md`：补充 2026-11-15 复核的同类项目（zzusec / Fausto / incogbyte / blackbox-re-agent / alvinhayy / awesome 清单），标注星数与吸收情况
- `docs/MCP-INTEGRATION.md`：补充复核过的移动安全 MCP 项目

## [0.5.4] - 2026-11-15

### Changed

- README 图片加载优化：移除 shields.io 动态徽章、star-history、contrib.rocks、skillicons 等外链图，
  全部改为本地静态 SVG（头像/横幅/徽章），首屏不再依赖第三方服务，国内加载明显变快
- 图片总量从约 500KB 降到约 10KB（SVG）

## [0.5.3] - 2026-11-15

### Fixed

- 修正 README 统计口径：脚本 31 → 32（含 privacy_scan.py）、参考文档 18 → 24

## [0.5.2] - 2026-11-15

### Added

- `scripts/privacy_scan.py --fix`：自动替换 .md/.txt 里的个人信息（设备型号、本机路径、令牌、邮箱、手机号、内部标记），
  发布流程里先扫 → 命中自动清理 → 再扫，仍有剩余则停止发布

## [0.5.1] - 2026-11-15

### Added

- `scripts/privacy_scan.py`：发布前隐私扫描（真实设备型号、本机路径、账号/令牌、邮箱/手机号、内部标记），
  `make_release.sh --public`、CI、发布技能都会跑；命中即拒绝发布

### Changed

- 公开版文档脱敏：去掉真实设备型号、本机 home 路径，示例邮件改为占位地址

## [0.5.0] - 2026-11-15

### Changed

- （填写本次改动）


## [0.5.0] - 2026-11-15

### Added

- `references/on-device-tooling.md`：手机 GUI 工具链（MT 管理器 / NP 管理器 / LSPosed / Termux）与脚本的分工
- `references/lsposed-modules.md`：重打包被拒时的 LSPosed 模块备选路径
- `references/decompilers.md` + `scripts/install_ddc.sh`：反编译器选型（jadx / Fernflower / ddc），
  ddc（Rust，MIT）ARM64 静态版可在手机直接安装，版本与 SHA256 钉死
- `scripts/check_commands.py`：校验文档里引用的脚本/文档路径真实存在，CI 已接入
- 路由回归用例扩充到 15 条
### Added

- `references/triage-playbook.md`：15 分钟分诊清单（结构/加固/广告/权益/接口/校验/服务端权威）
- `docs/EVIDENCE.md` + `scripts/ledger.py`：证据分级（observed/measured/inferred）与轻量台账
- `docs/APP-INTEGRATION.md`：在手机 App 内使用本技能（远程主机、可选机械门）
- `docs/MCP-INTEGRATION.md` 补社区 MCP 清单；报告模板增加证据级别
- 路由回归用例扩充到 19 条

## [0.3.1] - 2026-11-15

### Fixed

- 路由回归用例兼容内部版的旧文件名（`vip-unlock.md` / `value-hacking.md` 与改名后的新文件都能通过），三份包自测全部通过

## [0.3.0] - 2026-11-15

### Added

- Frida 脚本库扩充：内存 dex dump、已加载 so dump、JNI RegisterNatives 追踪、
  加密调用观察（Cipher/MessageDigest/Base64）、SharedPreferences/KeyStore 读取、TLS 明文记录
  （实现思路参考 Apache-2.0 项目 CreditTone/android-reverse-engineering-skill，已重写）
- `references/kotlin-r8-recovery.md`：R8/ProGuard 混淆识别与 Kotlin 名称恢复（mapping / @Metadata / 字符串反查 / 调用链）
- `references/api-extraction.md` + `references/third-party-hosts.txt`：接口、鉴权头、第三方域名过滤
- `docs/ENVIRONMENTS.md`：本机 proot / Termux / 桌面 Agent 三种环境对比与本技能定位
- 路由回归用例扩充到 12 条

## [0.2.0] - 2026-11-15

### Added

- `scripts/frida/`：Frida 脚本库（SSL unpinning / 反调试绕过 / 退出拦截 / root 伪装 / Frida 隐藏 / 函数返回值替换）+ `run_frida.sh` 启动器
- `docs/STAGES.md`：六阶段总控（侦察 → 协议/数据 → 逻辑定位 → 补丁 → 验证 → 交付），每阶段有入口、产物和过门条件
- `docs/REPORT-TEMPLATE.md`：分析报告模板（结论先行、证据链、改动清单、验证结果）
- `docs/MCP-INTEGRATION.md`：JADX / Ghidra / IDA / Burp MCP 接入说明与手机端可行性
- `tests/routing_cases.json` + `scripts/check_routing.py`：路由回归用例，CI 自动校验

### Changed

- CI 增加路由用例检查；SKILL.md 与中英 README 的索引同步补充

## [0.1.3] - 2026-11-15

### Changed

- 变更记录措辞收敛：不再罗列内部用语与具体检测词表，只描述能力变化
- 扫描器逻辑不变（词表与 0.1.2 相同）

## [0.1.2] - 2026-11-15

### Changed

- 扫描词表扩充（公开版与内部两版同步，重复词只保留一份）：补充若干检测用关键词，
  用于匹配目标 App 内的字符串；`analyze_ads.py` 增加广告关闭类关键词

## [0.1.1] - 2026-11-15

### Fixed

- 修复扫描器检测关键词的误替换：恢复若干用于匹配目标 App 字符串的搜索词
  （措辞中性化时被误改，可能导致公开版扫描漏报）

## [0.1.0] - 2026-11-15

### Changed

- （填写本次改动）


## [0.1.0] - 2026-11-15

### Changed

- 横幅改为居中排版，右半边不再空；文字统一居中、底部小注居中
- 圆形头像新增浅色版（`assets/avatar-light.png`），README 按主题自动切换明暗两张

## [0.0.9] - 2026-11-15

### Changed

- 横幅重做：去掉右侧重复的图形标记和斜纹底，改为干净的左对齐排版（圆形方标 + 标题 + 中英副标题 + 关键词一行）
- 深色 / 浅色两版同步更新，浅色主题下自动切换

## [0.0.8] - 2026-11-15

### Changed

- README 保留顶部圆形头像的同时，**横幅恢复到徽章下方**（明暗主题自适应），两者不再互相挤压

## [0.0.7] - 2026-11-15

### Changed

- README 顶部布局仿同类仓库：**圆形头像居中在上、标题单独一行在下**，不再和横幅/图标叠在一起
- 移除与顶部头像重复的底部图标区；横幅素材保留在 `assets/` 备用

## [0.0.6] - 2026-11-15

### Changed

- 公开版措辞中性化：数值类、付费权益类、限制解除类、异常数值类的旧称谓统一改为中性表述，
  文档正文与脚本注释里不再出现旧称谓
- 两个旧文件名含违规措辞的参考文档已改名：`value-logic-analysis.md`、`entitlement-analysis.md`；
  `SKILL.md` 与其余文档里的引用全部同步
- 脚本输出标签同步中性化；检测用正则关键词保留（用于匹配目标 App 内的字符串，不属操作指导）

### Removed

- 旧名参考文档（已由上述两个新文件取代）

## [0.0.5] - 2026-11-15

### Changed

- README 排版仿照同类技能库：顶部横幅与标语、锚点导航、`一眼看完` 状态表、流程图、
  能力表、Star 历史、技术栈图标、每节「返回顶部」、致谢与免责声明
- 中英文 README 同步重排，锚点一一对应

## [0.0.4] - 2026-11-15

### Changed

- 发布包与仓库页面保持一致：README 明暗主题横幅、标题左侧图标、Logo 区、贡献者头像墙、`assets/` 素材全部打进发行包
- CHANGELOG 结构整理（0.0.3 条目并入正式版本）

## [0.0.3] - 2026-11-15

### Added

- `assets/banner-dark.png`、`assets/icon-512.png`：README 顶部横幅与方形图标
- README 中英文顶部重排：居中横幅 + 徽章行（release / stars / forks / issues / license / Android）+ 语言切换
- README 底部「贡献者 / Contributors」头像墙（contrib.rocks）
- `scripts/verify_release.sh`：校验发行 zip 的 SHA256（配 `SHA256SUMS` 或 `<包>.sha256`）
- `scripts/install_tools.sh` 下载校验：已知版本按 `scripts/download-sha256.txt` 固定 SHA256，不一致自动删除并中止；未钉版本打印实际哈希并 WARN
- `scripts/make_release.sh`：发布打包（自检 → 打包 → 完整性 → SHA256 → 解压复检）

## [0.0.2] - 2026-11-14

### Added

- `scripts/publish_github.sh`：手机端一键发布到 GitHub（提交/建仓/push/tag/Release，token 走 askpass，不写 remote）
- `scripts/verify_release.sh`：发行 zip SHA256 校验；`scripts/bump_version.sh`：三版版本号统一升级

## [0.0.1] - 2026-11-13

### Added

- 首个公开版本：Android APK 逆向研究技能包（`SKILL.md` + `references/` + `scripts/`）
- 解包与反编译：apktool / jadx / smali3 / CFR
- 组件与广告分析、付费与权益逻辑分析、数值逻辑分析
- 补丁：smali 定点补丁、静态字段、原生 `.so` 指令补丁
- 保护分析：加固壳、签名校验、完整性校验的识别与适配
- 动态与网络分析：Frida / objection、mitmproxy、证书固定适配
- 打包签名与真机验证：zipalign / apksigner / adb 通道
- 仓库自检脚本 `scripts/check_repo.py` 与 CI
- 治理文档：`AGENTS.md`、`SECURITY.md`、`CONTRIBUTING.md`、`VERSION`

### Security

- README 与 SKILL 顶部声明用途边界与免责声明
- 明确不提供绕过技术保护措施、反检测或影响他人环境的成品工具
