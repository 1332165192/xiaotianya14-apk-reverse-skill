# 原生层模糊测试（AFL++ / ASan）——什么时候值得在手机上做

> 思路参考 [alvinhayy/Mobile-ReverseSkill](https://github.com/alvinhayy/Mobile-ReverseSkill)（★11，设备端 AFL++）。
> 本机没有预装 AFL++；这是**可选进阶**，不要当默认流程。

## 适合的场景

- 目标是自研/授权 App 的 **native 库（.so）**，需要找崩溃/内存错误，而不是改功能；
- 已经能定位到具体 `.so` 与入口函数（`so_patch.py info` / `r2` 先看导出）；
- 有 root（fuzzing 需要 ptrace/ASan 注入）且能接受手机发热、耗时。

## 手机上怎么起步（概念流程）

```sh
# 1) 拿目标 .so（从 APK 里取）
unzip -o app.apk 'lib/arm64-v8a/*.so' -d /tmp/native

# 2) 看导出与字符串（先确认入口，别盲 fuzz）
bash scripts/so_patch.py info /tmp/native/libtarget.so

# 3) 设备端需要：AFL++ 的 android 构建 + 目标可执行 harness
#    （原生库不能直接 fuzz，要写一个小 harness 调用目标函数；这部分在 PC 上做更现实）
adb push harness /data/local/tmp/ && adb shell chmod 755 /data/local/tmp/harness

# 4) ASan 版本需要在编译时开启：-fsanitize=address -fno-omit-frame-pointer
```

## 现实建议

- **手机只做“取样”**：确认哪个 `.so`、哪个函数值得测；真正的 AFL++ 循环放到 PC/服务器上跑；
- 手机上跑 fuzz 的收益通常低于成本（发热、耗电、速度慢）；
- 本技能默认不提供 fuzzing 脚本（避免把设备拖死）；需要时按上面流程自建，或在 PC 上用 `afl++`。

## 与静态分析的关系

fuzz 只能证明“这里有崩溃”，不能替代静态分析定位逻辑；先走 `references/protection-map.md` 与 `scan_premium.py`，
把范围缩小到一个函数再考虑 fuzz。
