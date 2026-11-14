# 权限链路：怎么才算「真的检查过 root」

> 核心原则：**root 检查 = 尝试提权**。没有入口就查不出「能不能用」，
> 只能查「设备有没有 root 方案」——两层必须分开说，否则就是循环论证。

## 1. 两层检查（脚本：`scripts/device_perm_chain.sh`）

```sh
bash scripts/device_perm_chain.sh            # 能力层 + 迹象层 + 结论
bash scripts/device_perm_chain.sh --channel  # 只输出通道名，脚本用
# exit：0=有真 root 能力  2=仅 shell 级能力  1=无能力（只能查迹象）
```

### ① 能力层（唯一算「真检查」）

- 判据：**执行一次真实特权操作**（读 `/data/adb`、`/data/misc/adb`、`/data/system/users/0`），成功 = 真 root；
- **不要用 `id -u` 判断**：proot 的 fakeroot 让 `id -u` 恒为 0（连 `/system/bin/sh -c id` 也显示 0），全是假象；
- 入口四条，按可靠性排：
  1. **adb root**（无线调试/USB）→ `adb shell id -u=0` 且能读 `/data/adb`；
  2. **本机 su**（非 proot 环境才可能）；
  3. **App 侧 su**（KernelSU/Magisk 已授权本应用）→ `/system/bin/su -c 'test -r /data/adb'`；
  4. **Shizuku rish** → 仅 shell uid=2000，**不是 root**。
- 四者都没有 → 能力 = `none`，**如实说「无法验证」**，不要拿迹象冒充能力。

### ② 迹象层（回答「设备有没有 root 方案」，不代表你能用）

| 证据 | 命令（无需 root 即可试） | 说明 |
|---|---|---|
| KernelSU 模块 | `grep -i kernelsu /proc/modules` | 最强信号，app 也能读 |
| KernelSU 符号 | `grep -m1 '\[kernelsu\]' /proc/kallsyms` | 模块名可见、地址为 0 |
| su 隐藏特征 | `cat /system/bin/su` → ENOENT，但 `stat` 有 | KernelSU 对未授权进程隐藏 su |
| 内核版本后缀 | `grep -iE 'kernelsu\|apatch\|magisk' /proc/version` | LKM 方案不改版本号，缺失 ≠ 没 root |
| 适配状态 | `getprop ro.boot.verifiedbootstate / ro.boot.flash.locked` | 多数 root 需适配；locked + 内核集成 KSU 也可能 |
| root 管理器 | `pm list packages`（需 adb shell）或 MCP `mcp__phone__apps` | 装了管理器 ≠ 当前进程有权限 |

- 典型状态：设备装了 KernelSU、su 被隐藏，但本进程 SELinux=`untrusted_app` 没被授权 → 能力层仍是 `none`。

## 2. 为什么 proot 里查不出真 root

- 进程在 `untrusted_app_27` 域，无 CAP_NET_RAW，`/system/bin/su` 打不开（被 KernelSU 隐藏）；
- proot 的 fakeroot 让 `id`/`whoami` 全显示 root，**只改显示、不改权限**；真实文件访问仍按 Android uid 判定；
- 所以任何结论都必须用「真实 I/O 成功与否」验证，而不是看 uid 数字。

## 3. 实测样例（本机 2026-11-13）

```text
能力层: adb root ✅（能读 /data/adb，context=u:r:ksu:s0）；本机 su ❌；App 侧 su ❌（open ENOENT）；rish ❌
迹象层: /proc/modules=kernelsu ✅；su 隐藏 ✅；verifiedbootstate=green / flash.locked=1；
        管理器=me.weishu.kernelsu, moe.shizuku.privileged.api
结论: 通道=adb-root（唯一入口）；设备有 KernelSU，但本进程未获授权
```

## 4. 用户问「没有 adb root 权限怎么检查」怎么答

- 直接说：**没有入口就无法验证能力**，这是原理限制，不是偷懒；能查的是迹象层；
- 想要真正拿到能力：让用户开无线调试/USB 调试（adb 入口），或在 KernelSU 里给 App 授权（App 侧 su 入口）；
- 别把「设备有 KernelSU / 装了 Magisk」说成「有 root 权限」，除非能力层真的读成功了。

## 5. 铁律

- 不擅自开/关 adb、不配对 Shizuku、不改 settings；root 管理器授权由用户自己点；
- 能力层结论优先；迹象层只写「设备侧 root 方案」，用词要区分；
- 收工提醒用户手动关两个调试开关（`device_adb_guard.sh status` 只读复核）。
