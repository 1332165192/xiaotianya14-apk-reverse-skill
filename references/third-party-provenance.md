# 第三方来源与自研边界（审计说明）

> 目的：把“哪些完全自研、哪些参考了别人思路、哪些是外部工具/运行库”说清楚，避免把别人的代码说成自己的。
> 结论先行：本仓库**没有把第三方工具或源码打包进来**；代码级参考只有 `scripts/frida/` 里 3 个脚本（CreditTone，Apache-2.0，思路参考、代码重写，已在 NOTICE 署名）。

## 1. 完全自研（本仓库原创代码/文档）

### 1.1 核心流程脚本

`scripts/` 下除 1.2 列出的 3 个 Frida 脚本外，其余为本项目自写：

- Shell：`adb_common.sh`、`adb_device.sh`、`build_sign.sh`、`decode.sh`、`device_adb_guard.sh`、`device_input.sh`、`device_perm_chain.sh`、`device_ui.sh`、`frida_server_prep.sh`、`install_ddc.sh`、`install_tools.sh`、`make_release.sh`、`publish_github.sh`、`toolcheck.sh`、`verify_release.sh`、`bump_version.sh`
- Python：`analyze_ads.py`、`call_graph.py`、`check_commands.py`、`check_repo.py`、`check_routing.py`、`dex_dump.py`、`find_api_calls.py`、`find_framework_apis.py`、`fix_dollar_resources.py`、`hook_gen.py`、`identity_report.py`、`il2cpp_meta.py`、`ledger.py`、`manifest_clean.py`、`manifest_summary.py`、`merge_splits.py`、`patch_method.py`、`privacy_scan.py`、`scan_premium.py`、`so_patch.py`、`unpack_archive.py`
- Frida（未标第三方来源的 10 个）：`exit_blocker.js`、`frida_hider.js`、`function_patcher.js`、`hook_encryption_algo.js`、`keystore_dump.js`、`root_bypass.js`、`run_frida.sh`、`ssl_log.js`、`ssl_unpinning.js`、`anti_debug_bypass.js`
- 文档：`SKILL.md`、`README.md`、`README_zh.md`、`references/*.md`、`docs/*.md`、本说明本身

### 1.2 0.6.9 新增工具（全部本次自写）

`unpack_archive.py`、`hook_gen.py`、`find_framework_apis.py`、`call_graph.py`、`dex_dump.py`、`dex_dump.js`、`il2cpp_meta.py`、`references/signature-recovery.md`。
其中 `dex_dump` 不依赖 `frida-dexdump`（GPL），`il2cpp_meta` 不依赖 `Il2CppDumper`。

## 2. 参考思路、代码重写（不是复制）

| 文件 | 参考项目 | 许可 | 处理 |
|---|---|---|---|
| `scripts/frida/dump_dex.js` | [CreditTone/android-reverse-engineering-skill](https://github.com/CreditTone/android-reverse-engineering-skill) | Apache-2.0 | 思路参考，代码重写；已在 NOTICE §7 署名 |
| `scripts/frida/dump_so.js` | 同上 | Apache-2.0 | 同上 |
| `scripts/frida/jni_method_trace.js` | 同上 | Apache-2.0 | 同上 |

**说明**：这 3 个文件不是从对方仓库复制的源码；文件头也写明了“思路参考、重写实现”。如果以后要复制其代码，必须保留 Apache-2.0 LICENSE/NOTICE 并标注修改。

## 3. 运行时依赖 / 外部工具（不随包分发）

这些是“调用”，不是“打包”：

- `jadx`、`apktool`、`frida` / `frida-tools`（Java bridge）、`CFR`、`smali/baksmali`、`Vineflower`、`dex2jar`、`bundletool`、`ddc`、`unidbg`
- `adb` / `aapt2` / `zipalign` / `apksigner`（Android SDK）
- 共同点：**不在 zip 里**，由用户环境或安装脚本获取；许可与条款按各自官方 LICENSE，本项目不代其授权。

## 4. 方法 / 资料参考（只读思路，不复制代码）

已在 `NOTICE` 第 6、7 节署名：

- `morluto/rea` — MIT
- `zhaoxuya520/reverse-skill` — MIT
- `Asaiuta/reverse-workbench-skill` — MIT
- `SimoneAvogadro/android-reverse-engineering-skill` — Apache-2.0
- `CreditTone/android-reverse-engineering-skill` — Apache-2.0
- 社区资料：incogbyte、index-login、NoraStory、darbra、alvinhayy、zzusec、Fausto-404、maosasagawa、MDSIXONE、zhuyansen（仅链接/摘要，见 `references/community-landscape.md`）

## 5. 明确没有使用 / 没有复制

- `frida-dexdump` — GPL-3.0，**未打包、未复制**；只作为“用户自行安装的外部工具”提过。
- `P4nda0s/reverse-skills` — README 称 MIT 但仓库无 LICENSE 文件，**未复制**。
- `woxiangyangzhimao/skills` — 无 LICENSE，**未复制**。
- `Il2CppDumper` — MIT，但本版**未打包**；`il2cpp_meta.py` 为自写最小解析器。
- `kotlinx-metadata` — Apache-2.0，本版**未使用**。

## 6. 结论

- **没有第三方源码被复制进本仓库**（唯一代码级参考是 CreditTone 的 3 个 Frida 脚本，已重写并署名）。
- **没有 GPL/AGPL 代码被打包**。
- 外部工具只是调用，不随包分发；其名字/条款已在 NOTICE 与本文档说明。
- 方法参考已尽量署名；如权利人认为某处应补充/删除，可通过 GitHub Issues 或邮箱联系，核实后处理。
