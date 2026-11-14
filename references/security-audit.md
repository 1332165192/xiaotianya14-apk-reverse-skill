# 安全审计清单（APK 静态检查 + 真机验证）

> 用途：对**自己拥有/已获授权**的 App 做安全体检（组件暴露、WebView、存储与加密、运行时对抗），
> 输出可复现的证据而不是"看起来有漏洞"。
> 方法参考社区同类 skill（如 [incogbyte/android-reverse-engineering-claude-skill](https://github.com/incogbyte/android-reverse-engineering-claude-skill)
> 的 security audit 项）——**社区资料，仅作参考**，具体命令以实测为准。
>
> **两条铁律**：
> 1. **静态 grep 命中 ≠ 漏洞**：必须结合上下文，能真机/动态验证的要验证；验证不了就标「待验证」，不写死结论。
> 2. **只读优先**：涉及数据/网络的操作先只读；不测试线上服务、不写别人数据、不做破坏性验证。

## 一、先决条件（先解码，再审计）

```sh
SK=/root/.dsh/skills/apk-reverse
bash $SK/scripts/decode.sh app.apk --out ./work     # 产物：./work/<任务名>/apktool 与 ./work/<任务名>/jadx/sources
python3 $SK/scripts/manifest_summary.py ./work/<任务名>/apktool
python3 $SK/scripts/scan_premium.py  ./work/<任务名>/apktool   # §7 运行时安全校验/完整性、§8 native 线索
python3 $SK/scripts/find_api_calls.py ./work/<任务名>/jadx/sources --secrets --auth   # 密钥/认证线索（脚本见 SKILL.md §2）
```

- 下文用 `A=./work/<任务名>/apktool`（apktool 解码目录）、`J=./work/<任务名>/jadx/sources`（Java 源码）代路径。
- 只看 smali/资源时用 `A`；能读 Java 时用 `J`（`decode.sh` 默认两者都出）。
- 真机命令里的 adb 目标 serial 用 `device_adb_guard.sh status` 打印的「目标」（自动发现，见 `SKILL.md` §12）；
  多设备时加 `--serial`。

## 二、检查清单（总表）

| 检查项 | 静态检查方法 | 命中后怎么验证（真机/动态） | 记录与风险 |
|---|---|---|---|
| 证书固定 / pinning | `scan_premium.py` §7 记录签名/完整性线索；grep `CertificatePinner`、`checkServerTrusted`、`TrustManagerImpl`、`sslSocketFactory`；看 `res/xml/network_security_config.xml` 的 `<pin-set>` | 装 mitmproxy CA 后抓包（`protection-map.md` §六 A）；失败就试 apk-mitm（B）/ Frida C2–C3，或 `objection ... android sslpinning disable` 快速判断是不是 Java 层 pin | pin 类型（Java / native / Flutter）、位置、能否适配、是否必须重打包 |
| 明文流量 | `manifest_summary.py` 的 `cleartext` 行；grep `usesCleartextTraffic`、`cleartextTrafficPermitted` | 代理抓包看是否走 http（`protection-map.md` §六 A）；注意 targetSdk ≥28 默认禁明文 | 全局允许还是仅调试域名；网络配置白名单；是否有敏感接口走明文 |
| debuggable | `manifest_summary.py` 的 `debuggable` 行；grep `android:debuggable` | `adb shell run-as <包名> id`（只有 debuggable 包能 run-as）；release 包应为 false | 是否 release 误开；能读私有目录/改数据的影响面 |
| allowBackup | `manifest_summary.py` 的 `allowBackup` 行（未声明默认 true，受 targetSdk/ROM 影响） | `adb backup -f /tmp/a.ab <包名>`（Android 12+ 很多 ROM 已限制；**失败不等于安全**）；有 root 可只读查看数据目录 | 是否可导出应用数据；targetSdk 影响；是否有更直接的导出路径 |
| 导出 Activity | `manifest_summary.py` 组件列表；grep `<activity` 且 `android:exported="true"`，看 intent-filter | `adb shell am start -n <包名>/<Activity>`（无需授权即可打开）+ `adb logcat -d` 观察；**不要点删除/支付类按钮** | 组件名、`android:permission` 保护、能否未授权启动、是否接收敏感 extra |
| 导出 Service | grep `<service` 且 `android:exported="true"` | `adb shell am startservice -n <包名>/<Service>`（或 `am start-foreground-service`）+ logcat | 是否能被任意 App 调用、是否执行敏感操作 |
| 导出 Receiver | grep `<receiver` 且 `android:exported="true"`，记录 intent-filter 的 action | `adb shell am broadcast -a <action> -n <包名>/<Receiver>` + logcat | 是否接受外部广播、action 是否可被伪造、是否做敏感动作 |
| 导出 Provider | grep `<provider` 且 `android:exported="true"`，记录 `authorities` / `grantUriPermissions` | **只读**：`adb shell content query --uri content://<authority>/`；不要 insert/delete | authority、读写权限、暴露的 path 范围 |
| Fragment Injection | grep `extends PreferenceActivity`、`isValidFragment`；**导出的 Activity + 未覆盖/宽松 `isValidFragment`** 才可疑 | 尝试 `adb shell am start -n <包名>/<Activity> --es ":android:show_fragment" "<fragment类名>"`；能加载到非预期 fragment 才算命中（不同实现有差异，**以实测为准**） | Activity、是否从 Intent extra 取 fragment 类名、实测结果；静态命中不等于可利用 |
| WebView 配置 | grep `addJavascriptInterface`、`setJavaScriptEnabled`、`setAllowFileAccess`、`setAllowUniversalAccessFromFileURLs`、`onReceivedSslError`（是否 `proceed()`） | 动态 hook 或测试页 `loadUrl` 后看 JS 能否调原生接口；只在授权、无敏感数据的测试环境做 | 暴露的 JS 接口名、文件访问开关、SSL 错误是放行还是取消 |
| 硬编码密钥 / 凭据 | `find_api_calls.py --secrets`（AKIA/AIza/sk-/BEGIN/password 等）；grep 兜底；`--auth` 看 Authorization/token/sign 参数 | **只看本地上下文**（是否 demo/占位/被混淆）；**不要拿密钥请求线上服务验证**；确认真实就记录并建议轮换 | 文件:行、类型（云 key/API key/密码/证书）、疑似真实还是示例、是否需轮换 |
| 弱加密 | grep `Cipher.getInstance`、`AES/ECB`、`DES/`、`IvParameterSpec`、`SecretKeySpec`；追 key/IV 来源 | 看 key 是否硬编码、IV 是否固定、是否 ECB；结合数据流确认用途；**不凭算法名直接报高危**（可能是校验/HMAC） | 算法/模式/填充、key/IV 来源、影响面、是否仅本地校验用 |
| root / 模拟器 / 调试检测（RASP 类） | `scan_premium.py` §7：`getPackageInfo`、`GET_SIGNATURES`、`MessageDigest`、Play Integrity、SafetyNet、`isDebuggerConnected`、root/magisk/xposed/frida/ptrace/goldfish | 在本机 root 环境运行 App，复现闪退/弹窗后看 `adb logcat -d`；确认是否检测触发（时间点/栈） | 检测类型、触发条件、为改包放行需要做什么（不是攻击他人） |
| 日志泄露（可选） | grep `Log.d/i/v` 里带 token/password/手机号；第三方 App 的 log 在 Android 4.1+ 读不到，但 debug 包/root 可看 | `adb logcat -d` 复现关键流程后检索包名/关键字 | 是否泄露敏感值、release 是否仍开、能否被 root 设备读到 |
| 组件权限保护（横向） | 对照上面导出的组件看 `android:permission` / `protectionLevel`；`manifest_summary.py` 的权限列表 | 对照 5–8 的实测结果：**无权限保护 + exported** 才是风险 | 受保护/不受保护组件清单，别把"导出了但需要 signature 权限"当高危 |

## 三、命令速查（复制用）

```sh
SK=/root/.dsh/skills/apk-reverse
A=./work/<任务名>/apktool
J=./work/<任务名>/jadx/sources

# 清单属性与组件
python3 $SK/scripts/manifest_summary.py "$A"
grep -n 'android:exported="true"' "$A/AndroidManifest.xml"
grep -nE 'android:debuggable|android:allowBackup|usesCleartextTraffic' "$A/AndroidManifest.xml"
grep -rn 'cleartextTrafficPermitted\|<pin-set' "$A/res/xml" 2>/dev/null

# 证书固定 / WebView / 加密 / 检测
grep -rnE 'CertificatePinner|checkServerTrusted|TrustManagerImpl|X509TrustManager|sslSocketFactory' "$J"
grep -rnE 'addJavascriptInterface|setJavaScriptEnabled|setAllowFileAccess|setAllowUniversalAccessFromFileURLs|onReceivedSslError' "$J"
grep -rnE 'Cipher\.getInstance|AES/ECB|DES/|IvParameterSpec|SecretKeySpec' "$J"
grep -rnE 'isDebuggerConnected|TracerPid|/system/xbin/su|magisk|xposed|lsposed|frida|ptrace|goldfish|RootBeer' "$J"

# 脚本汇总
python3 $SK/scripts/scan_premium.py "$A"          # §7 完整性/运行时安全校验，§8 native 关键字
python3 $SK/scripts/find_api_calls.py "$J" --secrets --auth   # 密钥/认证线索
```

> smali-only（没跑 jadx）时把 `"$J"` 换成 `"$A"/smali*`；grep 的 `E` 正则与转义在 shell 里按需调整。

## 四、真机验证速查

| 目标 | 命令（只读优先） | 注意 |
|---|---|---|
| 导出 Activity | `adb shell am start -n <包名>/<Activity>` | 不点删除/支付/授权类按钮；看是否无需授权即可打开 |
| 导出 Service | `adb shell am startservice -n <包名>/<Service>` | Android 8+ 后台限制可能影响结果，结合 logcat 判断 |
| 导出 Receiver | `adb shell am broadcast -a <action> -n <包名>/<Receiver>` | 只发无害 action；不要伪造业务回调 |
| 导出 Provider（只读） | `adb shell content query --uri content://<authority>/` | **不要 insert/delete/update**；能读到数据即证明暴露面 |
| debuggable 验证 | `adb shell run-as <包名> id` | 成功 = 可读写该 App 私有目录（仅限自己测试环境） |
| 备份验证 | `adb backup -f /tmp/a.ab <包名>` | Android 12+ 常被限制；失败不要直接判定"安全" |
| 观察日志 | `adb logcat -d` | 先复现再抓；过滤包名/关键字减少噪音 |
| Fragment Injection | `adb shell am start -n <包名>/<Activity> --es ":android:show_fragment" "<fragment类名>"` | 需真机实测；不同 ROM/实现差异大，静态嫌疑不等于可利用 |

## 五、记录模板（给用户/报告用）

| 字段 | 填什么 |
|---|---|
| 检查项 | 上表里的名称（例：导出 Activity） |
| 证据 | `文件:行` 或命令输出片段（脱敏，不贴密钥明文） |
| 命中条件 | 为什么算命中（例：exported=true 且无 permission 保护） |
| 真机验证 | 命令 + 关键输出；没验证就写「未验证」 |
| 影响 | 可被谁利用、需要什么条件、影响什么数据/功能 |
| 建议 | 修复方向（例：exported=false / 加 signature 权限 / 移除 JS 接口） |
| 置信度 | 高 / 中 / 待验证（**没有验证证据的不要写"高"**） |

## 六、边界与免责

- 只对**用户自己拥有/已获授权**的 App 做审计；不测试他人线上服务、不做未授权渗透。
- 静态命中先当线索，不当结论；不能验证的条目标「待验证」，不夸大。
- 发现真实漏洞时先私下告知应用所有者，不公开未修复细节；报告里对密钥/Token 做脱敏。
- 本清单参照社区做法整理（见 `community-landscape.md` §二），第三方工具/文章仅作参考，命令以本机为准。

> 关联：`references/protection-map.md`（加固/完整性/抓包）；本清单目标是**审计**而不是适配，
> 广告组件清理/适配等改动流程见 `SKILL.md` §3–§8。
