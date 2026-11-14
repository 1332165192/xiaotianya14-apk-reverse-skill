# 反编译器选型：jadx / Fernflower(Vineflower) / ddc

> 三者的定位不同：**jadx 看整体结构**，**Fernflower 系列补细节**，**ddc 追求“能编译回去”的高质量输出**。
> 手机上都能跑（ddc 有 ARM64 静态版）；大工程建议远程主机。

## 1. jadx（默认，结构清晰）

```sh
bash scripts/decode.sh app.apk --out ./work     # 内部调用 jadx
# 或手动
jadx --deobf -d out app.apk
```

- 优点：GUI/CLI 都有、资源与代码一起看、搜索快、`--deobf` 能恢复部分标准名。
- 缺点：复杂控制流/混淆代码可读性一般，偶尔生成不能编译的伪代码。
- 适合：第一遍通读、找入口、找字符串与调用链。

## 2. Fernflower / Vineflower（补 Java 细节）

- 优点：lambda/泛型/内联还原更完整，和 jadx 交叉看能补上误读。
- 缺点：只处理 class/jar 或 dex 转换后输入，命令行体验不如 jadx 顺。
- 适合：jadx 出来的代码看不懂时对照。

## 3. ddc（Rust；手机上可直接装，输出质量优先）

项目：https://github.com/ejfkdev/ddc（MIT）。**ARM64 静态二进制，手机本机可跑**，
输出以“javac 能编译”为目标，适合需要把反编译结果当代码继续改/再编译的场景。

```sh
# 安装（版本与 SHA256 钉死，走 GitHub API）
bash scripts/install_ddc.sh

# 反编译
ddc app.apk out/

# 起 HTTP REST + OpenAPI
ddc serve --addr 127.0.0.1:8080

# 作为 MCP 工具服务（可接 AI Agent）
ddc mcp stdio
```

- 优点：速度快、输出可编译、同一份反编译结果能喂给 MCP/HTTP 下游。
- 缺点：新项目（v0.1.x），生态与社区资料少；复杂混淆仍要靠人。
- 适合：要“能编译回去的 Java 源码”、或想让 AI Agent 通过 MCP 直接查询 DEX。

## 4. 选择建议

| 场景 | 选 |
|---|---|
| 第一遍了解 App | jadx |
| 某个方法看不懂 | jadx + Fernflower 对照 |
| 要拿反编译结果继续改/编译 | ddc |
| 想让 Agent 通过 MCP 查询 DEX | ddc MCP |
| 手机内存紧张 / 超大工程 | 只在手机做侦察，反编译放到远程主机 |
