# 手机上的图形界面工具链（MT 管理器 / NP 管理器 / LSPosed）

> 有些活用图形界面更快：已经装在手机上的 App、改一个字符串、40 MB 的包不想来回传电脑。
> 本文件说明这些 GUI 工具各管什么、什么时候比命令行划算。
> 证据级别标注：**[实测]** 在手机环境中实际用过；**[推断]** 来自公开文档/常见版本，未逐一实测。

## 1. MT 管理器（`bin.mt.plus`）：手机上的“编辑 → 重打包 → 签名”流水线

**[实测]** MT 管理器是文件管理器 + APK 编辑器，对本技能来说它是一条能在手机上跑完的重打包流程。

| 我们的阶段 | MT 能做什么 | 注意 |
|---|---|---|
| 侦察 | APK 查看器：manifest、入口列表、跨 dex/资源字符串搜索 | 字符串搜索最快；它不是完整 Java 反编译 |
| Dex 编辑 | Dex 查看 + smali 级编辑 | 编辑粒度是 smali，和 `references/patch-patterns.md` 的纪律一致 |
| 去签名校验 | 内置“去除签名校验”类功能 | 只是便利功能：要确认它改的是哪一层，Java 层放行不代表 native 校验也过了 |
| 取产物 | 从 APK/zip 里抽 `classes.dex`、`.so`、`resources.arsc` | 把一个 `.so` 单独拿出来给命令行工具用很方便 |
| 重打包 + 签名 | 在手机上重建 APK 并签名 | 产物在 MT 工作目录；对齐/resources.arsc 规则照样要检查（`build_sign.sh` 的验收标准不变）|

**什么时候用 MT**：一次性小改、要在同一台手机上立刻装回去验证、包太大不想来回传。
**什么时候用脚本**：可重复、要批量、要字节级补丁和校验、需要完整反编译——这些还是 `scripts/` 更稳。

## 2. NP 管理器 / 其他同类工具

**[推断]** 同类的 APK 编辑器（NP 管理器等）能力相近：查看、编辑、重签、去校验。
选择标准：能改 smali、能看 manifest、签名可自定义、产物能对齐。不要依赖“一键”黑盒功能，
动完用 `scripts/verify_release.sh` 或 `apksigner verify` 复核。

## 3. LSPosed / LSPatch：不改包，也能改行为

**[推断]** 如果目标 App 重打包必崩（签名校验在 native、加固、完整性校验），可以换思路：
做一个 **LSPosed 模块**在运行时 hook，不重打包原 APK。步骤与边界见 `references/lsposed-modules.md`。

## 4. Termux：纯命令行的替代环境

**[实测]** Termux 也能装 jadx/apktool/frida，适合没有电脑、又不想用本技能自带环境的人。
区别：Termux 没有本技能的设备操控与发布管线；工具要自己装、自己维护。
本技能默认不需要 Termux（直接在本机 Linux 容器里跑），但产物可以互通。

## 5. 与脚本的分工（建议）

| 任务 | 首选 |
|---|---|
| 改一个字符串 / 删一个布局 | MT 管理器（快）|
| 批量、可复现的补丁 | `scripts/patch_method.py` / `so_patch.py` |
| 反编译看逻辑 | `jadx` 或 `ddc`（见 `references/decompilers.md`）|
| 重打包 + 签名 + 验证 | `scripts/build_sign.sh` + `references/device-verify.md` |
| 运行期行为修改 | `scripts/frida/` + `references/lsposed-modules.md` |
