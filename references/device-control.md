# adb 混合操控：界面操作怎么选（adb 优先，视觉兜底）

> **一句话**：真机 adb 在线 → **默认用 adb 操控**（`scripts/device_ui.sh` 的
> launch/foreground/dump/tap/swipe/key/text/screen/wait/apps）；视觉（`mcp__phone__screen` 截图 + 看图）只做
> **结果确认、兜底、看自绘/加密界面**。**只有 adb 离线才提示用户开**
> （`bash scripts/device_adb_guard.sh open-hint`），不许因为"安全"绕开 adb 只用视觉点屏。
>
> 为什么这样：纯视觉每步都要「截图→理解→算坐标」，慢且会点偏；纯 adb 又看不到自绘/图片按钮/广告横幅。
> 两条路**可组合**：adb 操作 → 视觉确认；视觉发现目标 → 先用文本找，找不到才落坐标。
> 开关规则见 `references/adb-security.md`；装/卸/日志见 `references/device-verify.md`。

## §1 两种操控的边界（为什么混合）

| 维度 | adb 操控（`device_ui.sh`） | 视觉操控（MCP `screen` / `tap_xy`） |
|---|---|---|
| 定位依据 | uiautomator 节点树：按 `text` / `content-desc` 精确找，能断言"文本出现了" | 截图像素 + 看图/OCR：按坐标点，受字号/缩放/动画影响 |
| 速度 | 每次 dump 约 1–2s，tap/key 即时（亚秒） | 每次截图+理解数秒，一轮操作通常慢数倍 |
| 稳定性 | 可复现、可 `wait` 等条件、失败有原始报错 | 易点偏/误判；OCR 对图标按钮、艺术字常失效 |
| 看得到什么 | 只有无障碍节点；**自绘/Canvas/部分加固页可能 dump 为空** | 渲染出来的都能看到（图片按钮、广告横幅、自绘 UI） |
| 典型用途 | 装/卸/启动/列表/表单/系统页/重试流程 | 确认结果、找自绘控件、看广告是否消失、排查黑屏 |

**量级对比**（经验值，非精确基准）：adb 一轮「dump→tap→wait」约 2–4s；视觉一轮「截图→理解→点→再截图」约 10–30s。
所以：**能用 adb 断言的就别用眼睛**；只在 adb 看不到/对不上时切视觉。

## §2 命令表（`scripts/device_ui.sh` 全部子命令）

> serial **自动发现**（优先 `ADB_SERIAL`/`--serial`；否则 5555 在线就用；否则取 `adb devices` 第一个真机、跳过 `emulator-*`；
> 无线调试随机端口如实测 `127.0.0.1:42777`）；adb 失败会打印原始输出。
> `bash scripts/device_ui.sh -h` 看帮助。

| 子命令 | 示例 | 作用 |
|---|---|---|
| `foreground` | `device_ui.sh foreground` | 当前焦点 Activity（确认 App 是否在前台/跳没跳商店） |
| `launch` | `device_ui.sh launch com.example.app` / `launch pkg/Act` | `am start` 启动（解析不到启动页自动退回 monkey） |
| `dump` | `device_ui.sh dump --texts` / `dump --limit 50` / `dump --limit 0` | `uiautomator dump` 后列出 text/bounds/clickable（`--limit 0` 全部） |
| `tap` | `device_ui.sh tap '登录'` / `tap '登.*录' -i` / `tap 540 1200` | 按文本正则找节点点中心；或直接点坐标（`-i` 忽略大小写） |
| `swipe` | `device_ui.sh swipe 540 1600 540 600 400` | 滑动（默认 300ms；上滑一屏 = 起点大 y → 终点小 y） |
| `key` | `device_ui.sh key back` / `key home` / `key enter` / `key del` | 按键（back/home/enter/recents/menu/delete/tab/space/esc/方向键/音量/power，或数字键码） |
| `text` | `device_ui.sh text 'hello'` / `text 'a@b.com' --switch-ime` | **安全打字**：转调 `device_input.sh`，中文输入法默认拒绝（见 `ime-typing.md`） |
| `screen` | `device_ui.sh screen /tmp/after.png` | 截图并拉回（供视觉确认；默认 `/tmp/device_ui_screen.png`） |
| `wait` | `device_ui.sh wait '首页' 10` | 轮询 dump 等文本出现（默认 10s，超时打印当前可见文本） |
| `apps` | `device_ui.sh apps 设置` / `apps --user` / `apps --system` | 包列表（子串/正则过滤；`--user` 只列用户装的） |

`dump` 每次会把 XML 缓存到 `/tmp/device_ui_dump.xml`（tap/wait 同一次 dump 复用它），要更细的字段直接读这个文件。

## §3 典型流程（启动 → 读 → 点 → 等 → 视觉确认）

```sh
S="bash scripts/device_ui.sh"
# ① 启动 + 确认前台（不是还停在桌面/商店）
$S launch com.example.app
$S foreground
# ② 读界面：先看有哪些文本/按钮
$S dump --texts
# ③ 操作 + 用 wait 断言，而不是 sleep 瞎等
$S tap '继续'
$S wait '广告' 10          # 出现 = 广告页到了
# ④ 需要视觉确认/看自绘页时截图，再让模型看图
$S screen /tmp/shot.png    # 之后 read_image /tmp/shot.png，或 mcp__phone__screen(image=true)
```

- 装/卸/清数据/日志/抓包不在这里，走 `references/device-verify.md` §1.2 的 `adb_device.sh`。
- 跑完验证（重启后是否仍 OK）：`$S apps <包名>` 或 `$S launch` + `wait` + `screen` 确认。

## §4 文本找不到怎么办（按顺序试，别乱点坐标）

1. **全量 dump**：`dump`（不加 `--texts` 会带上可点击但无文字的节点）→ 看 `bounds` 与 `clickable`。
2. **查 resource-id**：dump 输出不打印 resource-id，直接读缓存 XML：
   `grep -o 'resource-id="[^"]*"' /tmp/device_ui_dump.xml | sort -u | head -30`
   （`resource-id` 比文案稳定，适合按钮/输入框：拿它的 bounds 中心去 `tap X Y`）。
3. **文案被拆/是英文/是图标**：用更宽的正则（`tap '登.*录' -i`），或按 class 末段 + bounds 推断坐标 `tap X Y`。
4. **目标在屏幕外**：先滚动再 dump —— `swipe 540 1600 540 600 400`（上滑一屏），到底换
   `swipe 540 600 540 1600 400`（下滑）；列表页也可以 `key dpad_down` 逐项移动。
5. **dump 为空/节点极少**（自绘 UI、Canvas、加固页、无障碍被关）：切视觉——
   `mcp__phone__screen(image=true)` 或 `screen` 拉图 → `read_image` 看 → `mcp__phone__tap_xy` 点。
6. **dump 报错**（锁屏/无窗口/动画未停）：`key home` 回桌面再 `launch`；或用 `screen` 先看画面状态。

## §5 失败回退与分工

| 情况 | 处理 |
|---|---|
| adb 离线（`device_ui.sh` 报 `device '127.0.0.1:42777' not found` 之类，serial 由自动发现给出） | 一句话告知 + `bash scripts/device_adb_guard.sh open-hint` 问用户开；用户不开 → 转 MCP 视觉，**说明慢/不准** |
| 系统权限/授权弹窗（安装器、无障碍授权、KernelSU 授权） | 优先 adb `tap '允许'`；adb 点不到或属系统安全页 → 同屏截图后 `mcp__phone__tap_xy`，仍不行 `handoff` 让用户点 |
| 文本匹配到多个节点 | `dump --texts` 看顺序，先滚动/筛选让目标唯一，或直接 `tap X Y` |
| 点了没反应 | `foreground` 看是否还在原页 → `wait` 超时 → `screen` 看是否被弹窗/广告挡住 |
| FLAG_SECURE 页面 | 截图是黑图/读屏受限，属正常，**不要判成崩溃**；`handoff` 请用户确认 |
| 需要长按/双击/拖动 | 脚本没封装 → `input` 系列：`adb -s "$SERIAL" shell input swipe X Y X Y 800`（`SERIAL` 取 `status` 的「目标」，实测 `127.0.0.1:42777`；长按≈原地滑 800ms）；双击≈连按两次 `tap X Y`（脚本无 doubletap 子命令，需另行处理） |

## §6 安全与收工

- adb root = 整机 root：只在本次任务窗口开；**收工 `bash scripts/device_adb_guard.sh status` 只检查**
  两个调试开关值，**提醒用户自己去开发者选项手动关**（AI 不自动关、不改 settings、不跑 `adb usb`；
  `close` 只打印手动关闭步骤；自动关已移除，原因见 `references/adb-security.md`）。
- **`adb usb` ≠ 关开关**：它只切换 adbd 模式，设置里「USB 调试」开关还开着 —— 所以关闭交给用户手动最可靠。
- 别在公共网络开调试端口（`adb tcpip 5555` 或无线调试）；`adb devices` 出现陌生设备先 `adb disconnect`。
- 装/卸/清数据会丢数据或改系统状态：`uninstall`/`clear` 先征得用户同意（脚本强制 `--yes`）。
- 用过的临时文件（截图/dump）放 `/tmp`，别塞交付目录。
