# Frida 脚本库（手机端常用 hook）

> 仅用于**自己拥有或已获授权**的 App 的安全研究；请遵守 `AGENTS.md` 的同意边界。

| 脚本 | 作用 |
|---|---|
| `ssl_unpinning.js` | 关闭常见证书固定（OkHttp / TrustManager / Conscrypt / HostnameVerifier）|
| `anti_debug_bypass.js` | 绕过 ptrace / TracerPid / debug flag 等常见反调试 |
| `exit_blocker.js` | 拦截 `exit` / `abort` / `Process.killProcess`，避免被自毁逻辑踢出 |
| `root_bypass.js` | 常见 root 检测（su 路径、Magisk、测试 key）返回伪装结果 |
| `frida_hider.js` | 隐藏 Frida 端口/线程/内存特征（配合改名换端口）|
| `function_patcher.js` | 按类名+方法名替换返回值（改判定/数值的快速验证）|

## 用法

```sh
# 0) 设备已 root，先准备 frida-server
bash scripts/frida_server_prep.sh

# 1) spawn 启动并注入
bash scripts/frida/run_frida.sh -s ssl_unpinning.js -p com.example.app

# 2) 已运行进程 attach
bash scripts/frida/run_frida.sh -s anti_debug_bypass.js -n com.example.app
```

`function_patcher.js` 的类名/放回值在文件顶部改，或用 `-P` 传参（见文件内注释）。

## 注意

- 这些脚本只改变运行期行为，**不持久**；要出成品仍要回到静态补丁（`patch_method.py` / `so_patch.py`）。
- 反作弊强的游戏/金融类 App 会检测 Frida；`frida_hider.js` 只能降低概率，不保证。
- 端口：默认 `27043`（`27042` 是宿主自带实例，脚本会拒绝使用）。
