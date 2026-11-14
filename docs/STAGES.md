# 六阶段总控（手机端）

> 把“拿到一个 APK”拆成 6 个可验收的阶段。每阶段有入口脚本、产物、以及“什么时候可以往下走”的门槛。
> 仅用于自己拥有或已获授权应用的安全研究（见 `AGENTS.md`）。

| 阶段 | 目标 | 入口 | 产物 | 过门条件 |
|---|---|---|---|---|
| 1 侦察 | 包结构、组件、加固/广告 SDK | `scripts/decode.sh` → `manifest_summary.py` → `analyze_ads.py` | 组件清单、SDK 列表、加固判断 | 知道有没有壳/反调试 |
| 2 协议/数据 | 接口、存档、加密位置 | `find_api_calls.py` + `references/protection-map.md` | 接口清单、存储点 | 抓到关键接口或存档 |
| 3 逻辑定位 | 权益/数值/广告开关 | `scan_premium.py` | 候选类/方法/字段/资源 ID | 找到 1~2 个可改点 |
| 4 补丁 | 静态或动态改 | `patch_method.py` / `so_patch.py` / `scripts/frida/*` | 补丁记录（改了什么、备份在哪） | dry-run 通过，真机行为验证 |
| 5 验证 | 重打包签名 + 真机 | `build_sign.sh` + `references/device-verify.md` | 可安装 APK + 验证结论 | 启动、目标功能、不崩 |
| 6 交付 | 报告 + 复现说明 | `docs/REPORT-TEMPLATE.md` | 报告 + field-journal 条目 | 别人按报告能复现 |

## 门禁原则

- 阶段 4 之前必须有阶段 3 的候选清单；没有候选就回到阶段 2/1，不要盲改。
- 每改一处就 `.bak` 备份并重新打包验证，不要攒一批再试。
- 服务端权威（C 级）在阶段 3 就要识别出来并如实说明“本地改不了”，不要硬做。
