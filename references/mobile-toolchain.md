# 手机端工具链（proot Ubuntu · ARM64）

> 本机 = Android 手机上的 proot Ubuntu 24.04（ARM64），无沙箱后端，bash 一律 `danger-full-access`。
> **proot 内没有任何提权能力**；真机 root 通道 = **无线调试**（adbd 是 root，KernelSU `u:r:ksu:s0`）；端口随机（实测 `127.0.0.1:42777`，5555 仅 `adb tcpip` 模式示例），脚本自动发现，可 `--serial`/`ADB_SERIAL` 指定。
> 装/卸/日志/抓包/frida 优先走 `scripts/adb_device.sh`（见 device-verify.md §一），MCP 手机工具是兜底。

## 环境事实

| 事实 | 说明 |
|---|---|
| 架构 | aarch64；x86_64 二进制会 SIGILL（exit 132） |
| 真机 adb（端口会自动变） | `/usr/bin/adb`；**无线调试端口随机**（实测 `127.0.0.1:42777`，5555 只是 `adb tcpip 5555` 模式示例）。4 个 adb 脚本自动发现 serial（可 `--serial`/`ADB_SERIAL`），连上即 root（KernelSU）。**不是常驻**：关开关/切换/重启就没了；开工/收工都用 `scripts/device_adb_guard.sh status` **只检查两个开关值**（只读），关闭由用户手动（AI 不自动关，见 `adb-security.md`） |
| 输入法风险 | 中文输入法（拼音/双拼/九键）会把输入的英文组合成中文：网址走 `device_input.sh url` / `open(url=)`，文本走剪贴板，别用 type 硬打（见 `ime-typing.md`） |
| `/sdcard` | FAT，**没有执行位**；工具放 `/root` 下；工作目录可用 `/sdcard/Download/deapk-work` |
| 网络 | GitHub 直连常超时，用 `https://gh-proxy.com/` 前缀镜像 |
| apt 源 | 阿里云镜像，有 universe；**jadx 不在源里** |
| 工作目录 | 工作区建议放 `/sdcard/Download/`（可写） |
| adb | `/usr/bin/adb`（Android Debug Bridge 1.0.41）；真机无线调试随机端口（实测 `127.0.0.1:42777`；**root**：`id -u=0`，`u:r:ksu:s0`）|
| adb 设备名坑 | `adb devices` 里若出现 `emulator-5554`，是**这台真机的显示名，不是模拟器**（本机曾出现）；自动发现会跳过 `emulator-*`，脚本也显式拒绝它，请用无线调试的 `127.0.0.1:<端口>` |
| adb 安全 | adb root = 整机 root：收工**只检查 + 提醒用户手动关无线调试/拔线**（AI 不自动关）；⚠️ 别在公共网络开调试端口（tcpip 5555/无线调试）；`uninstall`/`clear` 丢数据先征得同意 |
| adb 调试开关（settings key）| `settings get global adb_enabled` = 设置里「USB 调试」开关（1=开 / 0=关）；`adb_wifi_enabled` = 「无线调试」开关（部分 ROM 返回 `null`，表示该键不单独暴露）|
| 关闭通道（用户手动） | `device_adb_guard.sh status` 只读检查两个开关值并提醒；`close` **只打印手动关闭步骤**（不改 settings、不跑 `adb usb`）；AI 不自动关。**`adb usb` ≠ 关开关**（设置里开关仍开着）。恢复：`open-hint` 看设置路径/配对步骤，开/关都由用户手动（AI 不改 settings） |
| 界面操控 | adb 在线优先 `scripts/device_ui.sh`（`foreground/launch/dump/tap/swipe/key/text/screen/wait/apps`，基于 uiautomator + input）；视觉（MCP screen/截图）只做确认与看自绘页，见 `device-control.md` |

## 安装/修复命令

```sh
# 基础（一般已有）：java 21 / apktool 2.7.0 / apksigner / zipalign / aapt / aapt2 / python3
which java apktool apksigner zipalign aapt aapt2 python3

# jadx 1.5.1（GitHub + 镜像）
cd /root
curl -sL --max-time 900 -o jadx.zip https://gh-proxy.com/https://github.com/skylot/jadx/releases/download/v1.5.1/jadx-1.5.1.zip
unzip -oq jadx.zip -d jadx && chmod +x jadx/bin/jadx
/root/jadx/bin/jadx --version

# 可选：.so 分析与 strings
apt-get install -y --no-install-recommends radare2 binutils

# 可选：Android 平台工具（zipalign/apksigner 已装可跳过）
apt-get install -y --no-install-recommends apksigner zipalign
```

## 关键坑与对策

1. **aapt2 版本太旧**：Ubuntu 的 aapt2 不认新版 Material 的 `$mtrl_*`/`$avd_*` 资源名 → `fix_dollar_resources.py` 重命名 + 修 public.xml/引用（资源 ID 不变，smali 数字引用不受影响）。
2. **apktool 2.11 自带 aapt2 是 x86_64** → SIGILL；**用 apt 的 apktool 2.7.0 + `--use-aapt2`**（走 PATH 里的 aarch64 aapt2）。
3. **framework 缓存损坏**（`RES_TABLE_TYPE_TYPE entry offsets overlap`）→ `rm -rf ~/.local/share/apktool/framework` 重建；`build_sign.sh` 已自动处理。
4. **build-tools 34 的 aapt2 x86_64 别下载**（跑不了）。
5. **`$` 资源名修复**：`python3 scripts/fix_dollar_resources.py <解码目录>`（幂等，可重复跑）。
6. **jadx 反编译慢**：7MB dex 约 5-15 分钟；后台跑（run_in_background），先干别的；`--show-bad-code` 容忍部分类报错。
7. **apktool 解码慢**：7000+ smali 可能 10-30 分钟；解码期间可并行做 jadx/分析；后台任务别重复启动。
8. **/root/.local/share/apktool/framework 会在首次打包时自动生成**，不需要手动放 framework。
9. **zip/unzip 可用**；大文件操作用 `/sdcard/Download/` 交付。

## 真机动态能力（adb root 通道，AI 可直接驱动）

- 本机有 KernelSU/Shizuku/LSPosed（见用户设备）；**proot 内无法执行 `su` / 无 `CAP_NET_RAW`**，
  但 `adb -s <自动发现的 serial> shell`（实测 `127.0.0.1:42777`）就是真机 root，所以动态能力走 adb：
  ```sh
  bash scripts/adb_device.sh check          # 检测 adb/设备/root/frida-server/tcpdump（退出码 0 = 可用）
  bash scripts/adb_device.sh frida start    # 起 frida-server（27043），约 15s 内自动验证
  bash scripts/adb_device.sh tcpdump start -i any   # 真机抓包（设备端 /system/bin/tcpdump）
  ```
- 用户确认授权后即可用；**仍是可选增强**：默认验证走 MCP 手机工具 + 界面观察（见 device-verify.md），
  adb 不可用时才请用户在 Termux 手动起（`frida_server_prep.sh`）。
- 端口：**27043** 是脚本用的测试实例；**27042 可能被宿主占用实例**，不用/不杀。

## 分析权益逻辑 / 改数值要补的工具（实测可装）

| 工具 | 装法 | 用途 |
|---|---|---|
| `frida` / `frida-tools` | `pip install frida frida-tools -i https://pypi.org/simple` | 动态 Hook：找判定点、看加密字符串/存档、改内存/响应（需 root 起 frida-server，见 protection-map.md §七） |
| `frida-server`（arm64） | GitHub releases 下载，用户 root 终端启动 | Frida 服务端；**版本必须与 pip 包一致** |
| `androguard` | `pip install androguard -i https://pypi.org/simple` | 纯 Python 解析 APK/dex，写脚本批量找类/方法/常量 |
| `sqlite3` | `apt-get install -y sqlite3` | 读写 `/data/data/<pkg>/databases/*.db`（存档） |
| `radare2` + `binutils` | `apt-get install -y radare2 binutils` | `.so` 反汇编/改指令、`strings` |
| `mitmproxy`（已装） | 12.3.1（`mitmdump`/`mitmweb` 在 PATH）；重装 `pip install mitmproxy -i $PIP_INDEX` | 抓服务端权益/数值接口；证书+代理见 protection-map.md §六 |
| `protobuf`（可选） | `pip install protobuf` / `protoc --decode_raw` | 解析 protobuf 存档/响应 |

> **pip 源坑**：默认清华镜像 `pypi.tuna.tsinghua.edu.cn` 对 `frida` 的 wheel 返回 403（实测），
> 装 frida 时用官方源 `-i https://pypi.org/simple`；镜像只适合装普通包。
> `frida` 有 `manylinux_2_17_aarch64` wheel，手机 ARM64 可直接装（38 MB 左右，耐心等）。
>
> **PATH 坑（实测）**：pip 装到 `/opt/python/bin`，`frida`/`frida-ps` 不在默认 PATH 里，
> 先 `export PATH="/opt/python/bin:$PATH"`；Python 里 `import frida` 不受影响。
>
> 本机已验证版本：`frida 17.26.2` / `frida-tools 14.13.1` / `androguard 4.1.4`（都能装能跑；
> `frida` 连服务端需用户 root 起同版本 frida-server，见 protection-map.md §七）。

## 适配/数值流程额外注意

1. **先扫后改**：`scan_premium.py` 给出候选 → `patch_method.py find` 精确定位 → `--dry-run` 预览。
2. **改前备份**：`.bak` 由 `patch_method.py` 自动生成；整包也备份到 `/sdcard/Download/`。
3. **动态验证优先**：判不准时先用 Frida 在真机上 Hook 确认，再落静态补丁（不依赖 root 常驻）。
4. **Frida 客户端与服务端版本对齐**：`frida --version` 与 `frida-server` 版本号必须一致，否则连不上。
5. **重打包仍是唯一交付形态**：Frida 只用于定位验证，交付给用户的还是改完签名的 APK。

## 本机预装清单（2026-11-11 已验证，可直接调用）

| 工具 | 命令/路径 | 版本 |
|---|---|---|
| java | `java` | OpenJDK 21 |
| apktool | `apktool` | 2.7.0（配 `--use-aapt2`）|
| jadx | `jadx`（已软链到 `/usr/local/bin/jadx`，真身在 `/root/jadx`）| 1.5.1 |
| aapt / aapt2 / apksigner / zipalign | 同名命令 | Ubuntu 24.04 apt 版（aarch64）|
| smali / baksmali | `smali` / `baksmali` | 2.5.2 |
| frida 客户端 | `frida` / `frida-ps` / `frida-trace`（已软链到 `/usr/local/bin`）| 17.26.2 |
| frida-server（设备端）| `/root/tools/frida-server-17.26.2-android-arm64`（81 MB，已解压）| 17.26.2（与客户端一致）|
| androguard | python `import androguard` | 4.1.4 |
| lief | python `import lief` | 1.0.0（ELF/.so 读写）|
| blackboxprotobuf | python `import blackboxprotobuf` | 1.0.1（protobuf 存档/响应解析）|
| adb | `adb`（`/usr/bin/adb`）| 1.0.41（apt `android-tools-adb`；真机无线调试随机端口（实测 `127.0.0.1:42777`）为 root，见上节）|
| sqlite3 | `sqlite3` | 3.45.1（改存档数据库）|
| radare2 | `r2` | 5.5.0（.so 反汇编/改指令）|
| binutils | `strings` | 2.42 |
| xxd / jq / xz | `xxd` / `jq` / `xz` | 均可用（十六进制/JSON/解压）|
| mitmproxy | `mitmdump` / `mitmweb`（已软链到 `/usr/local/bin`）| 12.3.1（pip 装，抓包用）|

> 抓包/深度逆向二梯队（mitmproxy · apk-mitm · objection · apkid · binwalk · yara · CFR · smali3 · hermes-dec）见下节
> 「深度逆向与抓包工具」；本节只列开工必用的第一梯队。

自检命令（新会话开工先跑）：
```sh
bash scripts/toolcheck.sh          # 退出码 0 = 必需工具齐
```

> `frida` 客户端在 PATH 里可直接用；`frida-server` 是**设备端**程序，proot 内不能运行，
> 需要用户 root 终端把它拷到 `/data/local/tmp` 并启动（见 protection-map.md §七）。

## 深度逆向与抓包工具（2026-11-12 补装）

> 二梯队工具：看服务端接口、啃加固、处理新 dex 指令集。安装/验证记录见 `/root/tools/toolreport.json`；
> pip 类装在 `/opt/python/bin`（已软链到 `/usr/local/bin`，默认 PATH 直接能调）。
> 用之前先 `bash scripts/toolcheck.sh` 看当前状态，**下表标「不可用/未装」的别当已就绪用**。

| 类别 | 工具 | 路径或命令 | 版本 | 用途 | 安装命令或链接 |
|---|---|---|---|---|---|
| 抓 HTTPS | mitmproxy | `mitmdump` / `mitmweb`（`/opt/python/bin`，已软链 `/usr/local/bin`） | 12.3.1 | 解密请求/响应、改包、落 flow 文件 | 自动（`install_tools.sh --pip`）；实测 aarch64 wheel 免编译 |
| 原始流量 | tcpdump | `tcpdump`（`/usr/bin/tcpdump`） | 4.99.4 | `-w x.pcap` 抓非 HTTP/QUIC/底层协议（mitmproxy 解不了的） | `apt-get install -y tcpdump`；**proot 内抓不了，见下方坑** |
| 流量文本过滤 | ngrep | `ngrep`（`/usr/bin/ngrep`） | 1.47.1-git | 按正则直接看 payload（明文接口/老服务端一秒定位） | `apt-get install -y ngrep` |
| 信任用户 CA | apk-mitm | `apk-mitm app.apk`（node 全局，`/usr/local/bin/apk-mitm`） | 1.3.0 | 自动改 manifest + `network_security_config` 信任用户 CA，重签输出 `app-mitmed.apk`（绕 Java 层证书固定） | 自动（`--re`）；重装 `npm i -g apk-mitm`（需 node，本机自带） |
| 不重打包抓包 | frida | `frida -H 127.0.0.1:27043 -f <包名> -l unpin.js` | 17.26.2 | Hook 响应/证书固定/native SSL（C1-C3 模板见 `protection-map.md` §6.3、`dynamic-hook-help.md`） | 自动（`--pip`）；server 用 `bash scripts/adb_device.sh frida start` 自动起（27043；27042 可能被宿主占用实例）|
| 一键解证书固定 | objection | `objection -g <包名> explore` → `android sslpinning disable` | 1.12.5 | Frida 封装：一条命令关掉 OkHttp/native 常见 pinning（需先起 frida-server） | 自动（`--re`）；`pip install objection -i $PIP_INDEX` |
| 加固识别 | apkid | `apkid app.apk`（`-j` 出 JSON） | 3.2.0 | 一键识别壳/混淆/packer/anti-debug（比手 grep 快且不漏） | 自动（`--re`）；`pip install apkid -i $PIP_INDEX`；CLI 无 `--version`，用 `pip show apkid` 查版本 |
| 嵌套/异常包 | binwalk | `binwalk app.apk` | 2.3.3（apt 包 2.3.4+dfsg1-5） | 扫 APK/.so 里的嵌套 zip、加密 dex、附加 payload | 自动（`--re`，apt 装）；**pip 版 2.1.0 是残缺 stub，已弃用** |
| 特征扫描 | yara | `yara rule.yar app.apk` | 4.5.0 | 批量匹配加固/广告/壳特征（自写规则，比散落 grep 可维护） | `apt-get install -y yara` |
| 反编译（jar/class） | CFR | `java -jar /root/tools/jars/cfr.jar <sdk.jar\|A.class> --outputdir out` | 0.152 | 反编译 jar/新版本 class（SDK 混淆、jadx 卡住时交叉验证）；**不能直接吃 .dex**（实测 `Magic != Cafebabe`）| `curl -L -o /root/tools/jars/cfr.jar https://www.benf.org/other/cfr/cfr-0.152.jar` |
| 新 dex 指令集 | smali3 / baksmali3 | `baksmali3 d classes.dex -o smali/`（反编译）/ `smali3 a smali/ -o out.dex`（回编译）；包装脚本已带依赖 classpath | 3.0.9 | 换掉 apt 的 2.5.2：新 dex 指令集（API 35+）只有它能读/能回编；实测 8.8MB dex → 6576 smali → 回编 8.8MB 通过 | 由 `install_tools.sh --re` 自动装 **fat jar**（`smali-3.0.9-fat.jar` / `baksmali-3.0.9-fat.jar`，自带依赖，来自 baksmali/smali release；google/smali release 无 jar 资产、Maven thin jar 无 Main-Class 需 classpath） |
| RN Hermes 反编译 | hermes-dec | `hbc-decompiler index.android.bundle out.js`（输出是位置参数；`hbc-disassembler` 看字节码） | 0.1.8 | React Native 应用：Hermes 字节码还原成可读 JS（广告/会员逻辑常在 bundle 里） | 自动（`--re`）；`pip install hermes-dec -i $PIP_INDEX` |
| 响应/存档解析 | protoc | `protoc --decode_raw < resp.bin` | 3.21.12 | 不用 schema 直接看 protobuf 响应/存档字段 | `apt-get install -y protobuf-compiler` |
| JNI 模拟（可选） | unidbg | — | **未装** | 不依赖真机直接跑 APK 的 native 方法（签名算法、JNI 校验、so 解包还原） | **需联网安装**：项目无官方 jar 资产，得 `git clone https://github.com/zhkl0228/unidbg` + Maven 构建（依赖 1GB+，手机不划算）|
| 原生反编译 | Ghidra | — | **不装** | 官方 release **没有 linux-arm64 的反编译后端**（Decompiler 是原生二进制，只出 x86_64/win/mac）；自行编译要数小时，手机屏/内存也不适合 | 不装；native 分析用 `radare2`（`r2 -A lib.so`）/`objdump -d`/`strings` 代替 |

**mitmproxy 证书**：首次启动生成 `~/.mitmproxy/mitmproxy-ca-cert.pem` / `.cer`（本机已实测生成）。
Android 7+ 不信任用户 CA，要装进系统证书：`openssl x509 -inform PEM -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem`
算哈希 → 改名为 `<hash>.0` 放进 `/system/etc/security/cacerts/`（root + 重启；Android 14+ 见坑）；
或直接走 apk-mitm 让 APK 信任用户 CA。完整步骤见 `protection-map.md` §六 6.1/6.2。

**tcpdump/ngrep 在 proot 里抓不了**（实测：无 `CAP_NET_RAW`，`-i lo` 直接 `Operation not permitted`）。
真机抓包只能在 **root 侧**跑：Termux 里 `su -c 'tcpdump -i any -s0 -w /sdcard/Download/x.pcap'`，
落盘后回 proot 用 `tcpdump -r` / `wireshark`（无 GUI 就看 `strings`）分析；`ngrep` 同理。

**三件套怎么配**：mitmproxy 负责「解」，tcpdump/ngrep 负责「解不了的」，apk-mitm 负责「让 App 愿意被解」。
证书安装、三条路径选型与风险红线见 `protection-map.md` §六。

**什么时候用 CFR / smali3**：三者分工别搞混——
- jadx 卡在新 opcode（`invoke-polymorphic`、`MethodHandle`）或 `--show-bad-code` 后仍缺类 → 用 **`baksmali3 d`**
  反编译成 smali（比 jadx 更早支持新指令集），看完再 `smali3 a` 回编（apt 的 2.5.2 对新指令会报错）；
- 要恢复 **SDK 的 jar/新版本 class** 源码（jadx 对高版本 class 常崩）→ 用 **CFR**：
  `java -jar /root/tools/jars/cfr.jar sdk.jar --outputdir /tmp/cfr-out`；
- CFR **不能直接读 .dex**（实测 `Magic != Cafebabe`），dex 先 `baksmali3 d` / jadx 处理。

## 工具下载链接与自动安装（换机/重装后用）

skill 本体不带二进制（那样包会到 100MB 左右，加载和分享都变慢）。
正确的做法是**缺什么自动下**：

```sh
bash scripts/install_tools.sh          # 一条命令补齐全部必需工具，装完自动 toolcheck
bash scripts/install_tools.sh --check  # 只看缺什么 + 打印下载链接
bash scripts/install_tools.sh --apt / --pip / --frida / --jadx   # 只补某一类
bash scripts/install_tools.sh --re     # 只补深度逆向/抓包：apkid/binwalk/hermes-dec/objection/apk-mitm/CFR/smali3
```

安装顺序是「本地缓存 → 镜像/官方源」：
- 缓存目录 `/root/tools/toolcache`（有 `wheels/`、`frida-server-*.xz`、`jadx-*.zip` 就先离线装）；
- `PIP_INDEX` 默认 `https://mirrors.aliyun.com/pypi/simple`（实测能下 frida 的 aarch64 wheel；
  **清华镜像对 frida wheel 返回 403**），失败自动回退 `https://pypi.org/simple`；
- `GH_PROXY` 默认 `https://gh-proxy.com/`（GitHub 直连常超时），失败回退直连。

| 工具 | 下载链接 | 安装方式 |
|---|---|---|
| frida / frida-tools / androguard / lief / blackboxprotobuf | `pip install ... -i $PIP_INDEX` | 自动（`--pip`） |
| frida-server（arm64） | `https://github.com/frida/frida/releases/download/<frida版本>/frida-server-<frida版本>-android-arm64.xz` | 自动（`--frida`，版本跟 pip frida 对齐） |
| jadx 1.5.1 | `https://github.com/skylot/jadx/releases/download/v1.5.1/jadx-1.5.1.zip` | 自动（`--jadx`，解压到 `/root/jadx`） |
| sqlite3 / radare2 / binutils / xxd / jq / xz | `apt-get install -y sqlite3 radare2 binutils xxd jq xz-utils` | 自动（`--apt`） |
| mitmproxy（已装） | `pip install mitmproxy -i $PIP_INDEX` | 自动（`--pip`；12.3.1 有 aarch64 wheel，不需要编译链）|
| apkid / hermes-dec / objection / apk-mitm | `pip install apkid hermes-dec objection` / `npm i -g apk-mitm` | 自动（`--re`）|
| binwalk / yara / protobuf-compiler | `apt-get install -y binwalk yara protobuf-compiler` | 自动（`--re`，apt）|
| CFR 0.152 / smali+baksmali 3.0.9 | `https://www.benf.org/other/cfr/cfr-0.152.jar`、Google Maven `com.android.tools.smali:smali:3.0.9`（GitHub release 无 jar 资产） | 自动（`--re`，装到 `/root/tools/jars/`）|

环境限定：aarch64 · proot Ubuntu 24.04 · Python 3.12。换 PC/x86 时 apt/pip 能装，frida-server 要换
对应架构的包，jadx/apktool 需要 Java。
