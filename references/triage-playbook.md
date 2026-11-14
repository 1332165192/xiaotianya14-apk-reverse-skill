# 15 分钟分诊（Triage Playbook）

> 拿到一个 APK，先花 15 分钟判断“这是什么货、值不值得往下做、走哪条路”。
> 分诊结论写进 `docs/REPORT-TEMPLATE.md`，证据用 `scripts/ledger.py` 落盘。

## 分诊清单（按顺序，每步 ≤3 分钟）

| 步 | 做什么 | 命令 | 看什么 |
|---|---|---|---|
| 1 | 包基本信息 | `python3 scripts/manifest_summary.py <解码目录>` | 包名、版本、组件、权限 |
| 2 | 是否加壳/加固 | `references/protection-map.md` 的特征表 + `lib/` 里的壳 so | 360/腾讯乐固/梆梆等特征 |
| 3 | 广告 SDK | `python3 scripts/analyze_ads.py <解码目录>` | 命中哪些 SDK、开关候选 |
| 4 | 权益/数值候选 | `python3 scripts/scan_premium.py <解码目录>` | 支付 SDK、`isVip` 类方法、数值字段 |
| 5 | 接口与鉴权 | `python3 scripts/find_api_calls.py <解码目录>` | 业务域名、token/签名头 |
| 6 | 完整性校验 | `references/protection-map.md` §五 | 签名校验、root/调试检测、Play Integrity |
| 7 | 服务端权威判断 | 候选里有没有“每次启动从服务端拉状态” | 有 → C 级，本地改基本无效 |

## 结论模板（分诊结束时写三行）

```text
分级：A 纯本地 / B 部分服务端 / C 服务端权威
可行目标：广告清理 / 本地权益 / 数值（可写哪些）
主要风险：加固壳 / native 校验 / 服务端回滚 / 封号
下一步：走 patch_method.py 还是先脱壳；是否需要 Frida 动态验证
```

## 什么时候停

- 命中加固且脱壳成本高于收益 → 如实说明，不硬做；
- 服务端权威 + 无抓包条件 → 停在分析结论，不承诺“能改”；
- 目标涉及他人权益（公共多人服、付费内容分发）→ 按 `AGENTS.md` 边界拒绝。
