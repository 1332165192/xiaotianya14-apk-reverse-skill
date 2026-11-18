# 配套脚本清单（`$SK/scripts/`）

> 开工先 `bash scripts/toolcheck.sh`；缺工具 `bash scripts/install_tools.sh`（缓存/镜像/官方源，装完自检），换机重装同样一条命令补齐（本机已齐全）。

| 脚本 | 用途 |
|---|---|
| `decode.sh` | 一键 jadx + apktool 落盘 + Triage 摘要（包名/java/smali/so） |
| `manifest_summary.py` | 抽 manifest：包名、启动 Activity、权限、组件、debuggable/allowBackup |
| `analyze_ads.py` | 广告特征扫描：SDK 包名、广告字符串+资源 ID 反查、开关候选类 |
| `merge_splits.py` | AAB 拆分包资源/原生库合并进 base（跳过 split 的 public.xml） |
| `fix_dollar_resources.py` | 修复 `$mtrl_*` 等非法资源名（重命名+public.xml+引用，资源 ID 不变） |
| `manifest_clean.py` | 清拆分包标记、广告权限、AdMob 组件与 meta-data |
| （npm/Release 包不含） | pairip 授权壳：发布包不提供自动放行脚本，手动补丁见 `references/patch-patterns.md` §五 |
| `install_tools.sh` | 自动装缺失工具：apt / pip / frida-server / jadx（缓存优先，失败回退镜像），装完自检；`--re` 补深度逆向/抓包，`--community` 按需装社区工具（Vineflower/dex2jar/bundletool/unicorn），`--net` 抓包编译链|
| `toolcheck.sh` | 工具链自检（新会话先跑，退出码 0 = 齐）|
| `adb_device.sh` | **真机 root 通道**（adb）：`check` / `frida start\|stop\|status` / `tcpdump start\|stop\|pull` / `logcat` / `install` / `uninstall` / `clear` / `start` / `stop` / `info` / `screencap` / `push` / `pull`（`-h` 看全量；serial **自动发现**：5555 或无线调试随机端口如 `127.0.0.1:42777`，可 `--serial`/`ADB_SERIAL` 指定）|
| `device_input.sh` | 输入法安全：`detect`（识别拼音/双拼/九键）/ `url`（不打字开网址）/ `type --switch-ime`（临时切英文键盘）/ `ascii list\|on\|off` |
| `device_adb_guard.sh` | adb 通道守口（**只检查、不自动关**）：`status` 只读检查（自动发现目标 serial/在线/root/两调试开关/是否重启过）、`close` **只打印手动关闭步骤**（不改 settings、不跑 `adb usb`）、`open-hint` 恢复步骤、`policy` 开/关规则 |
| `device_perm_chain.sh` | **权限链路检测（只读，两层）**：能力层（adb root / 本机 su / App 侧 su / rish，真提权成功才算）+ 迹象层（/proc/modules 的 kernelsu、su 隐藏、适配状态、管理器包名）；`--channel` 只输出通道名（exit 0=真 root / 2=shell 级 / 1=无）；判据见 `references/perm-chain.md` |
| `device_ui.sh` | **adb 界面操控**：`foreground` / `launch` / `dump` / `tap` / `swipe` / `key` / `text` / `screen` / `wait` / `apps`（adb 优先的混合操控入口，见 `references/device-control.md`）|
| `frida_server_prep.sh` | 复制 frida-server 到 /sdcard + 打印用户操作卡（adb 通道不可用时的兜底）；`--auto` 走 adb 自动启动、`--status` 验证、`--stop-hint` 关闭（serial **自动发现**：5555 或无线调试随机端口，可 `--serial`/`ADB_SERIAL` 指定） |
| `identity_report.py` | 本地身份卡：包名/版本/签名指纹/SDK/ABI/权限/结构，**替代上网搜应用判身份** |
| `scan_premium.py` | 付费权益 + 数值定位扫描：付费点 SDK、权益判定类、货币字段、存档点、接口 URL、完整性校验、native 线索 |
| `find_api_calls.py` | 扫接口线索：硬编码 URL/ws、Retrofit 注解、OkHttp/Volley/WebSocket、GraphQL、认证参数（Authorization/sign/token）、可疑密钥；`--json`/`--report` |
| `patch_method.py` | 定点补丁：方法返回固定值（权益判定恒真 / 数值改大）、静态字段初值、方法签名查找；支持 `--dry-run`/`--restore`，自动 `.bak` |
| `so_patch.py` | **原生 .so 补丁**：`info`/`find`（符号·字符串）/ `patch` NOP·恒真·常数返回·hex（按 VA/Offset/符号，自动 .bak）/ `restore` |
| `build_sign.sh` | 一键打包(--use-aapt2)→zipalign→keystore→apksigner→verify |

脚本均已在实测（单元测试 + 真实 smali 补丁 + 端到端打包签名）。
