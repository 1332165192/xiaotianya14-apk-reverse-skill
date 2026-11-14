# 接口 / 鉴权头 / 第三方域名提取

> 目标：从反编译产物里稳定捞出“真实业务接口”和“鉴权方式”，并过滤掉第三方 SDK 的噪音。

## 1. 先跑脚本

```sh
python3 scripts/find_api_calls.py <jadx输出或smali目录>
python3 scripts/manifest_summary.py <apktool解码目录>
```

脚本会给出 URL、可疑 header、调用点；**结果里一半是第三方 SDK**，用下一步过滤。

## 2. 第三方域名过滤

- `references/third-party-hosts.txt` 是常见 SDK 域名清单，先排除；
- 剩下的域名按“是否和业务功能相关”排序（登录、订单、内容接口优先）；
- 自研域名常见特征：公司英文名、`api.`/`gw.`/`open.` 前缀、短域名。

## 3. 鉴权头识别

| 头 | 说明 |
|---|---|
| `Authorization: Bearer …` | OAuth/JWT，找 token 生成处（`Bearer ` 字符串）|
| `token` / `access_token` / `session` | 自研鉴权，找取值来源（SharedPreferences/内存）|
| `sign` / `signature` / `timestamp` / `nonce` | 请求签名，找签名函数（常见 MD5/HMAC）|
| `X-*` 自定义头 | 风控/设备指纹，先记录，不急着改 |

## 4. 调用链梳理

按顺序记录：`入口（Activity/Fragment）→ ViewModel/Presenter → Repository/Manager → 网络层（OkHttp/Retrofit）`。
每层写一条“类名 + 方法 + 关键字符串”，后面打补丁/抓包时直接跳转。

## 5. 输出到报告

用 `docs/REPORT-TEMPLATE.md` 的“证据链”段落：现象 → 依据（文件/类/方法/抓包）→ 结论。
