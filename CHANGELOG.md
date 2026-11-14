# Changelog

All notable changes to **apk-reverse** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
