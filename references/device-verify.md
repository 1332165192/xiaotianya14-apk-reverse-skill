# 真机安装与验证（adb root 优先 · MCP 兜底）

> **真机 root 通道**：手机已开无线调试，adbd 是 root（Android 17 / KernelSU，`u:r:ksu:s0`），
> `adb -s <自动发现的 serial> shell` 就是真机 root。无线调试端口**是随机的**（实测 `127.0.0.1:42777`，
> 不是 5555；`127.0.0.1:5555` 只是 `adb tcpip 5555` 模式示例）。4 个 adb 脚本自动发现，也可 `--serial`/`ADB_SERIAL` 指定。
> proot 里是普通 app uid、**不能自己提权**，要 root 只能走 adb。
> 所有操作封装在 `scripts/adb_device.sh`，**下文命令就是脚本真实子命令**（`bash scripts/adb_device.sh -h` 看全量）。
>
> **安全**：adb root = 整机 root（能删任何 App 数据）。**工作结束关无线调试/拔线**；⚠️ **别在公共网络开调试端口（tcpip 5555/无线调试）**
> （同网段谁都能连你的 root shell）；`uninstall` / `clear` 会丢数据，**必须先征得用户同意**；
> 脚本拒绝 `emulator-*` 设备、拒绝系统/厂商包。

## 一、adb root 通道（优先）

### 1.1 检测（开工先跑）

```sh
bash scripts/adb_device.sh check    # 退出码 0 = adb/设备/root/frida-server/tcpdump 全就绪
```

实测输出（2026-11-12，Android 17 / PLC110 / arm64-v8a）：

```text
[OK] adb: Android Debug Bridge version 1.0.41
[OK] 设备在线: 127.0.0.1:42777   # 自动发现；无线调试端口随机（实测 42777，5555 仅 tcpip 模式）
[OK] root: id -u=0 (context=u:r:ksu:s0)
[OK] Android 17 / PLC110 / abi=arm64-v8a
[OK] 设备 frida-server: /data/local/tmp/frida-server (--version=17.26.2)
[OK] 设备 tcpdump: /system/bin/tcpdump (tcpdump version 4.99.6)
结论: 真机 root 通道可用——frida/tcpdump 均可由 AI 直接驱动，无需用户手动 Termux。
```

- **通过** → 本文件 §1.2 的命令优先，MCP 点屏只用来确认界面效果。
- **不通过** → 手机开「无线调试」→ 按无线调试页显示的 `adb connect <IP>:<端口>`（实测 `127.0.0.1:42777`；
  手机弹 RSA 授权，点允许）→ 重跑 `check`；
  仍失败就退回 §2 的 MCP 点屏（无 adb / 用户不让开时都走这条路）。

### 1.2 常用操作（命中后优先用这些）

| 操作 | 命令 | 说明 |
|---|---|---|
| 安装/覆盖 | `bash scripts/adb_device.sh install /sdcard/Download/xxx.apk` | `adb install -r -d`（保留数据、允许降级）；加 `--dry-run` 只打印命令 |
| 启动 | `bash scripts/adb_device.sh start <包名>` | `am start`（解析不到启动 Activity 自动退回 monkey） |
| 强制停止 | `bash scripts/adb_device.sh stop <包名>` | `am force-stop`；冷启动验证前先停 |
| 看包信息 | `bash scripts/adb_device.sh info <包名>` | `pm path` + versionName/首装时间/installer |
| 崩溃日志 | `bash scripts/adb_device.sh logcat` | 默认过滤 `AndroidRuntime\|FATAL\|Exception\|ANR\|crash`，最近 300 行 |
| 精确崩溃栈 | `bash scripts/adb_device.sh logcat --grep AndroidRuntime --lines 500` | 复现闪退后跑这一条 |
| 清缓冲再复现 | `bash scripts/adb_device.sh logcat --clear` → 复现 → `bash scripts/adb_device.sh logcat` | 最快定位"这次启动崩在哪" |
| 截图 | `bash scripts/adb_device.sh screencap /sdcard/Download/shot.png` | 设备端 `screencap` 后 pull 回 |
| 卸载 | `bash scripts/adb_device.sh uninstall <包名> --yes` | **丢数据**，先征得同意；系统/厂商包被拒 |
| 清数据 | `bash scripts/adb_device.sh clear <包名> --yes` | **丢存档/登录态**，先说明再执行 |
| 推送/拉取 | `bash scripts/adb_device.sh push <本地> <设备路径>` / `pull <设备路径> <本地>` | 替换 base.apk、拉存档/日志等 |

- **崩溃排查流程**：`logcat --clear` → `start <包名>` → 复现 → `logcat --grep AndroidRuntime`，
  栈顶类名回 jadx/smali 定位（`pad`/`AbstractMethodError`/`UnsatisfiedLinkError` 各有对应坑，见 SKILL.md §6）。
- `uninstall` / `clear` 必须显式 `--yes`（脚本硬性要求）；另外脚本按「包名前缀黑名单 + `pm path` 是否在系统分区」双重拒绝。
- serial **自动发现**：优先 `ADB_SERIAL`/`--serial`；否则 5555 在线就用；否则从 `adb devices` 取第一个 `device`
  （跳过 `emulator-*`；无线调试随机端口如 `127.0.0.1:42777`）。脚本**始终拒绝 `emulator-*`**：
  `adb devices` 里若出现 `emulator-5554`，先确认是不是本机显示名（本机曾出现，不是模拟器）；
  需要用它连时改用无线调试的 `127.0.0.1:<端口>`，不要 `--serial emulator-5554`。

### 1.3 界面操作：`device_ui.sh`（adb 优先，视觉兜底）

装完后"点按钮/读页面/看是否跳商店"这些界面操作，**adb 在线就优先用 `device_ui.sh`**，比截图点屏快且可断言；
视觉（`mcp__phone__screen` / 截图看图）只做结果确认和看自绘页。完整指南见 `references/device-control.md`。

```sh
S="bash scripts/device_ui.sh"
$S launch <包名>                  # 启动（不打开文件管理器点）
$S foreground                     # 确认前台 Activity（没跳商店/没卡桌面）
$S dump --texts                   # 读页面上的文本/按钮
$S tap '继续安装'                 # 按文本点
$S wait '安装完成' 20             # 等结果，别 sleep 瞎等
$S screen /tmp/after.png          # 截图供视觉确认（read_image /tmp/after.png）
```

- 安装/卸载/清数据/崩溃栈仍用 §1.2 的 `adb_device.sh`（`install` / `uninstall --yes` / `logcat`）。
- **装完/改完一定要重启验证**：`adb_device.sh stop <包名>` → `adb_device.sh start <包名>`
  （或 `device_ui.sh launch`）→ `wait` 关键文本 → `screen` 确认；冷启动不崩才算真通过。
- 文本找不到/自绘页/FLAG_SECURE 的降级路径：`references/device-control.md` §4–§5。

### 1.4 adb 不可用时：MCP 点屏（兜底）

无 adb、无线调试不能开、或用户不同意开 root 通道时，用下面 §2–§6 的 MCP 流程。
判定标准相同（能启动、无广告、功能可用），只是点屏更慢、看不到崩溃栈。

## 二、安装流程（MCP · ColorOS/OPPO 实测）

```text
1. 把 APK 拷到 /sdcard/Download/（bash 写入，需 danger-full-access）
2. mcp__phone__open(app="com.coloros.filemanager")          # 打开文件管理
3. 点「下载」→ 找到 xxx.apk → 点击
4. 安装器：
   - 首次安装：“第三方来源提醒”→ 继续安装 → 扫描 → 继续安装 → 安装完成 → 完成
   - 同版本已装：“已安装相同版本”→ 选“重新安装”→ 继续安装 → 完成
5. mcp__phone__open(app="应用名或包名") 启动
6. mcp__phone__screen(image=true) 读屏/截图验证
```

## 三、常见安装问题

| 现象 | 处理 |
|---|---|
| 签名冲突（原版已装） | 先卸载原版（**必须征得用户同意**，数据会丢）；adb 通道可用时 `bash scripts/adb_device.sh uninstall <包名> --yes` |
| 未知来源被拦 | 安装器会弹“继续安装”，逐级点；被系统策略拦 → handoff 用户操作 |
| 安装完成但打不开 | 先用 `adb_device.sh logcat --grep AndroidRuntime` 看栈；再查 pairip/授权壳（见 protection-map） |
| 已安装相同版本 | 选“重新安装”覆盖（同签名）；有 adb 时直接 `install`（`-r -d` 保留数据） |
| 安装器是“应用安装器”/无按钮 | 用 tap_xy + 最近截图坐标；必要时 handoff |

## 四、验证清单

```text
□ 能正常启动（不跳 Play 商店、不闪退、不卡 Logo）
□ 冷启动复验：`adb_device.sh stop <包名>` → `start`（或 device_ui.sh launch）后仍正常 —— 装完必须重启一次再判
□ 主界面/核心页无广告（无横幅、无插屏、无“加载广告”残留）
□ 原购买入口状态符合预期（已购模式下通常隐藏）
□ 核心功能可用（如反编译可出代码）
□ 无异常弹窗（“未授权”/“请购买”）
□ 有崩溃就用 adb logcat 看栈（§1.2）；无 adb 时手点+观察
```

权益逻辑分析 / 数值修改额外验证（详细见 `entitlement-analysis.md` §6、`value-logic-analysis.md` §6）：

```text
□ 冷启动不闪退，权益页不再强制跳购买
□ 权益功能"真能用"（不是只有按钮变色/文案变化）
□ 杀进程重启 / 清缓存后状态是否保留（验证是否持久化）
□ 数值显示与消耗一致（花一次看是否真扣；数值不扣减则看是否不减）
□ 重进界面/刷新后是否被服务端覆盖回原值（C 级属预期）
□ 断网场景：权益/数值功能是否仍可用（判断 A/B 级）
□ 核心功能无回归：登录、支付、云同步、更新检查
```

> 有 adb 通道时，"杀进程重启"用 `adb_device.sh stop <包名>` + `start`（比 MCP 点屏快一个量级）；
> "清缓存"用 `clear <包名> --yes`（**会丢存档/登录态，先说明**）。

## 五、read 屏受限（FLAG_SECURE）

- `mcp__phone__screen` 返回“安全窗口（禁止截屏/读取）”= 应用开了 FLAG_SECURE，**不代表崩溃**。
- 处理：`mcp__phone__handoff` 请用户看一眼并反馈；或让用户点开具体页面拍照/描述。
- 有 adb 时：`adb_device.sh screencap` 也会被 FLAG_SECURE 拦（黑图/空图），同样不要误判成崩溃。
- 不要因读不到屏就重复重启应用或误判失败。

## 六、交付（默认只给 APK）

- 默认只输出到 `/sdcard/Download/`：
  - `xxx_广告组件清理版.apk`（已签名，附 sha256）
- 用 `present` 展示；回复里 1-2 句话说明"改了什么/能不能用/限制"。
- **用户明确要才做**：`xxx_反编译源码.zip`（要源码）、`xxx_修改说明.md`（要说明/研究材料），模板见 `SKILL.md §7`。
- `field-journal/` 只在遇到可复用坑时记，不必每次写。
- 收工：`adb_device.sh frida stop`（若起过）/ `tcpdump stop`（若抓过），关无线调试或拔线。
