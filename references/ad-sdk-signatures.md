# 广告 SDK 特征库与开关定位

## 一、按包名扫描（smali/dex 字符串）

| 广告平台 | 包名前缀 | 备注 |
|---|---|---|
| Google AdMob | `com/google/android/gms/ads`、`com/google/ads/mediation`、`com/google/android/ump`、`consent_sdk` | 最常见；公开 API 名保留（AdView/InterstitialAd），内部类被 R8 relocate |
| 字节穿山甲 Pangle | `com/bytedance/sdk/openadsdk`、`com/ss/android`、`com/bytedance/msdk` | 国内主流 |
| 腾讯优量汇 GDT | `com/qq/e`、`com/qq/e/ads` | 国内主流 |
| 快手广告 | `com/kwad`、`com/kwad/sdk` | |
| 百度百青藤 | `com/baidu/mobads` | |
| AdMob 中介 | `com/google/ads/mediation`（各适配器如 `com/google/ads/mediation/admob`） | |
| Mintegral | `com/mbridge/msdk` | 出海 |
| Unity Ads | `com/unity3d/ads`、`com/unity3d/services/ads` | |
| AppLovin | `com/applovin` | 出海 |
| ironSource | `com/ironsource`、`com/unity3d/ironsource` | |
| Vungle/Liftoff | `com/vungle` | |
| Amazon Ads | `com/amazon/device/ads` | |
| Meta/Facebook Audience | `com/facebook/ads` | |
| InMobi | `com/inmobi` | |
| Chartboost | `com/chartboost` | |
| AdColony | `com/adcolony` | |
| 厂商广告（华为/小米/OPPO/vivo） | `com/huawei/hms/ads`、`com/miui/ads`、`com/heytap`、`com/vivo/ads` | 国内分发 |

快速命令：
```sh
grep -rlE 'com/(google/android/gms/ads|bytedance/sdk/openadsdk|qq/e|kwad|baidu/mobads|mbridge|unity3d/ads|applovin|ironsource)' smali --include='*.smali' | head
```

## 二、资源字符串反查（不依赖代码可读性）

常见明文文案/键名（`res/values*/strings.xml`）：
`广告`, `广告开关适配`, `广告组件清理`, `Remove Ads`, `广告组件清理版`, `权益`, `权益`, `premium`,
`ad_loading`, `Banner`, `reward`, `interstitial`, `splash`, `ad_free`, `ad_remove`, `watch_ad`, `no_ad`

流程：
1. `grep -rn '广告\|Remove Ads\|ad_remove\|ad_loading\|reward' res/values*/strings.xml`
2. `grep -n 'ad_remove\|ad_loading\|banner' res/values/public.xml` → 拿 hex id
3. `grep -rn '0x7f1xxxx' smali --include='*.smali' | grep -vE 'R\$|smali/com/google'` → 命中管理类
4. 读该类：静态 `Z` 字段、`()Z` 判定方法、billing 回调、广告加载调用

## 三、常见"开关"模型（定位重点）

```smali
# 模式 A：静态布尔 = 已购/广告开关适配
.field public static d:Z                      # 购买回调里 sput-boolean 1
.method public static b()Z                    # 广告开关适配判定：d || consent
# 模式 B：Kotlin StateFlow 已购状态
.field public static final w:Lx9/z            # App.w.Y() 与 Boolean.TRUE 比较
# 模式 C：唯一广告加载点（R8 内部 API）
invoke-static {ctx, unitId, cb, cb2}, Lcom/google/android/gms/internal/ads/li;->a(...)V
```

补丁优先级：A/B 置真（进入官方"已购"模式）→ 删 C 的加载调用 → 清单清理 → 布局占位清理。

> 踩坑："正在加载广告…"的弹窗/提示可能在判定**之前**就展示——只把 `b()` 改 true 不够，
> 要把 StateFlow/已购标志的**初始值**也置 TRUE（走官方"已购"模式），否则仍会闪一下加载提示。

## 四、服务端驱动广告（无本地 SDK）

特征：广告来自 API（`bannerList`、`ad_slot_key`、`ad_show:`），Flutter 在 `libapp.so`、RN 在 `assets/index.android.bundle`。
思路：定位字符串表 → **等长替换广告 JSON 键/插槽键/上报标签**（保留 API 路径，避免 404 卡启动）→ 重打包签名 → 真机验证。
详见 `protection-map.md` §Flutter（服务端驱动广告）。

## 五、Google UMP 同意流程（AdMob 配套）

`consent_sdk` + `consent_sdk/i`（ConsentForm）+ `consent_sdk/b3`（ConsentInformation）。
广告组件清理时通常无需处理；若移除 AdMob 组件后启动崩溃，检查 App.onCreate 的 consent 初始化是否被直接调用（可 no-op 或保留）。
