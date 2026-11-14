# 输入法 / 打字安全（手机自动化必读）

> 场景：AI 用手机操控（`mcp__phone__type` / adb `input text` / `device_ui.sh text`）往输入框打网址、账号、搜索词时，
> 被用户的**中文输入法（拼音/双拼/九键）**吃掉：英文被拼成中文、候选框弹出、
> 回车变成上屏、页面卡死甚至"死机"。
>
> 根因：`input text` 动态加载的是按键，输入法会按当前方案（拼音/双拼/九键）做组合，
> 不会原样输入 ASCII。**不是手机坏了，是输入法在组合。**
>
> 本文 adb 命令里的 `$SERIAL` 用**自动发现**结果（`bash scripts/device_adb_guard.sh status` 的「目标」；
> 实测 `127.0.0.1:42777`，5555 只是 `adb tcpip 5555` 模式示例）。

## §1 第一原则：能不打字就不打字

| 目的 | 正确做法 | 不要做 |
|---|---|---|
| 打开/测试某个网址 | `mcp__phone__open(url="https://…")`；或 adb `am start -a android.intent.action.VIEW -d "https://…"` | 打开浏览器→点地址栏→`type` 打网址 |
| 打开 App 某页面 | 深链 / `intent` / `open(app=包名)` | 在搜索框里打 App 名 |
| 搜索内容 | 能复制就复制：`mcp__phone__clipboard(set=…)` → 长按输入框→粘贴 | 用 `type` 打中文/英文混合串 |
| 填表单 | 剪贴板粘贴优先 | `type` 多段文本 |

> `type` 只适合：**纯 ASCII 短文本 + 已确认当前输入法是英文/数字键盘**。
> **真要打字时的统一入口**：`bash scripts/device_ui.sh text '<文本>'`（内部转调 `device_input.sh`，同一套安全规则；
> 中文输入法下默认拒绝，加 `--switch-ime` 才临时切英文键盘，打过自动切回）。

## §2 检测用户用的是什么输入法

### 2.1 有 adb root 时（准确）
```sh
adb -s "$SERIAL" shell 'settings get secure default_input_method'
adb -s "$SERIAL" shell 'ime list -s'                 # 已启用/可用的 IME
adb -s "$SERIAL" shell 'settings get secure enabled_input_methods'
# 判断是不是中文输入法：包名/类名里出现 sogou/baidu/iflytek/xunfei/qq/sohu 等
# 具体方案（拼音/双拼/九键）：读输入法自己的 prefs（需 root）
adb -s "$SERIAL" shell 'ls /data/data/com.sohu.inputmethod.sogou/shared_prefs/'
adb -s "$SERIAL" shell 'grep -ilr "xiaohe\|双拼\|shuangpin\|九键\|pinyin" /data/data/com.sohu.inputmethod.sogou/shared_prefs/ | head'
```
- 示例输入法：`com.sohu.inputmethod.sogou`；百度：`com.baidu.input`；讯飞：`com.iflytek.inputmethod`；
  Gboard：`com.google.android.inputmethod.latin`；AOSP 键盘：`com.android.inputmethod.latin`。
- **双拼通常是输入法里的"双拼方案"设置**（不是独立 App），所以按包名只能判定"中文输入法"，
  具体方案要读 prefs 或问用户一句。

### 2.2 没有 adb 时（MCP 路径）
1. `mcp__phone__apps(query="输入法")` 看装了哪些输入法；
2. `mcp__phone__screen` 看当前键盘（候选栏/拼音提示出现就是中文态）；
3. 拿不准就直接问用户：「你现在用的是拼音还是双拼？我打网址前确认一下，免得被拼成中文。」

## §3 安全打字的三条路（按优先级）

### 路 1：不经过输入法（首选）
```sh
# 开网址（不碰键盘）
adb -s "$SERIAL" shell am start -a android.intent.action.VIEW -d "https://example.com"
# 或走 MCP
mcp__phone__open(url="https://example.com")
```

### 路 2：剪贴板粘贴（次选，不会触发组合）
```text
1. mcp__phone__clipboard(set="https://example.com")     # 写剪贴板
2. 点一下输入框（mcp__phone__tap）
3. 长按输入框 → 粘贴（tap_xy long 或菜单"粘贴"）
4. 回车/发送
```
> 粘贴是直接插入字符，不经过拼音组合；地址栏/搜索框一般都支持长按粘贴。

### 路 3：临时切英文键盘再 `input text`（最后手段）

> 推荐用封装好的入口（内部等价本路，且自动记录/切回原输入法）：
> `bash scripts/device_ui.sh text '<文本>' --switch-ime`；直接敲 adb 命令的写法仅作原理参考。
```sh
# 列出可用的英文/中性键盘
adb_device.sh   # 或直接：
adb -s "$SERIAL" shell 'ime list -s' | grep -iE 'latin|gboard|aosp'
# 切换（示例）
adb -s "$SERIAL" shell 'ime set com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME'
adb -s "$SERIAL" shell 'input text "https://example.com"'    # 空格要写 %s
# 用完切回（务必！否则用户打字习惯被打乱）
adb -s "$SERIAL" shell 'ime set com.sohu.inputmethod.sogou/.SogouIME'
```
- 没有英文键盘可切时：**不要硬打**，走手 2 或让用户自己打。
- 切换会改用户设置，**做完必须恢复**，并在回复里说明你临时切过键盘。

## §3.1 统一入口：`device_ui.sh text`（推荐）

```sh
# 安全打字入口（内部调用 device_input.sh，规则完全一致）
bash scripts/device_ui.sh text 'hello@example.com'                 # 中文输入法 → 默认拒绝并给出替代方案
bash scripts/device_ui.sh text 'hello@example.com' --switch-ime    # 允许临时切英文键盘，打完自动切回
bash scripts/device_ui.sh text 'hello' --dry-run                   # 只打印将执行的 adb 命令，不动设备
```

- 拒绝时（退出码 2）仍按 §3 优先改用剪贴板 / `device_input.sh url` 直开网址；
- 切换键盘会改用户设置：脚本打完会自动切回，但仍需在回复里说一句"临时切过英文键盘，已切回"。

## §4 判断"输入法是否在组合"的自检
- 打完字后 `mcp__phone__screen`：出现候选栏/中文 → 说明被组合了，**立刻停止打字**，不要连续重试（会越卡越死）；
- 页面卡住：`mcp__phone__key(key="back")` 收键盘，再读屏；必要时 `handoff` 让用户接管输入；
- 绝对不要连续发 `type` + `KEYCODE_ENTER` 硬怼：IME 组合态下回车会把拼音上屏，导致跳错页/死循环。

## §5 交付与记录
- 用过临时切键盘/剪贴板：在回复里一句话说明（"我临时切过英文键盘，已切回"）；
- 把输入法方案记进案例（`field-journal/`）：机型 + 输入法 + 方案（如"拼音/双拼"），
  下次同一用户直接走安全路径，避免重复踩坑。

## §6 常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 打英文变成中文/候选 | 输入法在组合 | 停手，改用剪贴板/URL 直开 |
| 打完回车页面乱跳 | 组合态下回车=上屏候选 | 先 back 收键盘，别连发 |
| `input text` 没反应 | 输入框未聚焦/被遮挡 | 先 `tap` 聚焦再打 |
| 切换键盘后用户打字异常 | 没恢复默认 IME | `ime set <原包名/类名>` 切回 |
| 键盘弹不出 | 焦点在非输入区域 | 点输入框，不是点旁边文字 |
