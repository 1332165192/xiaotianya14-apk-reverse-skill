# Changelog

All notable changes to **apk-reverse** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-11-15

### Fixed

- 恢复 `scan_premium.py` / `analyze_ads.py` 里的检测关键词（`解锁`、`免广告`、`去广告`）。
  这些只是用来匹配目标 App 内字符串的搜索词，措辞中性化时被误替换，导致公开版扫描可能漏报

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
