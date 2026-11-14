# 动态 Hook：什么时候找你、你要怎么操作（跟着做版）

> 目的：**AI 不许在没告诉你的情况下要求动态 Hook**。需要动态时，AI 必须按 §8 的模板
> 先说清楚"为什么、要不要你动手、怎么验证、怎么关"，你同意后再继续。
> **adb root 通道可用时（多数机型，见 §0）你完全不用动手**，AI 自己起临时实例；§4 的 Termux 步骤只在兜底时需要。
> 不需要动态 Hook 的活（大多数广告组件清理 / 本地会员 / 存档数值），AI 自己静态做完，不打扰你。

## §0 方案 0：AI 自己起（adb root，不需要你动手）

手机已开无线调试、adbd 带 root（KernelSU），AI 可以在 proot 里用 adb 直接驱动真机起 `frida-server`。
**这种情况下你什么都不用做**，只需要回一句同意。AI 会执行：

```sh
bash scripts/adb_device.sh check          # 先自检：adb / id -u=0 / frida-server / tcpdump
bash scripts/adb_device.sh frida start    # 推送 + root 启动 + frida-ps 验证（端口 27043）
frida -H 127.0.0.1:27043 -f <包名> -l hook.js   # 动态 Hook
bash scripts/adb_device.sh frida stop     # 用完自己关（只停它自己起的实例）
```

- **仍要先告知你**：为什么用动态、预计多久、怎么关（§8 模板），你同意后才动手。
- adb root 等于整机 root：只在这次分析期间用；你可以随时要求 AI「现在关掉」。
- `check` 不通过（没开无线调试 / 没授权 / 你不想开）→ AI 自动退回 §4 的 Termux 手动方案。
- 端口说明：**27043** 是这次分析用的测试实例；**27042 可能被宿主占用实例**，AI 不会去碰。

## §1 一句话流程

```text
AI: "这个判定点被混淆了，静态找不到，需要开一次 Frida 动态确认"
  → 方案 0（优先）：AI 跑 adb_device.sh frida start（27043）→ 直接 Hook → 用完 frida stop
     你只需要回一句"同意"，不用动手机
  → 方案 1（兜底，adb 不可用时）：AI 跑 frida_server_prep.sh 把操作卡和 3 条命令给你
     你：打开 Termux → su → 粘贴 3 条 → 回车 → AI 验证连上
  → AI 跑 Hook 找到结果
  → 找到后落成静态补丁（交付还是 APK），关掉 frida-server
```

## §2 什么时候 AI 会来找你（需要动态 Hook）

| 场景 | 为什么静态做不了 |
|---|---|
| 会员判定点被 R8 混淆，类名/方法名全是 `a()`/`b()` | 没有名字线索，只能运行时看谁返回 true、谁被调用 |
| 数值/会员数据在 native `.so` 里 | 静态改 `.so` 风险高，先用 Hook 确认函数与偏移 |
| 字符串被加密（StringFog 等） | grep 不到明文，只能 Hook 解密方法打印结果 |
| 会员/余额由服务端下发（C 级） | 要 Hook HTTP 响应看真实字段，再决定改哪 |
| 加固壳运行时校验导致静态改完闪退 | 先 Hook 看是哪个校验、返回值是什么 |
| 需要确认"这个方法运行时到底返回什么/被谁调用" | 静态读调用链成本高、易错 |

## §3 什么时候 AI 不该来烦你（静态就能完成）

- 普通广告组件清理（SDK 类名可见、广告调用可直接删）；
- 会员/已购是本地字段或 SharedPreferences（`isVip()Z` 之类名字还能看到）；
- 数值在明文存档（shared_prefs / SQLite）或 getter 返回值；
- 只是要改文案、清单、布局、资源。

> 这些 AI 直接改 smali → 重打包 → 签名，**不需要 root、不需要 Frida、不需要你动手**。

## §4 你要做的（手机 root 终端 · Termux · 兜底方案）

> 只有 §0 的 adb 通道不可用时才需要你动手。

本机已装 **Termux**（`com.termux`），root 管理器是 **KernelSU**（`me.weishu.kernelsu`）。

1. AI 先跑：`bash scripts/frida_server_prep.sh`
   → 会把 frida-server 复制到 `/sdcard/Download/frida-server-17.26.2-arm64`，并给你操作卡。
2. 打开 **Termux**，输入 `su` 回车；KernelSU 弹「授予超级用户」→ 点**允许**（只授权 Termux 即可）。
3. 复制粘贴这 3 条（一条一条执行）：

   ```sh
   su
   cp /sdcard/Download/frida-server-17.26.2-arm64 /data/local/tmp/frida-server
   chmod 755 /data/local/tmp/frida-server && /data/local/tmp/frida-server &
   ```

4. 第 3 条没报错就是起好了（回到普通提示符正常，**别关 Termux**，切后台可以）。
5. 跟 AI 说一声「起好了」，AI 会跑验证：

   ```sh
   bash scripts/frida_server_prep.sh --status
   ```

   显示「已连上 frida-server」就继续；显示「还没连上」按 §7 排查。

> 不想手打也行：Termux 里长按屏幕 → Paste（粘贴）；或让 AI 用手机操控工具打开 Termux 代打，
> 但 KernelSU 的授权弹窗必须你点「允许」。

## §5 AI 起好后会做什么

- `frida -H 127.0.0.1:27043 -f <包名> -l hook.js`（spawn 挂载，赶在检测前；27042 可能被宿主占用实例，别用）；
- 枚举疑似类 / Hook 会员判定 + 打印调用栈 / Hook SharedPreferences / Hook HTTP 响应；
- 确认到具体类和方法后，**落成静态补丁**（`patch_method.py`），重打包签名；
- 交付物仍是 APK，不要求你长期开 Frida。

## §6 用完怎么关

```sh
# 方案 0（AI 用 adb 起的）：AI 会执行
bash scripts/adb_device.sh frida stop

# 方案 1（你在 Termux 手起的）：手机 root 终端里
su -c 'pkill -f frida-server'
# 或
su -c 'kill $(pidof frida-server)'
```

- 关掉后 AI 跑 `--status` 显示连不上，属正常。
- **建议用完就关**：frida-server 是本地调试服务，常驻会让部分 App 检测到、也费电。
- 重启手机后它自己不会启动（这次是临时起的），不用管。

## §7 起不来 / 连不上怎么排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `adb_device.sh check` 某项 `[失败]`/`[缺]` | adb 通道没通（无线调试没开/没授权/adbd 非 root） | 按输出里的「修法」：手机开无线调试 → 按无线调试页 `adb connect <IP>:<端口>`（实测 `127.0.0.1:42777`）点允许 → 重跑 `check`；仍不行走 Termux 兜底 |
| `su: not found` 或没弹授权 | Termux 没拿到 root | KernelSU App → 超级用户 → 给 Termux 授权；或换用 KernelSU 侧终端 |
| `cp: Permission denied` | 没在 su 下执行 | 先 `su` 再跑 `cp` |
| `frida-server: not executable` | 权限没给 | `chmod 755 /data/local/tmp/frida-server` |
| AI 连不上，报 unable to connect | server 没起/版本不一致/端口不对 | 先看 Termux 里进程在不在；`frida --version` 必须 = 17.26.2；换端口要两边一致 |
| 连上就退出/被检测杀 | App 检测 Frida | 换端口 + 改名（`-l 0.0.0.0:8888`，文件改名 `fs`），或先 spawn 动态加载 |
| Termux 切后台后连接断 | 系统杀后台 | Termux 里 `termux-wake-lock`；或保持前台 |

## §8 AI 必须遵守的告知模板（强制）

需要动态 Hook 时，AI 必须一次说清这 5 件事，等你同意后再继续：

```text
【需要你配合开一次 Frida】
1. 为什么：<静态做不到的具体原因，例如"会员判定被混淆成 a()Z，找不到是谁返回 true">
2. 你要做：打开 Termux → su → 允许 KernelSU 授权
3. 粘贴这 3 条命令：<prep 脚本给出的命令>
4. 我怎么验证：bash scripts/frida_server_prep.sh --status
5. 用完怎么关：bash scripts/frida_server_prep.sh --stop-hint
(可选) 预计耗时 X 分钟；只在这次分析用，交付还是改好签名的 APK。
```

硬规则：
- **不许**不告知就要求/假装使用动态 Hook；**不许**在连接失败时说"已经连上了"。
- 你不想开/开不了时，AI 必须**退回静态方案**并说明限制（例如"服务端下发的会员只能显示、接口仍会拒"）。
- 动态 Hook 只是定位手段，**最终交付仍然是重打包签名的 APK**。

## §9 安全提醒

- frida-server 只在本机 127.0.0.1 监听，**不要** `-l 0.0.0.0` 暴露到局域网/公网（除非明确做反检测实验）。
- 开着 frida-server 时不要登录支付/银行类 App，也不要在调试时输入密码。
- **adb root = 整机 root**：AI 用完必须停掉 frida-server 和抓包，并请你**关掉无线调试或拔线**；
  ⚠️ 别在公共 Wi-Fi 开调试端口（`adb tcpip 5555`/无线调试；同网段谁都能连你的 root shell）。`uninstall`/`clear` 会丢数据，AI 会先问你。
- 端口：27043 是测试实例；27042 可能被宿主占用实例，不要混。
- 用完关掉（方案 0 由 AI `frida stop`；方案 1 `pkill`）；不需要长期给 Termux root 的话，可以去 KernelSU 里撤销。
