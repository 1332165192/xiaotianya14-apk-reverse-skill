# 手机端 APK 工具（补足"没有电脑生态"）

> 结论先说：**不用堆一堆 App**。CLI 工具链（jadx/apktool/frida/mitmproxy/adb）已经覆盖 90% 的活；
> 只有 3 个场景 Android App 确实比 CLI 顺手，其余装了也是占地方。
>
> 原则：**只用开源/免费且来源可信的**；修改成品/加载器/第三方修改类（GameGuardian、Lucky Patcher 之类）不装、不推荐。

## §1 值得装的（按真实缺口挑）

| App | 包名 / 来源 | 开源 | 补什么缺口 | 什么时候用 |
|---|---|---|---|---|
| **App Manager** | `io.github.muntashirakon.AppManager`（F-Droid / GitHub） | ✅ GPLv3 | 应用分析：组件/权限/追踪器/导出 APK/冻结；比一堆 `dumpsys` 命令直观 | 摸一个陌生 App 的结构、看有没有广告/统计 SDK、导出原包对比 |
| **LibChecker** | `com.absinthe.libchecker`（GitHub / F-Droid） | ✅ | 一条列表看清目标用了哪些第三方 SDK（广告/付费点/统计/加固） | 开局 Triage，比 `analyze_ads.py` 更快给人看结论 |
| **PCAPdroid** | `com.emanuelef.remote_capture`（F-Droid / GitHub） | ✅ | 免 root 抓全机流量，**专治"忽略系统代理"的 App**（Flutter/自研网络栈，mitmproxy 抓不到） | mitmproxy 抓不到、要看 App 到底连了哪些域名时 |
| **Termux** | `com.termux`（F-Droid） | ✅ | 手机上直接跑 shell：无 adb 时起 tcpdump、跑 frida-server、adb 兜底 | **已装**；adb 通道关掉时的手动兜底 |
| **MT管理器** | `bin.mt.plus` | ❌ 闭源（免费版可用） | 临时快修：dex/资源二进制直接改、签名/重签、批量文件操作、hex 编辑 | **已装**；只当"快修/查看"工具，主流程仍走 CLI，避免不可复现 |

## §2 明确不装（安全/法律/不可复现）

| 工具 | 为什么不装 |
|---|---|
| GameGuardian / 烧饼修改器 类 | 需要常驻 root/悬浮窗，来源不可信；数值修改我们用 Frida + 静态补丁，可验证可复现 |
| Lucky Patcher 类 | 修改成品/自动 patch，带广告后门风险；技能不做未授权副本分发 |
| 各种"一键广告组件清理/一键修改"工具 | 输出不可审计，容易把包改坏/带毒；本技能要求每一步可回滚 |
| 来路不明的"签名克隆/过签"工具 | 拿不到私钥时所谓"克隆"多是改校验，容易触发服务端风控 |

## §2.5 本机已装（2026-11-13，用 adb 装好）

| App | 包名 | 版本 | 安装包位置 |
|---|---|---|---|
| App Manager | `io.github.muntashirakon.AppManager` | 4.1.1 | `/sdcard/Download/AppManager_v4.1.1.apk` |
| LibChecker | `com.absinthe.libchecker` | 2.5.5.1 | `/sdcard/Download/LibChecker-release.apk` |
| PCAPdroid | `com.emanuelef.remote_capture` | 2.0.2 | `/sdcard/Download/PCAPdroid_v2.0.2.apk` |

首次使用注意：
- **LibChecker**：要「读取应用列表」权限。已用 `adb shell appops set com.absinthe.libchecker android:get_installed_apps allow` 打开，
  重启 App 后能列出全部应用（实测）；若再弹提示，点允许即可。
- **App Manager**：首启有「密钥库」提示框，点"关闭"进入主界面。
- **PCAPdroid**：第一次抓包会弹 VPN 授权，必须用户点「允许」（AI 不代点 VPN 授权）。

### AI 怎么"调用"这些 App（实测可行）

> 下面 `$SERIAL` 用**自动发现**结果（`bash scripts/device_adb_guard.sh status` 的「目标」；实测
> `127.0.0.1:42777`，5555 只是 `adb tcpip 5555` 模式示例）。

```sh
# 1) 启动（用真实 Activity，避免跨应用打开对话框）
adb -s "$SERIAL" shell am start -n io.github.muntashirakon.AppManager/.main.SplashActivity
adb -s "$SERIAL" shell am start -n com.absinthe.libchecker/.domain.home.ui.MainActivity
adb -s "$SERIAL" shell am start -n com.emanuelef.remote_capture/.activities.MainActivity

# 2) 读界面（比 MCP 读屏更细，含 resource-id/bounds）
adb -s "$SERIAL" shell uiautomator dump /data/local/tmp/ui.xml
adb -s "$SERIAL" shell 'cat /data/local/tmp/ui.xml' | grep -oE 'text="[^"]+"'

# 3) 点击（系统权限页 MCP 不让点，用 adb 可以）
adb -s "$SERIAL" shell input tap 640 1200
adb -s "$SERIAL" shell input swipe 640 2000 640 600 300
```
局限：靠 UI 自动化，慢且可能点错；**重要结论仍用 CLI（apkid/analyze_ads/identity_report）交叉验证**，
App 只负责"看得快/给人看"。

## §3 怎么装（本机现成渠道）

本机已装 **F-Droid / Obtainium / Aurora Store**，adb 通道可用时也可以：

```sh
# adb 在线时（推荐，可复现）
adb -s "$SERIAL" install -r -d AppManager.apk
# 或从 F-Droid 搜索安装（无 adb 时，让用户点两下即可）
```

装前核对：包名、开发者、签名来源（F-Droid/GitHub release 优先）；**不装第三方"修改版"站点下的包**。

## §4 和 CLI 的分工（别混）

| 任务 | 首选 | App 只用来 |
|---|---|---|
| 反编译/改 smali/重打包 | `jadx` + `apktool` + `build_sign.sh` | MT 快速看一眼/临时 hex |
| Hook/改内存/抓 HTTPS | `frida` + `mitmproxy`（adb 起） | PCAPdroid 抓忽略代理的流量 |
| SDK/广告/加固识别 | `analyze_ads.py` + `apkid` | LibChecker 快速列表 |
| 看组件/导出/对比 | `dumpsys` + `identity_report.py` | App Manager 图形化 |
| 数值/权益修改 | `patch_method.py` / Frida / 改存档 | **不用 App**（不可复现） |

## §5 交付里怎么说

- 用到 App 工具时，在结论里说明用它做了什么（如"用 PCAPdroid 确认了流量域名，再回 mitmproxy 改响应"）；
- 最终交付物仍是**改好签名的 APK**，不要求用户装任何工具。
