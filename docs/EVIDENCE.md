# 证据分级与台账纪律

> 反向后最贵的错误不是“没做出来”，而是**把猜测当结论**。本文件规定：什么算证据、怎么记、报告里怎么写。

## 1. 三级证据

| 级别 | 含义 | 例子 |
|---|---|---|
| `observed` | 直接看到的东西（文件、日志、抓包、返回值） | `smali` 里 `isVip()Z` 返回 `const/4 v0, 0x0` |
| `measured` | 自己动手验证过的（改了确实生效/失效） | 改 `isVip` 后重打包，功能解锁且不崩 |
| `inferred` | 推断（文档/经验/旁证），**不能单独作为交付依据** | “这类 App 通常服务端校验” |

交付结论至少要有 `observed` + `measured`；只有 `inferred` 时必须写明“未验证”。

## 2. 用台账落盘

```sh
# 观察
python3 scripts/ledger.py observe "isVip 字段在 User.smali:12，getter 返回 0" --kind static --evidence "smali/com/x/User.smali:12"

# 结论
python3 scripts/ledger.py conclude "权益判定纯客户端，可本地改" --kind client-side --proof "改后重打包验证通过"

# 卡点（防止反复试同一路径）
python3 scripts/ledger.py stuck "签名校验在 native 层，Java 层放行无效" --tried "签名 killer / hook isSignatureValid"

# 查看
python3 scripts/ledger.py query
```

台账默认 `work/ledger.json`，建议和你的解码目录放一起；**不进发行包**。

## 3. 报告里怎么写

- 每条结论后面标注证据级别：`（observed）`、`（measured）`、`（inferred）`；
- “不可行”类判词必须给出卡在哪一层（校验/加固/服务端/时间），并说明试过什么；
- 不确定就写“未验证”，不要用“应该/可能”混过去。

## 4. 常见坏习惯

- 只跑了一个脚本就把输出当结论（脚本给的是**候选**，不是事实）；
- 改了没验证就写“已解决”；
- 同一路径失败 3 次还在重试，不落 `stuck`、不换路。
