# MCP 工具接入（JADX / Ghidra / IDA / Burp）

> 本技能在**手机本机**跑核心流程；下面这些 MCP 属于“增强”，能接就接，接不上不影响主流程。
> 注意：远程主机/桌面端接 MCP 更容易；手机本机受 CPU/内存限制。

## 优先级

| 工具 | 用途 | 手机本机可行性 |
|---|---|---|
| JADX（MCP 或 CLI） | 反编译后按类/方法检索、交叉引用 | 高（`scripts/decode.sh` 已含 jadx） |
| Burp / mitmproxy MCP | 抓包与请求重放 | 中（先看 `references/protection-map.md` 证书固定） |
| Ghidra MCP | native 符号/结构恢复 | 低（内存占用大，建议远程主机） |
| IDA MCP | native 深度分析 | 低（同上） |

## 接入约定

1. MCP 只负责“取信息”，**决策仍在 `SKILL.md` 的流程里**。
2. 抓包前先确认证书固定方案（`references/protection-map.md` §六）。
3. 远程主机跑 Ghidra/IDA 时，把产物（导出符号、反编译片段）带回手机侧写进报告。
4. 不要把 App 的私有数据/密钥贴进对话或 issue；报告里用占位符。
