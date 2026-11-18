# 加固/保护识别与对策

## 一、加固壳识别

| 加固厂商 | 特征文件/类 | 备注 |
|---|---|---|
| 360 加固 | `libjiagu*.so`、`com/stub/StubApp`、`com/qihoo/util` | 真实 dex 加密在壳里 |
| 腾讯乐固 | `libshell*.so`、`com/tencent/StubShell` | |
| 梆梆 | `libDexHelper.so`、`com/secneo/apkwrapper` | |
| 爱加密 | `libexec.so`、`s.h.e.l.l` 相关类 | |
| 网易易盾 | `libnesec.so` | |
| 娜迦 | `libnaga*.so` | |
| 阿里聚安全 | `libmobisec.so`、`com/ali/mobisecenhance` | |
| 顶象 | `libx3g.so` 等 | |
| Google pairip | `com/pairip/licensecheck/*`、`com.android.vending.derived.apk.id` meta | 授权校验壳（我们已实测放行方案） |
| StringFog | `$/$` 类 + native 解密方法 + `System.loadLibrary("xxx")` | 字符串加密 |

识别命令：
```sh
ls smali/com/ | grep -iE 'stub|shell|jiagu|naga|secneo|mobisec|pairip'
unzip -l base.apk | grep -E 'libjiagu|libshell|libDexHelper|libnesec|libmagi'
grep -rn 'System.loadLibrary' smali --include='*.smali' | grep -vE 'google|androidx'
```

## 二、常见对策

| 保护 | 静态对策 | 动态对策（可选） |
|---|---|---|
| 加固壳（dex 加密） | 广告逻辑若在壳外/资源/Flutter 层，直接跳过解包还原 | FART/BlackDex/Frida dump（需 root） |
| StringFog 字符串加密 | 不啃算法：用资源字符串、资源 ID、结构/调用链定位 | Hook 解密方法打印字符串 |
| pairip 授权 | npm/Release 包不含自动脚本；按 `references/patch-patterns.md` §五 手动补 5 处 | — |
| 签名校验 | 找证书 hash 比较/`PackageManager.getPackageInfo` 校验点 → 改判定 | Hook 校验方法 |
| 反调试 | 一般不影响重打包后功能；真受阻再 patch `Debug.isDebuggerConnected` 判定 | Frida 隐藏 |
| root 检测 | 目标本身不改 root 判定（广告组件清理不需要） | Shamiko/Magisk Hide |
| SSL Pinning | 广告组件清理不需要抓包时跳过 | OkHttp `CertificatePinner.check` hook |

## 三、本机（手机 proot）动态能力边界

- **proot 内不能提权**（普通 app uid）：`su` 不可用、没有 `CAP_*`，**要 root 只能走 adb**。
- **真机 root 通道（首选）**：手机开无线调试后，`adb -s <自动发现的 serial> shell`（实测 `127.0.0.1:42777`；
  5555 只是 `adb tcpip` 模式示例）就是真机 root
  （Android 17 / KernelSU，`u:r:ksu:s0`）。一键检测：`bash scripts/adb_device.sh check`；
  安装/日志/启停/清数据/截图/抓包命令见 `device-verify.md` §1.2。
- **Frida 方案 0（adb 自动，首选）**：`bash scripts/adb_device.sh frida start`（端口 **27043**）→
  `frida -H 127.0.0.1:27043`；`frida stop` 收工。用户不用动 Termux，但仍须先按 SKILL.md §9.4 告知并取得同意。
- **Frida 方案 1（Termux 兜底）**：adb 不可用时，用户 root 终端把 `frida-server`（arm64）放 `/data/local/tmp` 启动，
  proot 内连 **27043**（操作卡：`bash scripts/frida_server_prep.sh`）。
  - 前提：用户明确同意、设备已授权、仅用于其自有应用。
- **LSPosed/Shizuku** 可用但需用户在系统侧授权，agent 不擅自操作。
- **安全**：adb root = 整机 root；收工关无线调试/拔线；⚠️ 别在公共网络开调试端口（tcpip 5555/无线调试）。

## 四、Flutter 专项

- 工具：`blutter`（Dart AOT 分析，需匹配 Dart 版本编译；ARM64 Linux 环境可尝试源码构建，耗时 15min+）。
- 无 blutter 时的低门槛路径：`strings libapp.so | grep -iE 'ad|banner|slot|reward'` 找插槽键/API；
  等长字符串替换（保偏移）→ 重打包签名 → 真机验证。
- **API 路径字符串绝不能替换**（换掉会 404 → 启动卡死，见 field-journal 踩坑）。

## 五、完整性 / 运行时安全校验校验（改包前先过）

`scan_premium.py` 第 7 节会列命中的校验类型；命中了就先处理，否则功能补丁一启动就闪退。

| 校验类型 | 特征字符串/类 | 对策 |
|---|---|---|
| 签名校验 | `getPackageInfo` + `GET_SIGNATURES`/`GET_SIGNING_CERTIFICATES`、`MessageDigest`、证书 hash 比较 | 找比较点改判定恒真；或把原签名证书替换成自己的（`original/META-INF` 不参与） |
| Play Integrity / SafetyNet | `IntegrityManager`、`SafetyNet`、`attest`、`PlayCore` | 服务端校验无法静态适配；把校验调用 no-op（会失去部分功能）或放行失败分支 |
| 调试检测 | `isDebuggerConnected`、`Debug.isDebuggerConnected` | 判定恒真放行或删调用 |
| root 检测 | `/system/xbin/su`、`magisk`、`Superuser` 路径、`Runtime.exec("su")` | 判定恒假；用户 root 环境用 Shamiko/Magisk Hide 隐藏 |
| Xposed/LSPosed 检测 | `xposed`、`lsposed`、`de.robv.android`、`ClassLoader` 扫包 | 判定恒假；LSPosed 隐藏列表排除目标 App |
| Frida 检测 | `frida`、`gum-js`、`/proc/self/maps` 扫 `frida`、`27042`/`27043` 端口 | frida-server 改名/换端口（如 8888），或先 hook 检测点再动态加载 |
| ptrace 检测 | `ptrace`、`TracerPid` | 改判定；或用隐藏型动态加载 |
| 模拟器检测 | `goldfish`、`generic`、`ro.kernel.qemu` | 判定恒假 |
| native 完整性 | `.so` 自校验、`libmtprotect` 之类 | r2 定位校验函数改返回；或 Frida native hook |
| 备份/篡改检测 | `allowBackup`、文件校验和 | 见 value-logic-analysis §7 |

> 改完签名后，**签名校验类**几乎一定会触发；这是重打包最常见闪退原因（见 SKILL.md §6）。

### 5.1 APK 文件级完整性（实测：MT管理器 / MT_Protector）

**症状**：改包后一启动就 `java.lang.UnsatisfiedLinkError: No implementation found for void …<clinit>() (Native Method)`，
logcat 里还伴随 `W/<pkg>: Unsupported class loader: java.lang.Class<…>`；栈顶是 Application 类 `<clinit>` → AppComponentFactory。

**四级实验法（先做，10 分钟定性，别直接逆向）**：
| 试验 | 做法 | 崩/不崩说明 |
|---|---|---|
| ① | 原包只重签 | 崩 → 签名/签名方案校验 |
| ② | 原包不 zipalign 只重签 | 仍崩 → 与对齐无关 |
| ③ | 仅 v2/v3（关 v1） | 仍崩 → 与 v1 无关 |
| ④ | root 替换**已安装**的 `/data/app/**/base.apk`（本地重新打 zip、**保留原签名主体、dex 不变**） | ④也崩 → **APK 文件/zip 结构级校验**（本节）；只有改代码才崩 → 代码完整性；①②崩④好 → 签名校验 |

**结论（实测）**：MT_Protector 类壳校验的是 APK 文件完整性本身，与签名无关、与 dex 内容无关；
只要 APK 被重新打包（zip 重建/对齐变化）就触发，它会故意不注册 native 方法让类初始化失败（把“检测到修改”伪装成链接错误）。
→ 这类壳的**改包+重签路线不可行**。

**补测（v2.26.11）：校验实为"签名相关"而非内容哈希**
- 保留原 **APK Signing Block** + root 替换已安装 `base.apk`（PM 缓存签名仍是官方签名）→ 内容随便改（dex 全换）都能启动；
- 重签（PM 签名变）→ 崩；重打 zip 丢签名块 → 崩。
- 所以：**自用（设备有 root）**可走"保留签名块重建 + root 覆盖 base.apk + 清 oat"路线（脚本见 journal）；
  **要产出可安装 APK** 则只能 patch 壳的签名校验（lib 补丁）或 LSPosed 模块。

**对策（按成本从低到高）**：
1. **同版本官方包 vs 修改包 lib 逐字节 diff**（最省事）：修改版通常只改壳 so 的几个字节（函数入口 `mov w0,#1; ret`、NOP、单指令替换），
   拿到偏移后在官方包上复刻 → 重签 → 真机验证。实测 v2.26.9 共存版：官方 2,894,808 字节，仅 191 字节/18 处不同，全套偏移见 journal。
2. 运行时补丁：动态加载小 dex / Application hook / 反射改字段（共享版修改常用：`getField`+`setBoolean`）；
3. LSPosed/Xposed 模块；
4. 无参考包时 patch 壳的校验点：`libmtprotect.so` 的 `JNI_OnLoad` 是 ~166KB 单体函数（CFF+字符串加密），
   静态 patch 成本高，需 root adb + logcat/frida native hook 配合定位。
   （只改 7 处 return-true 不够，要连同 stub/单指令一起补，实测差异 18 处全补才通过。）

**快速迭代环境**：手机开无线调试（端口随机，实测 42777；5555 仅 `adb tcpip 5555` 模式）→ proot `apt install android-tools-adb` → `adb connect 127.0.0.1:<无线调试端口>`（脚本会自动发现；手机弹 RSA 授权点允许）
→ 一键自检 `bash scripts/adb_device.sh check`（装/卸/启停/logcat/清数据全封装，见 `device-verify.md` §一）
→ `adb shell` 直接 root（KernelSU 域）：`logcat` / `pm install` / `cp` 替换 `base.apk` / `rm -rf …/oat`，一轮 10 秒级。
注意 `adb devices` 里设备可能显示为 `emulator-5554`（不是真模拟器）。

（旧案例文件已删除——对应版本已被后续版本解决，留着会误导；流程与体检清单仍按本节与 §五 走。）

## 六、服务端校验与抓包（B / C 级必读）

当客户端放行后功能仍不可用，说明权益/数值在服务端。先判断服务端信任边界：

1. **响应只是展示** → 改响应/改本地展示即可。
2. **响应参与判定**（`if (resp.isVip) unlock()`）→ Hook 响应或改判定。
3. **请求带签名/HMAC**（`sign=`、`timestamp=`、`nonce=`、`deviceId=`）→ 客户端改参数会被服务端拒；
   只能改"客户端如何消费响应"，或 Hook 签名函数（需要知道算法）。
4. **服务端每次重下发** → 本地补丁只影响当次；要么 Hook 响应，要么承认做不到。

> **风险红线（动手前先读）**：只抓**用户自有 App** 的流量。**支付、充值、账号登录、银行/金融类一律不抓**
> （涉及资金和凭据，法律风险 + 容易把账号搞进风控）。抓到的 `Authorization`/`token`/`cookie`/手机号属于凭据：
> 不写进交付物、不发聊天、不落公共目录；抓完删 `~/.mitmproxy/`、`/tmp/flow.mitm`。系统证书会改变全机信任链，
> **抓完要卸证书、关代理**。不确定该不该抓 → 问用户，别自己决定。

工具版本/路径见 `mobile-toolchain.md`「深度逆向与抓包工具」。先按成本从低到高选路径：

| 路径 | 做法 | 适用场景 | 代价 |
|---|---|---|---|
| **A** | mitmproxy + 系统 CA + 手动代理 | 目标没做证书固定、设备有 root | 需 root 装系统 CA（Android 14+ 更麻烦），只能看到走系统代理的请求 |
| **B** | apk-mitm 重打包（改 `network_security_config` 信任用户 CA） | 目标做了 Java 层 pinning、或高 targetSdk 不信任用户 CA | 必须重签 → 触发签名校验（§五）；加固包大概率崩（§5.1） |
| **C** | Frida Hook（不重打包） | 不想动包、包有强完整性校验、native pinning | 需用户 root + frida-server（§七）；每个点要写脚本 |

### 6.1 路径 A：mitmproxy + 系统 CA + 代理

**适用**：只想快速看接口/改响应，目标没做 pinning。

```sh
export PATH="/opt/python/bin:/usr/local/bin:$PATH"   # pip 工具目录（已软链到 /usr/local/bin）
mitmdump --listen-host 0.0.0.0 -p 8080 -w /tmp/flow.mitm   # ① 起代理并落 flow
mitmweb --listen-host 0.0.0.0 -p 8080 --web-port 8081      # 或：网页界面看请求（浏览器开 :8081）
# ② 手机 设置 → WLAN → 当前网络 → 代理 → 手动：主机=手机局域网 IP，端口 8080
#    只在本机抓：proot 与 Android 共享网络命名空间，多数机型可填 127.0.0.1；不通再换局域网 IP
# ③ 装 CA：证书首次启动生成在 ~/.mitmproxy/，要有 root 才能进系统证书目录
ls ~/.mitmproxy/mitmproxy-ca-cert.pem ~/.mitmproxy/mitmproxy-ca-cert.cer
HASH=$(openssl x509 -inform PEM -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem | head -1)
# 有 root（用户 KernelSU 终端）：把 .pem 放进 /system/etc/security/cacerts/$HASH.0，chmod 644，重启
# ④ 验证：手机浏览器开 http://mitm.it —— 能看到证书页说明代理+证书链路通
# ⑤ 收工：删代理、卸证书、rm -rf ~/.mitmproxy /tmp/flow.mitm
```

要点与坑：
- **App 必须走系统代理**：OkHttp/URLConnection 默认读系统代理；**Flutter/Dart、部分自研网络栈会忽略系统代理** → 抓不到就来路径 C。
- **Android 7+（targetSdk≥24）默认不信任用户 CA**：装成"用户证书"对目标 App 无效，必须进系统证书目录（这就是路径 A 的意义）。
- **Android 14+**：系统 CA 实际在 `/apex/com.android.conscrypt/cacerts/`，直接改 `/system` 会被 APEX 覆盖 → 用 Magisk 证书模块（如 Move Certificates）搬运，或走路径 B。
- 非 HTTP/QUIC/UDP 协议 mitmproxy 看不到 → 真机原始抓包（**proot 内 tcpdump/ngrep 没有 `CAP_NET_RAW`，抓不了**）：
  - **首选 adb**：`bash scripts/adb_device.sh tcpdump start -i any` → 复现 → `bash scripts/adb_device.sh tcpdump stop`
    → `bash scripts/adb_device.sh tcpdump pull /tmp/cap.pcap`（拉回后自动用本地 tcpdump 解析前几包，
    再 `tcpdump -r /tmp/cap.pcap -nn` 细看）；
  - adb 不可用：Termux `su -c 'tcpdump -i any -s0 -w /sdcard/Download/x.pcap'`，回 proot 解析。
- HTTP/2 解析报错（老服务端/中间设备）：`mitmdump` 加 `--no-http2` 退回 HTTP/1.1。

**风险**：系统 CA 改变全机 TLS 信任链（有 root 的门槛就在这里），抓完必须卸；代理开着时**所有** App 流量都经过本机，
公共 Wi-Fi 上别开；装 CA 前后各记一次，方便回滚。

### 6.2 路径 B：apk-mitm 重打包，让 APK 信任用户 CA（绕证书固定）

**适用**：路径 A 装不上系统证书（Android 14+/无 root 全机风险），或目标 Java 层做了 pinning；能接受重打包。

```sh
# ① 打补丁：自动改 manifest + network_security_config（trust-anchors 加用户 CA、关 pinning 限制）并重签
apk-mitm app.apk                     # 输出 app-mitmed.apk
# 也可对已解码目录：apk-mitm decoded/ ；或指定证书：apk-mitm app.apk --certificate ~/.mitmproxy/mitmproxy-ca-cert.pem
# ② 需要统一签名（交付/覆盖安装）时用自家 keystore 重签：
bash scripts/build_sign.sh decoded/  # 与 apk-mitm 二选一，交付包一律走 build_sign.sh
# ③ 装 app-mitmed.apk → 设代理（同 6.1 ②）→ 开抓
```

**坑（这是路径 B 的主要成本）**：
- **重签必触发签名校验**（§五）：先看目标有没有签名校验/完整性校验；加固包尤其 §5.1 的 MT_Protector 类**直接无解** —— 先用 §5.1 四级实验法定性，别白干。
- apk-mitm 只改 **Java 层**证书配置；**native 层 pinning（BoringSSL/Flutter）改不动** → 落路径 C。
- 覆盖安装要同签名的包（先卸载会丢数据），改动清单另存备份。
- 目标还有 `debuggable` 需求时用 `apk-mitm app.apk --debuggable`（一箭双雕）。

**风险**：重签包**只给自己用、不分发**（等于改包分发）；签名变了会被风控/完整性校验标记，**登录类 App 别试**，
抓完删掉 mitmed 包、换回原包。

### 6.3 路径 C：Frida Hook（不重打包，三选一）

**适用**：不能/不想重打包；加固包；只需临时看一眼。`frida 17.26.2` 已装、frida-server 已下载，起服务见 §七。

| 选法 | Hook 点 | 能干什么 | 模板位置 |
|---|---|---|---|
| **C1 改响应** | `okhttp3.Interceptor#intercept`、`java.net.HttpURLConnection`、`Retrofit` converter | 内存里改响应体/字段（`isVip`/`coin`），不碰 TLS、不影响签名 | `entitlement-analysis.md` §4.2、`value-logic-analysis.md` §5.3 |
| **C2 解证书固定** | `okhttp3.CertificatePinner#check`、`X509TrustManager#checkServerTrusted`、`TrustManagerImpl#checkTrustedRecursive` | 让 App 接受 mitmproxy 证书（仍需按 6.1 装 CA/代理） | 下方最小模板 |
| **C3 抓明文 / native** | native `SSL_read`/`SSL_write`、`SSL_verify_cert_chain`、`BoringSSL` | native pinning（Flutter/加固）唯一实用解，直接 dump 明文 | `value-logic-analysis.md` §5.4、`dynamic-hook-help.md` |

**偷懒路线**：`objection -g <包名> explore` → `android sslpinning disable`（objection 1.12.5 已装，Frida 封装，
先起 frida-server 再连；能关掉 OkHttp 等常见 pinning，native 的还是要 C3）。

C2 最小模板（存 `/tmp/unpin.js`）：
```js
Java.perform(function () {
  try { var P = Java.use('okhttp3.CertificatePinner');
        P.check.overload('java.lang.String', 'java.util.List').implementation = function () { return; };
  } catch (e) {}
  try { var TM = Java.use('javax.net.ssl.X509TrustManager');
        TM.checkServerTrusted.implementation = function () {};
  } catch (e) {}
});
```
```sh
frida -H 127.0.0.1:27043 -f <包名> -l /tmp/unpin.js --no-pause   # 27043 是本机测试实例；27042 可能被宿主占用
```
> Hook `CertificatePinner` 只对 OkHttp 生效；Flutter/Dart 的 `SecurityContext`、native 校验走 C3。
> Frida 本身会被检测（§五「Frida 检测」），被检测时改名 + 换端口（§7.3）。

**风险**：动态加载比代理更容易被运行时安全校验盯上（有封号风险，登录态 App 尤其）；C1 只改「读到的响应」别改支付/订单请求体，
否则可能真的下单成功；用完 `frida-kill` 结束进程。

### 6.4 抓到之后

- 先静态定位再抓包确认：`grep -rn 'https\?://' smali | grep -iE 'vip|member|order|reward|coin|user'`（`scan_premium.py` 第 6 节已列接口 URL）。
- 改响应：`entitlement-analysis.md` §4.2（等长替换最稳）；请求带 `sign`/`timestamp` 的，别硬改参数，**Hook 签名函数**（`value-logic-analysis.md` §5.4）。
- 服务端每次重下发权益 → 本地补丁只影响当次，交付时如实告诉用户做不到永久适配。

## 七、Frida 环境与常用脚本（动态调试主线）

两条链路，**优先 adb**：
1. **方案 0（首选）：adb root 通道** —— proot 里 `adb -s <自动发现的 serial>`（实测 `127.0.0.1:42777`）即真机 root，
   `scripts/adb_device.sh frida start` 一键 push + 启动 + `frida-ps` 验证（端口 **27043**），AI 全程自己驱动。
2. **方案 1（兜底）：用户 Termux 手动起** —— adb 不可用/用户不让开时，用 `frida_server_prep.sh` 出操作卡，
   用户 `su` 后起 server，proot 内连 **27043**。

> **端口别混**：**27043** = 我们自己的测试实例；**27042 可能被宿主占用的 frida-server 实例专用**，
> 脚本拒绝使用，也不要去 kill 它。

### 7.1 搭建（本机已预装/预下载）

```sh
# 0) 自检：adb 通道 + 客户端/server 版本
bash scripts/adb_device.sh check      # 真机 root 通道（adb / id -u=0 / frida-server / tcpdump）
bash scripts/toolcheck.sh             # 本机 frida 客户端 17.26.2 + frida-server 文件

# 1) 方案 0：adb 自动启动（首选，用户不用动手）
bash scripts/adb_device.sh frida start          # push + root 启动 + frida-ps 验证（27043）
bash scripts/adb_device.sh frida status         # 看 pid / 端口 / 连通性
frida-ps -H 127.0.0.1:27043 | head              # 独立验证
# ...Hook 分析...
bash scripts/adb_device.sh frida stop           # 收工：只停本脚本启动的实例，绝不碰 27042

# 2) 方案 1：adb 不可用时，用户 Termux 手动起（兜底）
bash scripts/frida_server_prep.sh               # 复制到 /sdcard + 打印操作卡
#   用户按卡执行：su → KernelSU 授权 → 3 条命令
#   或 bash scripts/frida_server_prep.sh --auto --serial 127.0.0.1:<无线调试端口> 让脚本自己走 adb 自动启动（脚本自动发现端口，可 `--serial` 显式指定）
bash scripts/frida_server_prep.sh --status      # 验证（优先用 adb_device.sh frida status）
bash scripts/frida_server_prep.sh --stop-hint   # 提醒用户关闭

# 3) 反检测：改名 + 换端口（--port 8888），客户端同步 -H 127.0.0.1:8888
```
连不上排错：版本不一致（`frida --version` 必须 = server 版本 = 17.26.2）、server 没起（`frida status`）、
端口被占（27042 已被 宿主自带实例占用）、SELinux 限制；`adb_device.sh check` 失败会直接打印「修法」。
客户端在 proot、server 在 Android 侧，走 TCP，不需要 USB 线。

### 7.2 常用脚本模板
- 枚举疑似权益类 / Hook 判定方法 + 栈：`entitlement-analysis.md` §5.1–5.2
- Hook SharedPreferences（看权益/数值键）：`entitlement-analysis.md` §5.3
- Hook HTTP 响应改 `isVip`/`coin`：`entitlement-analysis.md` §4.2、`value-logic-analysis.md` §5.3
- native 导出函数 Hook / 内存扫描：`value-logic-analysis.md` §5.4

### 7.3 反检测要点
- frida-server 改名 + 非默认端口（`-l 0.0.0.0:8888`），客户端 `-H 127.0.0.1:8888`。
- spawn 模式动态加载（`-f 包名`）比 attach 更早，能赶在检测前；必要时 `setTimeout` 延迟 hook。
- Magisk Hide / Shamiko / LSPosed 隐藏列表把目标 App 排除在 root 可见范围外。
- 只 Hook 目标方法，别 Hook `ClassLoader`/`Runtime` 高频方法（容易卡死/被检测）。
