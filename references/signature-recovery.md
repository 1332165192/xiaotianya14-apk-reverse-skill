# 签名 / 加密参数逆向流程（自研）

> 适用：自己拥有或已获授权 App 的接口分析。线上校验类功能无法靠本地修改绕过，本流程只用于**理解与复现**接口签名。
> 不包含：绕过第三方风控、破解付费、攻击他人服务。

## 1. 先抓包，定位字段

- 用 mitmproxy / Frida 抓请求，找这些字段：`sign`、`sig`、`token`、`timestamp`、`nonce`、`access_key`、`X-Sign`、加密的 `data`。
- 记录：URL、method、headers、body 原文、返回码；至少 3 组不同请求做对比。

## 2. 在代码里找生成点

```bash
# 在 jadx 输出里搜字段名/方法名
grep -rn "sign\|X-Sign\|nonce\|timestamp" jadx/sources --include='*.java' | head -50
python3 scripts/find_api_calls.py jadx --auth --secrets
```

重点看：
- 网络层拦截器（OkHttp `Interceptor`、Retrofit `@Headers`）
- 工具类（`SignUtil`、`MD5Util`、`EncryptUtils`、`HmacSHA256`）
- native 方法（`native` 声明 → `lib*.so`，用 `so_patch.py info/find` 定位符号）

## 3. Frida 验证入参与返回值

```bash
python3 scripts/hook_gen.py --class com.example.SignUtil --method sign --args --return original
# 生成的 hook.js 用 frida 加载，确认 sign 的输入、输出与抓包一致
```

## 4. 本地复现

常见组合：

| 组合 | 特征 |
|---|---|
| MD5(拼接串) | 32 位 hex，字段排序后拼接 |
| HMAC-SHA256(key, data) | 64 位 hex，有固定 key |
| AES-CBC + Base64 | body 是 Base64，长度 16 倍数 |
| RSA | 密文长、有公钥/私钥线索 |
| 时间戳/nonce 参与 | 每次请求 sign 不同 |

用 Python 复现后，和抓包结果**逐字节对比**；不一致就回到 hook 看中间值。

## 5. 记录与验证

- 把「字段 → 生成函数 → 输入 → 输出」写进报告；
- 用同一套参数本地算，和服务器返回对比；
- 线上校验失败就说明有服务端密钥/动态挑战，不要硬绕，如实记录限制。

## 6. 常见坑

- 字符串被加密（StringFog/加固）：先 dump DEX 或用 Frida 动态取；
- 签名在 native：`so_patch.py info` 看导出符号，Frida `Interceptor.attach` 跟参数；
- 多态/反射：静态找不到就动态 hook 基类方法；
- 时间戳/随机数：本地复现要固定这些值再对比。
