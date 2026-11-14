# 数值 / 数值 / 积分修改（value hacking 专章）

> 适用范围同上：自有/已授权应用。改数值前先想清楚——**数值存在哪，谁说了算**。

## §1 数值存哪里（决定手段和成功率）

| 存放位置 | 特征 | 改法 | 成功率 |
|---|---|---|---|
| 服务端数据库 | 每次进应用/刷新从接口拉；本地值只是缓存 | 只能 Hook 响应或改判定（§5.3），本地改显示 | 显示 100%，实际结算看服务端 |
| SharedPreferences | `/data/data/<pkg>/shared_prefs/*.xml`，key 形如 `coin`/`gold` | 直接改 XML（需 root）或改读写代码 | 高（离线） |
| SQLite | `databases/*.db`，表里一列 | `sqlite3` 直接 update（需 root） | 高（离线） |
| 自定义文件 | assets/ 外的 json、二进制、加密存档 | 解密后改，或改序列化代码 | 中（看加密强度） |
| 内存（进程内字段） | 无持久化，重启归零 | Frida Hook / 内存扫描 | 中（仅当次运行） |
| native 层（.so） | 数值在 C++ 对象里 | 改 .so 常量/函数，或 Frida native hook | 中高 |

判断优先级：**先看 App 有没有联网接口下发数值**（`scan_premium.py` 第 6 节），
没有就是本地存档，最容易；有的话先看回包（`entitlement-analysis.md` §4.1）再决定。

## §2 静态定位数值逻辑

```sh
# 1) 字段名（未混淆）
python3 scripts/scan_premium.py <解码目录>          # 第 4 节直接给候选
# 2) 手动：数值/积分类字段
grep -rlnE ':(I|J)' smali* | xargs grep -lE 'coin|gold|diamond|gem|credit|balance|score|point|money|wallet'
# 3) getter / 加法点
grep -rn 'add-int/lit8\|add-int/2addr\|sub-int' smali* | grep -iE 'coin|gold|score|balance'
# 4) 持久化 API
grep -rn 'getInt\|putInt\|getLong\|putLong' smali* | grep -iE 'coin|gold|score|diamond'
# 5) SharedPreferences 键名（字符串常量）
grep -rn 'const-string.*"\(coin\|gold\|diamond\|score\|balance\)"' smali*
```
JADX 里对照着看更快：
```java
int getCoins() { return this.coins; }                  // ← getter，改成常量最省事
void addCoins(int n) { this.coins += n; save(); }
boolean canAfford(int price) { return this.coins >= price; }
```

**先分清三个数**：
- 显示用的 getter（改它 → 只看得到，花不出去）
- 实际扣减/校验用的字段（改它 → 真能用，但可能被存档/服务端覆盖）
- 上限校验（`if (coins > 999999) coins = 999999;`）→ 一起改，否则改了立刻被夹回

## §3 静态补丁手法（smali 层重打包，指令长度不受限）

> 注意：只有**直接改 dex/so 二进制**才需要"等长替换"；走 apktool 重打包时指令可以随意增删，
> 只要寄存器语义正确。

### 3.1 getter 返回固定大数（最常用）
```sh
python3 scripts/patch_method.py ret <解码目录> --class com/app/User --method getCoins --return 99999999
```
```smali
.method public getCoins()I
    .locals 1
    # === reverse-skill patch: ret=99999999 getCoins()I ===
    const v0, 0x5f5e0ff
    return v0
    iget v0, p0, Lcom/app/User;->coins:I
    return v0
.end method
```
适合"只读显示 + 读取时校验"的离线 App。若 App 用**字段直读**（`iget v0, p0, User;->coins:I`），
getter 改了也白改 → 改字段初值或用 §3.4 的等长替换。

### 3.2 消费后不减（"数值不扣减"本质）
找扣减指令，直接换成 `nop`，寄存器保留原值：
```smali
# 原：coins -= cost
sub-int/2addr v0, v1       # v0=余额, v1=价格
iput v0, p0, Lcom/app/User;->coins:I

# 改：删掉减法（v0 仍是原余额）
nop
iput v0, p0, Lcom/app/User;->coins:I
```
同理 `sub-int v0, v0, v1`、`sub-int/lit8 v0, v0, 0x1` 都可以整行换 `nop`。
**注意**：如果后面还要用 v0 做别的比较/日志，`nop` 后 v0 是旧值——通常正是想要的效果；
但若扣的是"次数"且后面用它写 UI，要一起确认。

### 3.3 收益翻倍 / 签到奖励
```smali
# 原：reward = 1
const/4 v0, 0x1
# 改：reward = 100（const/4 只能 -8..7，用 const/16）
const/16 v0, 0x64
```
或者改 `add-int/lit8 v0, v0, 0x1` 的字面量为 `0x64`（lit8 范围 -128..127）。

### 3.4 价格归零 / 免费购买
```smali
# 原：price = 100（常出现在 getPrice() 或 const 赋值处）
const/16 v0, 0x64
# 改：
const/4 v0, 0x0
```
配合 `canAfford()` 恒真：
```sh
python3 scripts/patch_method.py ret <解码目录> --class com/app/Shop --method canAfford --return true
```
> 服务端下单的 App：本地价格改成 0 只是 UI，服务端按订单金额扣款/校验收据 → 属于 C 级，无解，
> 见 `entitlement-analysis.md` §4。

### 3.5 默认值（getInt 的第二个参数）
```smali
# 原：prefs.getInt("coin", 0)
const/4 v1, 0x0
invoke-interface {v0, v2, v1}, Landroid/content/SharedPreferences;->getInt(Ljava/lang/String;I)I
# 改默认值（寄存器够大用 const/16，最多 32767；再大用 const）
const/16 v1, 0x270f        # 9999
```

### 3.6 上限/夹紧逻辑
```smali
# 原：if-gt v0, v1, :skip ; const/16 v0, 0x7fffffff
# 常见：Math.min(coins, 999999) → 改成直接返回 coins，或把常量改大
```

### 3.7 存档写入点（让修改持久化）
```smali
# 消费/增加后都会写存档，找到 putInt/putLong 的键名，确认改的是同一个值
iget v0, p0, Lcom/app/User;->coins:I
invoke-interface {v2, v3, v0}, Landroid/content/SharedPreferences$Editor;->putInt(Ljava/lang/String;I)Landroid/content/SharedPreferences$Editor;
```
改了内存字段但没改写入点 → 重启回滚。要么在 getter 里返回常量（不需要存档），
要么把写入值也改掉。

## §4 直接改存档（需要 root，最快）

```sh
# 手机 root 终端或 adb root 环境
su
cd /data/data/<包名>
ls shared_prefs databases files
# SharedPreferences（明文 XML）
cat shared_prefs/*.xml | grep -iE 'coin|gold|diamond|score|balance'
# SQLite
sqlite3 databases/<名字>.db '.tables'
sqlite3 databases/<名字>.db 'update user set coin=999999 where id=1;'
sqlite3 databases/<名字>.db 'select * from user;'
```
注意：
- 改前 `cp` 备份；改完 `chown`/权限保持原样，否则 App 读不到会重置。
- App 运行中改会被内存值覆盖 → 先 `am force-stop <包名>`。
- 加密存档（看到 base64/乱码/`.dat`）：用 Frida Hook `Cipher.doFinal` 看明文，
  或 Hook `SharedPreferencesImpl.getString` 看解密后的值，再决定改哪层。
- 有的 App 存 byte[]/protobuf：用已预装的 `blackboxprotobuf` 先看结构（不需要 .proto），再按字段号改：
  ```python
  import blackboxprotobuf, pprint
  data = open('存档文件', 'rb').read()
  msg, types = blackboxprotobuf.decode_message(data)
  pprint.pp(msg)          # 改完再 encode_message 回写
  ```

## §5 动态改（Frida，需用户 root 启动 frida-server）

### 5.1 改 Java 字段（最直接）
```js
Java.perform(function () {
  var U = Java.use('com.app.User');
  var u = U.$new();
  console.log('before coin=' + u.coins.value);
  u.coins.value = 99999999;                     // 改实例字段
  // 静态字段：U.coins.value = 99999999;
});
```
配合 `Java.choose('com.app.User', {onMatch: function (inst) { inst.coins.value = 99999999; }})`
把堆里所有实例都改一遍。

### 5.2 Hook getter（实时生效）
```js
Java.perform(function () {
  var U = Java.use('com.app.User');
  U.getCoins.implementation = function () { return 99999999; };
});
```

### 5.3 Hook 接口响应（服务端权威数值）
```js
Java.perform(function () {
  var B = Java.use('okhttp3.internal.http.RealResponseBody');
  B.string.implementation = function () {
    var s = this.string();
    if (/"coin"\s*:/.test(s)) {
      console.log('[BODY] ' + s);
      s = s.replace(/"coin"\s*:\s*\d+/g, '"coin":99999999');   // 长度变了就补空格对齐
    }
    return s;
  };
});
```

### 5.4 native 内存扫描（数值在 .so 里）
```js
// 已知初始值（如 100）时，扫内存里的 int 100，再改成大数
var m = Process.getModuleByName('libgame.so');
m.enumerateRanges('rw-').forEach(function (r) {
  Memory.scan(r.base, r.size, '64 00 00 00', {
    onMatch: function (addr) { /* 人工确认后：addr.writeInt(99999999); */ },
    onComplete: function () {}
  });
});
```
> 大规模扫描会很慢/误伤；优先用 `Module.enumerateExports` + `Interceptor.attach` 改函数返回值。

## §6 验证清单

1. 数值显示正确且**能用**（买入/消费一次，看是否真生效）。
2. 消耗后数值是否按预期（数值不扣减的判定标准：花完不掉）。
3. 杀进程重启 / 重新进界面后是否回滚（回滚 → 改的是内存不是存档，回到 §3.7/§4）。
4. 清数据后是否回滚（回滚说明靠服务端，属预期）。
5. 数值溢出检查：`I` 超 2147483647 变负数 → 改用 `J`（`const-wide`）或换小一点的数。
6. 会不会触发风控/封号：服务端有校验的 App 改客户端值属于高危，提前跟用户讲清楚。
7. 与原版功能对比（购买、兑换、签到等写操作不能坏）。

## §7 常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 改了 getter 显示变了但花不出去 | 校验/扣减读的是字段不是 getter | 改字段初值（§3.2/§3.4）或改扣减指令 |
| 数值变大后变负数 | I 溢出 | 用 J（`const-wide`）或控制在 2^31-1 内 |
| 改了重启就回滚 | 只改内存，存档没改 | §3.7 写入点 / §4 直接改存档 |
| 改存档无效 | App 运行中内存值覆盖、或存档加密/校验 | force-stop 后改；加密走 §4 说明 |
| 修改后 App 重置数据 | 完整性校验发现存档被改 | 过校验（protection-map.md），或改代码写入 |
| 只有 UI 变，服务端不认 | 服务端权威 | 见 entitlement-analysis.md §4 |
| 改了数值价格变 0 但支付仍扣钱 | 价格由服务端订单决定 | 无解（合法途径是正常购买） |
| 存档是 protobuf/自定义二进制 | 需要按字段号解析 | `blackboxprotobuf.decode_message` 看结构后再改，别猜 |
| 越改越乱 | 一次改多个点 | 一次只改一处，重新打包验证，逐步加 |
