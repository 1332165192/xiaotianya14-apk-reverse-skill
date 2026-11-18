# 工具链清单（本机已验证）

| 工具 | 版本/安装 | 用途 |
|---|---|---|
| `java` | OpenJDK 21（`/usr/bin/java`） | jadx/apktool/apksigner/keytool 运行时 |
| `apktool` | 2.7.0（apt） | 解包/重打包（**必须 `--use-aapt2`**） |
| `jadx` | 1.5.1（`/root/jadx/bin/jadx`，github 下载） | Java 源码反编译（源码交付物） |
| `apksigner` / `zipalign` | apt | 对齐、v1/v2/v3 签名、验签 |
| `aapt` / `aapt2` | apt（ARM64） | badging/清单导出（**aapt2 过旧，见坑区**） |
| `python3` / `unzip` / `zip` / `keytool` | 自带 | 脚本、拆包、keystore |
| `frida` / `frida-tools` | **已装** 17.26.2（`frida` 已在 PATH）| 动态 Hook：权益判定/数值/响应（需用户 root 起 frida-server）|
| `frida-server` | **已下载** `/root/tools/frida-server-17.26.2-android-arm64` | 设备端；用户 root 终端拷到 `/data/local/tmp` 启动 |
| `androguard` / `lief` / `blackboxprotobuf` | **已装**（pip）| dex/APK 解析、.so 读写、protobuf 存档解析 |
| `sqlite3` / `jq` / `xxd` / `xz` | **已装**（apt）| 改存档数据库、JSON、十六进制、解压 |
| `radare2` / `binutils` | **已装**（r2 5.5.0 / strings 2.42）| `.so` 分析/改指令、`strings` |
| `mitmproxy` | **已装** 12.3.1（`mitmdump` / `mitmweb` 在 PATH）| 抓 HTTPS 看服务端权益/数值接口、改响应（证书+代理见 `protection-map.md` §六）|
| `apk-mitm` | **已装** 1.3.0（node 全局，`apk-mitm` 命令）| 重打包自动改 `network_security_config` 信任用户 CA，绕 Java 层证书固定（§六 路径 B）|
| `tcpdump` / `ngrep` | **已装** 4.99.4 / 1.47.1（apt）| 不走系统代理的原始流量：Flutter/自定义协议/QUIC，pcap 落盘再分析；**proot 内无 CAP_NET_RAW，真机抓包在 root 侧跑** |
| `apkid` / `binwalk` | **已装** apkid 3.2.0 / binwalk 2.3.3（apt 版；pip 的 2.1.0 是残缺 stub 已弃用）| 加固壳/混淆一键识别；扫 APK/.so 里的嵌套 dex、加密 payload |
| `CFR` / `smali3` | **已装** CFR 0.152（`java -jar /root/tools/jars/cfr.jar <jar>`，吃 jar/class 不吃 dex）；`smali3` / `baksmali3` 3.0.9（PATH 直接调）| 新 dex 指令集反编译/回编（baksmali3/smali3）、SDK jar 源码恢复（CFR）|
| `objection` | **已装** 1.12.5（`objection -g <包名> explore`）| Frida 封装：`android sslpinning disable` 一键解证书固定（需先起 frida-server）|

> `unidbg`/`Ghidra` **本机不装**（理由与替代见 `references/mobile-toolchain.md`「深度逆向与抓包工具」）；同批装了 `yara` 4.5.0、`hermes-dec` 0.1.8、`protoc` 3.21.12。

**手机端 App（非 CLI）**按需装，挑法见 `references/android-app-tools.md`：只装 App Manager / LibChecker / PCAPdroid 这类开源工具，
不装修改成品/加载器；多数活 CLI 已经能做，别堆 App。

**缺工具不用手动装**：跑 `bash scripts/install_tools.sh`，它按「本地缓存 → 镜像/官方源」自动补齐
（apt 类、pip 类、frida-server、jadx），完事自动跑 `toolcheck.sh` 验一遍。
下载链接与镜像说明见 `references/mobile-toolchain.md`；本机缓存目录 `/root/tools/toolcache`（有离线包先用）。

安装/修复命令见 `references/mobile-toolchain.md`。关键事实：**jadx 不在 apt 源**，要从 GitHub 下载（用 `gh-proxy.com` 镜像）；**build-tools 34 的 aapt2 是 x86_64，ARM 手机跑不了（SIGILL）**，只能用系统 aarch64 aapt2 + apktool 2.7；**pip 装 frida 要用官方源**（清华镜像对 frida wheel 返回 403），装完先 `export PATH="/opt/python/bin:$PATH"`（`frida`/`frida-ps` 默认不在 PATH）。
