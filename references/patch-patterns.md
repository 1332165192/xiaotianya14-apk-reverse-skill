# 补丁模式详解（smali / 清单 / 布局 / 资源）

## 一、smali 补丁

### 1. 布尔开关（最常用）

```smali
# 恒真：方法开头插入（原代码保留为死代码，合法）
.method public static b()Z
    .locals 1

    const/4 v0, 0x1

    return v0
    # …原逻辑（不可达，assembler 接受）…
.end method
```

```smali
# 静态初始化末尾置位（已购/广告开关适配标志）
    const/4 v0, 0x1
    sput-boolean v0, Lz2/k;->d:Z
```

```smali
# Kotlin StateFlow 初始值改成 TRUE（App.w 之类）
    sget-object v0, Ljava/lang/Boolean;->TRUE:Ljava/lang/Boolean;
    invoke-static {v0}, Lx9/a0;->a(Ljava/lang/Object;)Lx9/z;
    move-result-object v0
    sput-object v0, Lapk/dex/decompiler/App;->w:Lx9/z;
```

### 2. 方法提前返回

```smali
.method private startPaywallActivity(Landroid/app/PendingIntent;)V
    .locals 2

    return-void      # ← 插入这一行（后面原代码为死代码）
    …原逻辑…
.end method
```

要点：
- 插入位置在 `.locals` 之后、第一条指令之前；annotation 块在中间时插入到 `.locals` 后仍合法（实测 apktool 2.7 可以重建）。
- 无返回值方法插 `return-void`；返回 `Z` 的插 `const/4 v0, 0x1` + `return v0`。

### 3. 删除调用

```smali
# 无返回值：直接删整行（安全）
invoke-static {p0, v1, v0, v2}, Lcom/google/android/gms/internal/ads/li;->a(Landroid/content/Context;Ljava/lang/String;Ly3/e;La4/a;)V
```

```smali
# 有返回值：不能硬删，改成给结果寄存器赋默认值
const/4 v0, 0x0        # 例：方法返回对象/布尔时占位
# 原 invoke-…/move-result-object v0 两行整体替换为上面一行
```

### 4. 关键类定位技巧
- `sget-boolean` / `sput-boolean` + 静态字段 → 开关标志。
- `.method public static …()Z` 且调用方先判断再加载广告 → 判定方法。
- `invoke-static` 到一个 `La/a;`/工具类的字符串解密方法（`$/$;->$(I)`) → StringFog 加密点（读不到明文，别硬啃）。
- R8 把 SDK 内部类 relocate 到短包（`a5/f4/h4/o6`）→ 应用可能直接调 `com/google/android/gms/internal/ads/li;->a(...)`，不是公开 AdView。

## 二、AndroidManifest.xml

| 操作 | 说明 |
|---|---|
| 删拆分包标记 | `android:requiredSplitTypes="base__abi,base__density"`、`android:splitTypes=""`（合并通用 APK 必需） |
| 删广告组件 | `AdActivity`、`AdService`、`MobileAdsInitProvider`、`NotificationHandlerActivity`、`OutOfContextTestingActivity` |
| 删 meta-data | `com.google.android.gms.ads.APPLICATION_ID`、`com.google.android.gms.ads.flag.*` |
| 删广告权限 | `com.google.android.gms.permission.AD_ID`、`ACCESS_ADSERVICES_AD_ID/ATTRIBUTION/TOPICS` |
| 保留 | INTERNET、ACCESS_NETWORK_STATE、BILLING、CHECK_LICENSE（授权壳放行后不再依赖）、Firebase/analytics |
| 调试标记 | 删 `android:debuggable`；如需要可留 `allowBackup` |

用 `scripts/manifest_clean.py`（自动处理自闭合/带子元素组件）。

## 三、布局与资源

- 广告占位：删占位文字、容器 `layout_height` 改 `0.0dip`；**保留父容器 id**（代码可能 findViewById）。
- 购买入口：文本在 `res/values*/strings.xml`；若应用有"已购模式"，一般由代码控制显示，我们只做状态置真。
- 资源 ID 反查：`res/values/public.xml` 里 `name="xxx" id="0x7f1…"` → `grep -rn '0x7f1…' smali`。
- 资源名修复：`$` 开头（`$mtrl_*`）→ `fix_dollar_resources.py`（重命名 + public.xml + 引用，ID 不变，smali 数字引用不受影响）。

## 四、拆分包合并（AAB → 通用 APK）

1. 语言/密度 split 的 `res/values-xx`、`res/drawable-*` 拷进 base 的 `res/`（**跳过 split 的 `values/`**，那是 public.xml 片段，会破坏资源表）。
2. ABI split 的 `lib/<abi>/*.so` 拷进 base 的 `lib/`。
3. 清单删 `requiredSplitTypes`/`splitTypes`。
4. 重新打包 + 签名（见 `build_sign.sh`）。

## 五、授权/付费点（pairip 等）

- pairip：`LicenseContentProvider.onCreate` → `LicenseClient` → 未授权 → 弹窗/跳 Play/30s 杀进程。
- 补丁：`pairip_bypass.py`（onCreate 返 true + 4 个拦截方法 return-void）。
- 其他授权形态：签名校验（对比 cert hash）、`CHECK_LICENSE`、自研序列号/激活码 → 找返回值判定点，改成恒真；或直接 no-op 校验调用。
- 付费点判断：billing `Purchase` 回调里 `sput-boolean 1` 的开关 → 置真（等于已购）。

## 六、Flutter / React Native

- **Flutter**：`libapp.so`（Dart AOT）。广告若服务端驱动：字符串表里找 `ad_slot_key`/`ad_show:`/banner 列表 API；**等长替换 JSON 键/插槽键**（保留 API 路径），否则启动 404 → jsonDecode 异常 → 卡 Logo。
- **RN**：`assets/index.android.bundle`（JS）；或 `index.android.bundle.hbc`（Hermes 字节码）→ hermes-dec。
- 混淆/加密的 Flutter 函数无法反编译时，字符串表等长替换是最稳的路径。

## 七、权益 / 付费逻辑分析（速查）

详细流程与可行性分级见 `entitlement-analysis.md`。要点：

| 目标 | 补丁 | 命令 |
|---|---|---|
| 判定方法恒真 | 方法开头 `const/4 v0, 0x1` + `return v0` | `patch_method.py ret ... --method isVip --return true` |
| 静态标志初值 | `<clinit>` 里 `sput-boolean` | `patch_method.py field ... --field 'Lx/Y;->isVip:Z' --value true` |
| 权益到期时间 | long 字段置大（2100 年） | `... --field 'Lx/Y;->vipEndTime:J' --value 4102444800000` |
| 剩余次数 | getter 返回大数 | `... --method getRemainTimes --return 999999` |
| 购买回调 | 成功分支判定改恒真 | 找 `onPurchasesUpdated`/`PayResult`/`onResp` 里的 `sput-boolean` |

改之前必须分清 **A 本地 / B 本地凭证+服务端校验 / C 服务端权威 / D 加固** 四级（`entitlement-analysis.md` §1）。
C 级改客户端只能骗 UI，功能接口仍会拒绝，要抓包/Hook 响应。

## 八、数值 / 数值 / 积分（速查）

详细见 `value-logic-analysis.md`。要点：

| 目标 | 补丁 |
|---|---|
| 数值 getter 返回大数 | `const v0, 0x5f5e0ff` + `return v0`（`patch_method.py ret --return 99999999`） |
| 消费后不减 | 扣减指令整行换 `nop`（`sub-int/2addr v0, v1` → `nop`），v0 保留旧值 |
| 收益/奖励翻倍 | 改 `const/4`→`const/16` 字面量，或改 `add-int/lit8` 的 lit8 |
| 价格归零 | `const/16 v0, 0x64` → `const/4 v0, 0x0` |
| 免费购买 | `canAfford()Z` 恒真 |
| 默认值 | `getInt(key, 0)` 的第二个寄存器改 `const/16 v1, 0x270f` |
| 上限夹紧 | 找 `Math.min`/`if-gt` 的常量改大，或改判定跳过 |

改名/改值前先确认是"显示 getter"还是"扣减字段"——只改 getter 常出现"显示 999 但花不出去"。

## 九、等长替换与直接改 dex / .so

- **走 apktool 重打包时不需要等长**：指令可以增删，只要寄存器语义正确；apktool 会重算 dex 头。
- **直接改 dex 二进制时**字符串/方法名必须等长（dex 有长度字段与偏移表），且要重算 header `checksum`
  与 `signature`（sha1）；长度变了只能重建 dex（baksmali→smali 或 apktool）。
- **直接改 .so** 也要求指令等长（一条指令 4 字节 aarch64），常用替换：
  ```text
  mov w0, #1 ; ret            = 20 00 80 52  C0 03 5F D6   （让函数恒返回 true）
  mov w0, #0 ; ret            = 00 00 80 52  C0 03 5F D6
  ```
  用 `r2 -w libx.so` → `s main` 找地址 → `wx 20008052c0035fd6` 覆盖 → `wq`。
- 服务端响应/JSON 的等长替换（补空格对齐）见 `entitlement-analysis.md` §4.2。

## 十、多补丁顺序

1. 先过保护层（pairip/签名校验/完整性）→ 能启动。
2. 再打功能补丁（权益判定、数值）。
3. 最后清广告/UI（广告组件清理流程）。
4. 每加一批补丁重新打包验证一次，出问题好回滚（`.bak` 或重解码）。
