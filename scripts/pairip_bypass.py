#!/usr/bin/env python3
"""放行 Google pairip 授权壳（com.pairip.licensecheck.*）。

特征: 重新签名后启动跳 Play 商店 / 闪退 / 弹"未授权" / 约 30 秒后杀进程。

用法:
    python3 pairip_bypass.py <apktool解码目录>

补丁（全部是方法开头提前 return/返回 true，幂等可重复执行）:
1. LicenseContentProvider.onCreate()Z            -> const/4 v0, 0x1; return v0
2. LicenseClient.checkLicense(Context)           -> return-void
3. LicenseClient.startErrorDialogActivity()      -> return-void
4. LicenseClient.startPaywallActivity(PendingIntent) -> return-void
5. LicenseClient.scheduleAppShutdown()           -> return-void
"""
import os
import re
import sys

LCM = 'smali/com/pairip/licensecheck/LicenseClient.smali'
LCP = 'smali/com/pairip/licensecheck/LicenseContentProvider.smali'


def patch_methods(path, specs):
    """specs: [(方法头正则, 插入行列表)]；返回 (修改数, 命中方法数)"""
    if not os.path.isfile(path):
        return 0, 0
    with open(path, encoding='utf-8') as f:
        lines = f.readlines()
    out = []
    i = 0
    changed = found = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        out.append(ln)
        if ln.lstrip().startswith('.method'):
            # 复制到 .locals 行（smali 一般在方法头后立刻是 .locals）
            j = i + 1
            while j < n and '.locals' not in lines[j] and not lines[j].lstrip().startswith('.method'):
                out.append(lines[j])
                j += 1
            if j < n and '.locals' in lines[j]:
                out.append(lines[j])
                j += 1
                spec = next((ins for pat, ins in specs if re.search(pat, ln)), None)
                if spec is not None:
                    found += 1
                    head = lines[j:j + len(spec) + 2]
                    already = any(x.strip() == spec[0].strip() for x in head if x.strip())
                    if not already:
                        out.extend(spec)
                        changed += 1
                i = j
                continue
        i += 1
    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(''.join(out))
    return changed, found


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    dec = sys.argv[1]
    total = 0
    skip = 0

    n, found = patch_methods(
        os.path.join(dec, LCP),
        [(r'\.method public onCreate\(\)Z',
          ['    const/4 v0, 0x1\n', '\n', '    return v0\n'])],
    )
    total += n
    skip += max(0, found - n)
    print(f'LicenseContentProvider.onCreate(): {"patched" if n else ("already" if found else "absent")}')

    specs = [
        (r'\.method public static checkLicense\(Landroid/content/Context;\)V', ['    return-void\n']),
        (r'\.method private startErrorDialogActivity\(\)V', ['    return-void\n']),
        (r'\.method private startPaywallActivity\(Landroid/app/PendingIntent;\)V', ['    return-void\n']),
        (r'\.method private scheduleAppShutdown\(\)V', ['    return-void\n']),
    ]
    n, found = patch_methods(os.path.join(dec, LCM), specs)
    total += n
    print(f'LicenseClient 4 个拦截方法: patched={n} found={found}')

    if found == 0:
        print('未找到 pairip 授权类（可能未加壳，或类路径不同）；确认 smali/com/pairip/ 是否存在')
        return 0
    print(f'完成: {total} 处补丁（已打过的会跳过）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
