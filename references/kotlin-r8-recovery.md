# R8 / ProGuard 混淆与 Kotlin 名称恢复

> 适用：jadx/apktool 反编译后看到 `a/b/c`、`a()` 这类短名，需要恢复“这是什么类/方法”。
> 先判断是不是 R8 混淆，再选恢复路径；不要盲目全量反混淆。

## 1. 先确认混淆形态

| 现象 | 判断 |
|---|---|
| 类名 `a/b/c`、方法 `a()`、字段 `a` | R8/ProGuard 全量混淆 |
| 只有部分短名，字符串保留 | 混淆强度中等（可能保留 mapping 给崩溃上报） |
| 包里有 `mapping.txt` / `.mapping` | 有官方映射，直接 retrace，优先 |
| Kotlin metadata 还在（`@Metadata` 注解） | 可用 metadata 反推类名/参数名 |

## 2. 恢复路径（按成本从低到高）

1. **找 mapping.txt**：APK 里很少有；但在 `assets/`、崩溃上报配置、CI 产物里可能残留。
   有的话用 `retrace`（R8 自带）还原堆栈与类名。
2. **Kotlin @Metadata**：`kotlin.Metadata` 注解的 `k=1` 是类元数据，`d1/d2` 是编码后的字符串。
   用 `kotlinx-metadata` 类库可解析出原始类名/属性名（Kotlin 2.x 用新版 API）。
3. **字符串 / 资源 ID 反查**：`find_api_calls.py` + `grep -rn '<string id>' smali*`，
   从用户可见文案、接口 URL、日志 tag 反推类职责。
4. **调用链**：从入口 Activity/Fragment 往下跟（`UI → ViewModel → Repository → OkHttp/Retrofit`），
   混淆后仍保留调用关系；Retrofit 的注解（`@GET`、`@POST`）通常也在。
5. **反编译工具对比**：
   - jadx：可读性好，支持 `--deobf`（用内置字典尝试恢复常见名）；
   - Fernflower / Vineflower：恢复 lambda/泛型更完整，可与 jadx 交叉看；
   - smali：最接近字节码，补丁时以它为准。

## 3. Kotlin 特有注意点

- `@Metadata` 是判断“这是 Kotlin 写的”的最快依据；`k=1` 类、`k=2` 文件级。
- 协程：`suspend` 方法编译后多一个 `Continuation` 参数，看 `invokeSuspend` 更容易定位业务。
- 内联类（value class）：运行期被拆成底层类型，反编译看到 `long/int` 参数不一定是原类型。
- 扩展函数：编译成静态方法，第一个参数是接收者，容易被误认成普通工具方法。
- 属性：Kotlin `var` 一般有 `getX/setX` 或 `getX$app` 形式，定位字段时按 getter 找更稳。

## 4. 命令速查

```sh
# jadx 开反混淆字典（能恢复部分标准名）
jadx --deobf -d out app.apk

# retrace（如果有 mapping）
retrace mapping.txt crash.txt

# 找 Kotlin metadata 注解
grep -rl "Lkotlin/Metadata;" out/sources | head

# 按字符串反查类
grep -rn "目标文案" out/sources | head
```
