# LSPosed 模块：不改包也能改行为的备选路径

> 适用：重打包必崩（native 签名校验、加固壳、完整性校验），或不方便重新安装原 App 的场景。
> 边界：只对**自己拥有或已获授权**的 App 做；模块本身不下发、不传播。

## 1. 什么时候选它

- 静态补丁后 App 启动崩溃或功能异常，且判断是校验/加固导致；
- 想保留原 APK 签名与数据（不想卸载重装）；
- 只想改少量运行期行为（一个判定、一个返回值）。

代价：需要 LSPosed 环境（root + Zygisk）、模块只在自己设备生效、目标 App 更新可能失效。

## 2. 最小步骤

1. **定位 hook 点**：先用 `scripts/scan_premium.py` / `patch_method.py find` 找到类与方法；
   运行期用 `scripts/frida/function_patcher.js` 或 `hook_encryption_algo.js` 验证“改了确实有效”。
2. **建模块工程**：`lsposed_scaffold` 类模板（模块入口 `IXposedHookLoadPackage` + `handleLoadPackage`）。
3. **写 hook**：在目标包名判断后 `XposedHelpers.findAndHookMethod(类名, loader, 方法名, 参数类型, XC_MethodHook)`。
   参数类型必须写全，混淆后的短名以反编译结果为准。
4. **安装模块**：编译 APK → 安装 → LSPosed 里启用 → 勾选目标 App → 重启目标 App。
5. **验证与回滚**：确认目标功能生效、其他功能不崩；出问题在 LSPosed 里停用模块即可回滚。

## 3. 风险

- 模块与目标 App 版本强绑定，App 更新后类名/方法签名变化就会失效或崩溃；
- LSPosed 本身是 root 环境特征，目标有反框架检测时会被识别；
- 公共多人服里影响其他玩家的功能不做（见 `AGENTS.md` 边界）。

## 4. 与静态补丁的取舍

| | 静态补丁（改包） | LSPosed 模块 |
|---|---|---|
| 保留原签名/数据 | 否（要重签） | 是 |
| 被完整性校验拦截 | 容易 | 不触发（没改包）|
| 可分发给别人 | 是 | 只在自己设备 |
| 维护成本 | 包版本变就要重打 | 模块要跟版本 |
