# 贡献指南

## 可以提交

- 脚本修复、兼容性改进（shell / Python / 工具版本）；
- 文档纠错、命令更新；
- 可复用的过程记录：`现象 → 根因 → 解决`（放 `field-journal/`，≤40 行/条）。

## 不接受

- 绕过技术保护措施、反检测、成品注入/修改工具；
- 攻击他人设备、账号或网络的脚本与说明；
- 未授权应用的数据、个人设备信息、凭据、私钥；
- 大体积二进制或与技能无关的样本文件。

## 流程

1. Fork → 建分支；
2. 改动（脚本/文档/CHANGELOG）；
3. 本地跑 `python3 scripts/check_repo.py --public`，必须通过；
4. 更新 `CHANGELOG.md` 的 `[Unreleased]`（Added / Changed / Fixed / Security）；
5. 提交 PR，说明动机、影响范围与验证方式。

发布：`bash scripts/make_release.sh --name apk-reverse --public`（含自检、SHA256 与解压复检）。
推送到 GitHub：`bash scripts/publish_github.sh --repo <url> --tag vX.Y.Z --release`（token 只经 askpass，不写入 remote）。

## 约定

- 目录：`references/` 放专题文档，`scripts/` 放可执行工具，`field-journal/` 放过程记录；
- 版本：`VERSION` 为唯一来源，改动功能时按 SemVer 升级，并同步 `CHANGELOG.md` 与 README 徽章；
- 命令示例：路径用 `$SK` 或相对路径，不写个人设备路径。

## 素材与授权

- `assets/` 下的头像、横幅、图标、分享图**不随 MIT 授权**，未经作者同意不要复制、再分发或商用；
- 不要提交他人的作品、头像、截图或未授权的应用资源；
- 不把“未验证的能力”写成“已支持”：声称能做到什么，必须附验证方式或标注“未验证”；
- 涉及技能行为/流程规则的改动，先开 Issue 讨论方向，再提 PR；一个 PR 只解决一件事。
