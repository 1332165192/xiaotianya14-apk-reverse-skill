# 社区工具清单与按需安装（懒加载）

> 来源：社区移动逆向 skill 与 awesome 清单（见 `community-landscape.md`）。
> 原则：**用到才装，不用不占空间**。本机已装的直接用；未装的给“一条命令”，
> 统一走 `bash scripts/install_tools.sh --community`（或手动命令）。

## §1 本机已有（直接可用）

| 工具 | 用途 | 命令 |
|---|---|---|
| jadx 1.5.1 | APK/DEX → Java 源码 | `jadx` |
| apktool 2.7 | 资源/smali 解码与回编 | `apktool` |
| smali / baksmali 2.5.2 + smali3 3.0.9 | 汇编/反汇编（新指令集用 `smali3`/`baksmali3`） | 同名命令 |
| CFR 0.152 | jar/class 反编译（新版本 class 兜底） | `java -jar /root/tools/jars/cfr.jar` |
| frida 17.26.2 + frida-server | 动态 Hook | `frida` / `adb_device.sh frida start` |
| objection 1.12.5 | 一键解 SSL pinning 等 | `objection -g <包名> explore` |
| mitmproxy 12.3.1 / apk-mitm 1.3.0 | 抓包 / 重签信任用户 CA | `mitmdump` / `apk-mitm` |
| apkid / binwalk / yara / protoc | 加固识别 / 异常包 / 特征 / protobuf | 同名命令 |
| hermes-dec | RN Hermes 字节码反编译 | `hbc-decompiler` |
| lief / androguard / blackboxprotobuf | ELF 读写 / dex 解析 / protobuf | python import |
| radare2 / binutils / xxd | .so 分析、strings、hex | `r2` / `strings` / `xxd` |
| adb（自动发现端口） | 真机通道 | `adb_device.sh check` |
| MT管理器 / App Manager / LibChecker / PCAPdroid | 手机端图形化工具（已装） | 见 `android-app-tools.md` |

## §2 社区在用（2026-11-13 已按需装好）

| 工具 | 社区谁在用 / 干什么 | 装法 | 体积 |
|---|---|---|---|
| **Vineflower 1.11.1** | incogbyte skill：jadx 之外的第二反编译器，处理 lambda/generics 更干净 | ✅ 已装：`/root/tools/jars/vineflower.jar`（`java -jar ... --help`）| 1.8MB |
| **dex2jar v2.4** | incogbyte：DEX→JAR 后交给 Vineflower | ✅ 已装：`/root/tools/dex2jar/d2j-dex2jar.sh` | ~10MB |
| **bundletool 1.18.3** | incogbyte：AAB → 通用 APK | ✅ 已装：`/root/tools/jars/bundletool.jar`（`java -jar ... version`）| 32MB |
| **unicorn 2.1.4 + capstone 5.0.7** | MobileRE-Skill：Unicorn 模拟执行 .so 单函数 | ✅ 已装（pip，`import unicorn, capstone`）| ~20MB |
| **unidbg** | MobileRE/社区：离线跑 native 方法 | 无官方 jar，需 `git clone zhkl0228/unidbg` + Maven（依赖 1GB+，手机不划算）→ **不装**，需要时用 Frida/unicorn 代替 | — |
| **Ghidra / IDA** | 桌面端反编译 | Ghidra 官方无 linux-arm64 反编译后端；IDA 商业软件 → **手机不装**，用 r2 / objdump / `smali3` 代替 | — |
| **JADX-AI-MCP / GhidraMCP / frida-mcp / adb-mcp** | 社区通过 MCP 让 AI 直接操作 jadx/Ghidra/Frida | 需要 MCP 客户端接入；本环境只挂了 phone 资源服务，未接这些 → **暂不采用**；等价能力已由 CLI + adb 覆盖 | — |
| **SimpleHook / LSPatch / Xposed 模块** | 免 root Hook / 模块动态加载 | 与 Frida/静态补丁重叠，且需要改包/框架 → **不装**（需要时用 Frida） | — |
| **blutter**（Flutter Dart AOT） | Flutter 深度分析 | 需编译（cmake+ninja+Dart SDK，15min+）→ 需要时再装，先用 `strings libapp.so` 等长替换（见 `protection-map.md` §四） | — |

## §3 懒加载怎么用

```sh
# 一条命令装“社区工具组”（Vineflower + dex2jar + bundletool + unicorn/capstone）
bash scripts/install_tools.sh --community

# 只查有没有、缺什么（不装）
bash scripts/install_tools.sh --check

# 单独装某一类（脚本未封装时手动）：
pip install unicorn capstone -i https://mirrors.aliyun.com/pypi/simple
```

装好后位置（已实测）：

| 文件 | 路径 |
|---|---|
| Vineflower | `/root/tools/jars/vineflower.jar` |
| dex2jar | `/root/tools/dex2jar/d2j-dex2jar.sh` |
| bundletool | `/root/tools/jars/bundletool.jar` |
| unicorn/capstone | python 模块（`import unicorn, capstone`） |

## §4 用不用、怎么选

- 只做 APK 广告组件清理/会员/数值 → 本机已有工具足够，**不用装社区组**；
- 要交叉验证 jadx 反编译质量（lambda/泛型/新 class）→ 装 Vineflower + dex2jar；
- 要处理 `.aab` 而不是 `.apk` → 装 bundletool；
- 要离线跑 native 函数算法（签名/校验）→ 装 unicorn/capstone，或直接用 Frida 在真机跑；
- **不装**：修改成品、加载器、闭源收费工具、MCP 套件（本机没接）。

## §5 安全与体积

- 全部来自 GitHub release / PyPI 官方源（`ghfast.top`/`gh-proxy` 镜像、阿里云 PyPI），不装论坛“修改版”；
- 体积合计约 60MB（已下载缓存到 `/root/tools/toolcache` 的会优先复用）；
- 不用的工具不装，不拖慢自检（`toolcheck.sh` 把它们列在“可选”区，缺了只黄色提示）。
