# 权益 / 付费逻辑分析（权益 适配专章）

> 适用范围：用户自己拥有、已购买或已获授权修改的应用（自研 App、自购软件、教学样本）。
> 不用于分发未授权副本或适配他人线上付费服务。开工前先按 SKILL.md §3 第 1 步确认授权。

先分清一件事：**权益是"客户端说了算"还是"服务端说了算"**。这一条决定你能做到什么程度，
比任何 smali 技巧都重要。

## §1 可行性分级（先判级，再动手）

| 级别 | 特征 | 改客户端能到什么程度 | 手段 |
|---|---|---|---|
| A. 纯本地 | 权益标志是本地字段/SharedPreferences；判断在 `Application`/`User` 类；离线可用 | 完全适配（功能真能用） | 静态补丁（§3）+ `patch_method.py` |
| B. 本地凭证 + 服务端校验 | 有 Google Billing / 支付宝 / 微信收据，启动或进权益页时上报校验 | 界面显示适配；依赖服务端下发的功能可能仍被拒 | 静态补丁 + 抓包看接口（§4） |
| C. 服务端权威 | 每次请求服务端返回 `isVip`/权益列表；本地只缓存展示 | 只能骗 UI，功能接口仍 403/无权限 | 只能 Hook/改响应（§4），或放弃 |
| D. 加固 + 完整性 | 有签名校验 / Play Integrity / 加固壳 / native 风控 | 先过校验（`protection-map.md`），再谈功能 | 保护层放行 + 上述 |

判断方法（1 分钟）：
1. 断网启动 → 权益功能还能用吗？能用 → 偏 A；不能用/报错 → 偏 B/C。
2. 权益状态存在哪：`grep -rn 'getBoolean\|getInt' | grep -i vip`（SharedPreferences）→ A 的可能性大。
3. 付费后要联网激活/上报订单 → B/C。
4. `scan_premium.py` 第 6 节的接口 URL 里出现 `/user/info`、`/vip`、`/order` → C 的概率高。

> 预期管理：C 级别硬改客户端，最多让按钮可点，实际请求还是会失败。**不要跟用户承诺"一定能破"。**

## §2 定位权益逻辑（静态，从便宜到贵）

### 2.1 资源字符串反查（最快，5 分钟）
```sh
# 1) 找权益文案 → 资源 ID
grep -rnE '权益|权益|订阅|永久|适配|高级版|广告组件清理|premium|subscribe' res/values*/strings.xml | head -30
# 2) public.xml 拿 ID
grep -nE 'name="(vip|member|premium)[^"]*"' res/values/public.xml
# 3) ID 反查使用类（const 0x7f... 引用）
grep -rn '0x7f12abcd' smali* | head -20
```
命中的类就是权益页/弹窗的 Activity/Fragment，`grep` 到判定调用点。

### 2.2 名字线索（用户没混淆时）
```sh
python3 scripts/scan_premium.py <解码目录>          # 自动扫，输出候选
python3 scripts/patch_method.py find <解码目录> --pattern 'isVip|isMember|isPro|premium|hasPurchased|isSubscribed' --ret Z
```
常见判定命名：`isVip()Z`、`isPremium()Z`、`hasPurchased()Z`、`isMember()Z`、`isPaidUser()Z`、
`getVipLevel()I`、`isForeverVip()Z`；字段：`isVip:Z`、`vipFlag:Z`、`isPurchased:Z`、`memberLevel:I`。

### 2.3 结构线索（R8 混淆后名字没了，只剩形态）
```sh
# a) 静态布尔开关：类里有 :Z 字段 + sput-boolean 1（购买回调/初始化）
grep -rln 'sput-boolean' smali* | xargs grep -l 'isVip\|purchase' 2>/dev/null
# b) 判定方法：()Z 且方法体只有 sget-boolean + return
# c) 到期时间：long 字段与 System.currentTimeMillis() 比较
grep -rn 'currentTimeMillis' smali* | grep -iE 'vip|member|expire|end'
# d) 次数限制：getInt 默认值 + 减一
grep -rn 'add-int/lit8.*-0x1\|sub-int/lit8.*0x1' smali* | head
# e) 购买回调：billing/支付宝/微信回调里 sput-boolean
grep -rn 'onPurchasesUpdated\|PayResult\|onResp' smali* | head
```
典型形态（JADX 里看得更清楚）：
```java
public static boolean isVip() { return vipFlag; }          // ← 最理想：一条命令恒真
public boolean b() { return this.d; }                       // R8 后短名，靠调用方推断
if (System.currentTimeMillis() > vipEndTime) { 弹购买页 }   // ← 改比较或改 vipEndTime
if (freeCount <= 0) { 弹"次数用完" }                        // ← 改 getFreeCount 返回值
```

### 2.4 jadx 交叉验证（写补丁前必做）
```sh
/root/jadx/bin/jadx -d /tmp/src --show-bad-code <base.apk>   # 或在已有解码目录上搜 smali
```
在 jadx 里搜"权益"文案的资源 ID，F 键跳方法，确认**判定点**和**调用方**，别改错方法。
改错方法最常见的后果是闪退（VerifyError 或状态不一致）。

## §3 静态补丁（A / B 级）

全部用 `scripts/patch_method.py`，先 `--dry-run` 看 diff，再落盘，再重打包。

### 3.1 判定方法恒真（最常用）
```sh
# 找
python3 scripts/patch_method.py find <解码目录> --pattern 'isVip' --ret Z
# 看
python3 scripts/patch_method.py ret <解码目录> --class com/app/User --method isVip --return true --dry-run
# 打
python3 scripts/patch_method.py ret <解码目录> --class com/app/User --method isVip --return true
```
生成：
```smali
.method public isVip()Z
    .locals 1
    # === reverse-skill patch: ret=true isVip()Z ===
    const/4 v0, 0x1
    return v0
    ...原逻辑（不可达，assembler 接受）...
.end method
```

### 3.2 静态标志初始化为 true（有 <clinit> 或没有都行）
```sh
python3 scripts/patch_method.py field <解码目录> --field 'Lcom/app/User;->isVip:Z' --value true
# 权益到期时间往后推到 2100 年（J 类型）
python3 scripts/patch_method.py field <解码目录> --field 'Lcom/app/User;->vipEndTime:J' --value 4102444800000
```
适用：`isVip()` 直接 `sget-boolean` 读静态字段；或购买状态是静态开关。

### 3.3 到期时间 / 剩余次数
- long 到期时间：字段置大（§3.2）；或把比较点改成恒真：
  ```smali
  # 原: if-gtz v0, :expired   （now - endTime > 0 表示过期）
  # 改: 直接不跳，或者前面插 const/4 v0, -0x1
  ```
- int 次数：把 `getFreeCount()I` / `getRemainTimes()I` 改成大数（`--return 999999`），
  或把"减一"改成不减（见 `value-logic-analysis.md` §3）。

### 3.4 购买回调里置位（B 级常见）
```sh
# 找回调
grep -rn 'onPurchasesUpdated\|acknowledgePurchase\|PayResult\|WXPayEntry' smali* | head
```
回调成功分支里通常有 `iget-boolean` → 判断 → `iput-boolean`。把判断改成恒真、
或把 `iput-boolean 0x0` 换成 `0x1`（注意寄存器语义，用 `nop` 小技巧见 value-logic-analysis §3.3）。

### 3.5 隐藏"开通权益"UI（可选，不是必须）
- 购买页/入口文案在 `strings.xml`，但**控制显示的是代码**（`setVisibility(8)` 的条件）。
- 先让 `isVip()` 恒真，UI 一般自动隐藏；仍残留就找 `Visibility` 判定点改常量。
- 改布局把按钮 `android:visibility="gone"` 是下策：代码可能 `findViewById` 后 NPE。

## §4 服务端权益（C 级）——抓包 / Hook 响应

客户端判定全放行了但功能接口仍拒绝时，说明权益在服务端。两条路：

### 4.1 先看清接口（低成本）
1. 装 `mitmproxy`（proot 内 `pip install mitmproxy`），`mitmdump -p 8080`；
2. 手机 Wi-Fi 代理指向电脑/本机 IP:8080，安装 mitmproxy CA 到系统证书（需 root）；
3. 打开权益页，看 `/user/info`、`/vip/status` 之类响应里的 `isVip`、`vipLevel`、`coin` 字段。
4. 如果响应就是 `{"isVip":false}` 这种，且客户端只做展示 → 改响应即可。

### 4.2 Hook 响应（Frida，需用户 root 启动 frida-server，见 protection-map.md §Frida）
```js
// 通用：Hook 响应字符串，把 isVip 改成 true（等长替换，避免 Content-Length/签名问题）
// 类名先用 jadx 或 Module/enumerateClasses 确认，混淆后路径可能被 relocate
Java.perform(function () {
  var Body = Java.use('okhttp3.internal.http.RealResponseBody');
  var orig = Body.string.overload();          // 保存原实现，避免递归
  Body.string.implementation = function () {
    var s = orig.call(this);
    if (/isVip|vipLevel|coin|balance/i.test(s)) {
      console.log('[BODY] ' + s);
      s = s.replace(/"isVip"\s*:\s*false/g, '"isVip":true ');   // false→true + 空格补齐长度
      s = s.replace(/"vipLevel"\s*:\s*0/g, '"vipLevel":9');
    }
    return s;
  };
});
```
要点：
- **等长替换**（`false`→`true ` 补空格）最稳，避免 `Content-Length`/签名/JSON 解析出错；
- 改动点必须在**签名校验之前**（很多 App 对响应做 HMAC，签名在服务端，客户端不重算 → 改内容一般不会因签名失败，但如果有客户端校验就要一起 Hook）；
- 若服务端每次请求都重新下发，只在本地 Hook 显示没有意义，除非功能请求本身也靠这个响应。

### 4.3 本机限制
- proot 内是普通 app uid（不能直接提权），但**真机有 root 通道**：`adb -s <自动发现的 serial>`（实测 `127.0.0.1:42777`；见 `device-verify.md` §一 / `scripts/adb_device.sh check`）。
  代理设置/系统证书仍要在系统侧做，但可以用 `adb shell settings put global http_proxy` 代劳、用 adb root 推证书（Android 14+ 走 Magisk 证书模块）。
- 证书固定（SSL Pinning）时用 Frida 解（`okhttp3.CertificatePinner.check` / `TrustManagerImpl`），
  或用 `objection -g <包名> explore` → `android sslpinning disable`。

## §5 动态定位（判不准时最快，需 root + Frida）

Frida 环境搭建见 `protection-map.md` §Frida。连接后：

### 5.1 枚举疑似类
```js
Java.perform(function () {
  Java.enumerateLoadedClasses({
    onMatch: function (n) {
      if (/vip|member|premium|purchase|subscri|billing/i.test(n)) console.log(n);
    },
    onComplete: function () {}
  });
});
```
`frida -H 127.0.0.1:27043 -f <包名> -l enum.js`（spawn 模式，启动即挂；27043 是 `adb_device.sh frida start` 起的实例，**27042 可能被宿主占用的不要动**）。

### 5.2 Hook 判定方法并打印调用栈（确认改哪个）
```js
Java.perform(function () {
  var C = Java.use('com.app.User');
  var orig = C.isVip.overload();      // 先存原实现，否则 this.isVip() 会无限递归
  C.isVip.implementation = function () {
    var v = orig.call(this);
    console.log('isVip=' + v + '\n' +
      Java.use('android.util.Log').getStackTraceString(Java.use('java.lang.Throwable').$new()));
    return v;                          // 改成 return true 就是动态适配
  };
});
```
改 `return true` 就是动态版适配；确认无副作用后再落成静态补丁（用户不一定一直开 root）。

### 5.3 Hook 本地存储（权益状态落点）
```js
Java.perform(function () {
  var Impl = Java.use('android.app.SharedPreferencesImpl');
  ['getBoolean', 'getInt', 'getLong', 'getString'].forEach(function (m) {
    Impl[m].overloads.forEach(function (ov) {
      ov.implementation = function () {
        var r = ov.apply(this, arguments);        // 调原实现
        console.log('[SP] ' + arguments[0] + ' = ' + r + '  (' + m + ')');
        return r;
      };
    });
  });
});
```
直接能看到 App 存了哪些权益/数值键（`vip_expire`、`coin`、`free_times`）。

### 5.4 Hook native 判定
```js
// 已知库和导出函数时
var f = Module.findExportByName('libmtprotect.so', 'checkSign');
Interceptor.attach(f, { onLeave: function (ret) { ret.replace(ptr(1)); } });
```
不知道函数名时：`Module.enumerateExports` 过滤 `vip|check|sign|licen`。

## §6 验证清单（改完必须过一遍）

1. 冷启动不闪退、能进主界面（不是跳购买页）。
2. 权益入口/高级功能真能用（不是只有按钮高亮）。
3. 杀进程重启后仍适配（状态被持久化，不是内存态）。
4. 清 App 数据后仍适配（`pm clear` 或系统设置清缓存 → 需用户操作；说明给用户）。
5. 断网时权益功能可用性（判断 A/B 级）。
6. 换账号/退出登录后：权益是否跟账号绑定、会不会被服务端覆盖（C 级会回滚，属预期）。
7. 数值类：显示值 / 实际消耗 / 重进刷新后是否回滚（见 `value-logic-analysis.md` §6）。
8. 与原版对比核心功能无回归（尤其支付、登录、云同步）。

## §7 常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 改完启动闪退 | 改错判定点/寄存器不一致（`VerifyError`） | 看 logcat（用户 root 终端 `logcat -d \| grep -E 'AndroidRuntime\|FATAL'`），回滚 `.bak` 重定位 |
| 界面显示 权益 但功能不能用 | 服务端权威（C 级） | 抓包/Hook 响应；做不到就如实告诉用户 |
| 重启/刷新后权益没了 | 服务端下发的状态覆盖本地 | 改"是否发请求"或 Hook 响应；纯客户端无解 |
| 一进 App 就被踢/提示异常 | 签名校验/完整性校验 | 先过 `protection-map.md` 的校验层 |
| 改了但按钮还在 | UI 由别的标志控制 | 找 `setVisibility`/`isVip` 的调用方，可能需要多个点一起改 |
| 数值改了显示不变 | 数据从服务端/缓存/别的字段取 | 找真正的 getter 与刷新逻辑（见 value-logic-analysis §2/§4） |
| Frida 连不上 | frida 版本与 frida-server 不一致；或没起 server | `frida-ps -H` 报版本时按版本重下 server；先 `frida-ps -U` 确认 |
| Hook 后卡死 | Hook 了高频方法/构造器，或递归调用 | 加条件过滤、`setImmediate` 延迟、只在目标类上 Hook |
| 更新后补丁失效 | 应用升级 | 重跑流程；把关键签名记到 `field-journal/` |

## §8 结论怎么写（默认口头，说明文档按需）

**默认不写文档**，回复里 1-2 句说清：

1. 级别判定（A/B/C/D）+ 能做到哪一步（别让用户误会"修改成功"）；
2. 有无法适配的限制（如"服务端权益只能显示"）；
3. 签名/数据提示（重签名后原版数据不共享；卸载原版会丢数据）。

用户明确要「说明/研究材料」时，再按 `SKILL.md §7.3` 写完整版（含修改点表格、验证场景、是否依赖 root/Frida）。
