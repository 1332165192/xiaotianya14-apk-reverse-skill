#!/usr/bin/env python3
"""原生 .so 定点补丁：NOP / 恒真 / 恒假 / 常数返回 / 自定义字节。

原生库（`lib/*.so`）里的逻辑改不了 smali，
要么运行时 hook（Frida / 原生菜单库），要么直接改机器码。本脚本负责「静态改机器码」
那一路：按导出符号 / 虚拟地址(VA) / 文件偏移定位，写 ARM64 / ARM32 常见补丁片段，
自动备份 `.bak`、可 dry-run、可回滚。改完把 .so 塞回 APK 重新打包签名即可。

补丁预设（按 ELF 架构自动选编码）:
  nop        空指令（多用于「跳过扣减/校验」）
  ret-true   arm64: mov w0,#1; ret     arm32: mov r0,#1; bx lr
  ret-false  arm64: mov w0,#0; ret     arm32: mov r0,#0; bx lr
  ret-int:N  arm64: movz/movk w0,#N; ret；arm32: movw/movt r0,#N; bx lr
  ret-void   直接 ret / bx lr（void 方法提前返回；入口补丁，注意栈/寄存器前提）
  hex:...    自定义字节，如 hex:1f2003d5 或 hex:"1f 20 03 d5"

定位:
  --symbol NAME   导出符号（动态符号表；il2cpp 方法通常没导出，用 --va/--offset）
  --va 0x123456   虚拟地址（dump.cs / IDA 里的地址；自动换算文件偏移）
  --offset 0xB8F0 文件偏移（直接落在文件里的位置）

用法示例:
  python3 so_patch.py info dec/lib/arm64-v8a/libil2cpp.so
  python3 so_patch.py find dec/lib/arm64-v8a/libil2cpp.so --string Ammo --limit 10
  python3 so_patch.py find lib.so --name '^getAmmo'
  python3 so_patch.py patch libil2cpp.so --va 0x123456 --preset ret-true --dry-run
  python3 so_patch.py patch libil2cpp.so --va 0x123456 --preset ret-true
  python3 so_patch.py restore libil2cpp.so

注意：
- 只能改**未加密/未加壳**的 .so；有完整性校验（lib hash、签名校验）要先过
  protection-map.md §五，否则重打包后要么闪退要么被回滚。
- ARM32 Thumb 代码（符号地址最低位=1）要用 Thumb 预设；脚本会检测并提示。
- 静态补丁是「常开」；要运行时开关，用原生菜单库（LGL/NepMods 模板）或 Frida，
  见 references/game-native-il2cpp.md。
"""
import argparse
import os
import re
import shutil
import sys

try:
    import lief
except ImportError:  # pragma: no cover
    sys.exit('缺 lief：pip install lief（本机已装）')


# ---------------------------------------------------------------- 编码表

def arm64_presets():
    return {
        'nop': bytes.fromhex('1f2003d5'),
        'ret-true': bytes.fromhex('20008052c0035fd6'),      # mov w0,#1; ret
        'ret-false': bytes.fromhex('00008052c0035fd6'),     # mov w0,#0; ret
        'ret-void': bytes.fromhex('c0035fd6'),              # ret
    }


def arm32_presets():
    return {
        'nop': bytes.fromhex('0000a0e1'),                   # mov r0,r0
        'ret-true': bytes.fromhex('0100a0e31eff2fe1'),      # mov r0,#1; bx lr
        'ret-false': bytes.fromhex('0000a0e31eff2fe1'),     # mov r0,#0; bx lr
        'ret-void': bytes.fromhex('1eff2fe1'),              # bx lr
    }


def thumb_presets():
    return {
        'nop': bytes.fromhex('00bf'),                       # nop
        'ret-true': bytes.fromhex('01207047'),              # movs r0,#1; bx lr
        'ret-false': bytes.fromhex('00207047'),             # movs r0,#0; bx lr
        'ret-void': bytes.fromhex('7047'),                  # bx lr
    }


def u32le(v):
    return int(v).to_bytes(4, 'little')


def arm64_ret_int(n):
    """movz w0,#lo16 (; movk w0,#hi16 lsl 16) ; ret"""
    lo, hi = n & 0xFFFF, (n >> 16) & 0xFFFF
    ins = [u32le(0x52800000 | (lo << 5))]               # movz w0,#lo
    if hi:
        ins.append(u32le(0x72A00000 | (hi << 5)))       # movk w0,#hi,lsl#16
    ins.append(u32le(0xD65F03C0))                       # ret
    return b''.join(ins)


def arm32_ret_int(n):
    """movw r0,#lo16 (; movt r0,#hi16) ; bx lr"""
    lo, hi = n & 0xFFFF, (n >> 16) & 0xFFFF
    ins = [u32le(0xE3000000 | (((lo >> 12) & 0xF) << 16) | (lo & 0xFFF))]      # movw r0,#lo
    if hi:
        ins.append(u32le(0xE3400000 | (((hi >> 12) & 0xF) << 16) | (hi & 0xFFF)))  # movt r0,#hi
    ins.append(u32le(0xE12FFF1E))                       # bx lr
    return b''.join(ins)


def make_patch(arch, preset, thumb=False):
    if preset.startswith('hex:'):
        raw = preset.split(':', 1)[1]
        h = re.sub(r'[^0-9a-fA-F]', '', raw)
        if len(h) % 2:
            raise SystemExit('hex 字节数必须是偶数')
        return bytes.fromhex(h)
    if preset.startswith('ret-int:'):
        try:
            n = int(preset.split(':', 1)[1], 0)
        except ValueError:
            raise SystemExit('ret-int 需要数字，如 ret-int:9999 或 ret-int:0x3ff')
        if n < 0:
            raise SystemExit('ret-int 只支持非负值')
        if arch == 'AARCH64':
            return arm64_ret_int(n)
        if thumb:
            raise SystemExit('Thumb 模式的 ret-int 需要手写 hex（movs/movw 编码不同）')
        return arm32_ret_int(n)
    table = {'AARCH64': arm64_presets, 'ARM': thumb_presets if thumb else arm32_presets}
    if arch not in table:
        raise SystemExit(f'不支持的架构 {arch}（只做 AARCH64 / ARM；x86 用 hex: 手写）')
    tab = table[arch]()
    if preset not in tab:
        raise SystemExit(f'未知预设 {preset}；可用: {", ".join(sorted(tab))}, ret-int:N, hex:...')
    return tab[preset]


# ---------------------------------------------------------------- 工具

def load(path):
    if not os.path.isfile(path):
        raise SystemExit(f'文件不存在: {path}')
    b = lief.parse(path)
    if b is None or not isinstance(b, lief.ELF.Binary):
        raise SystemExit(f'不是 ELF: {path}')
    return b


def va_of(args, binary):
    """返回 (VA, 说明)"""
    if args.symbol:
        cand = [s for s in binary.dynamic_symbols if s.name == args.symbol]
        if not cand:
            cand = [s for s in binary.symtab_symbols if s.name == args.symbol] if hasattr(binary, 'symtab_symbols') else []
        if not cand:
            raise SystemExit(f'导出符号表里没有 {args.symbol}（il2cpp 方法常不导出，用 --va/--offset）')
        return cand[0].value, f'symbol {args.symbol}'
    if args.va is not None:
        return args.va, f'VA {hex(args.va)}'
    if args.offset is not None:
        va = binary.offset_to_virtual_address(args.offset)
        if va is None:
            raise SystemExit(f'文件偏移 {hex(args.offset)} 换算不出 VA')
        return va, f'offset {hex(args.offset)} (VA {hex(va)})'
    raise SystemExit('需要 --symbol / --va / --offset 之一')


def backup(path):
    bak = path + '.bak'
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print(f'已备份: {os.path.relpath(bak)}')


# ---------------------------------------------------------------- 子命令

def cmd_info(args):
    b = load(args.so)
    print(f'文件: {args.so}')
    print(f'架构: {b.header.machine_type.name}  类型: {b.header.file_type.name}  '
          f'类: {b.header.identity_class.name}')
    try:
        print(f'入口: {hex(b.entrypoint)}')
    except Exception:
        pass
    syms = [s for s in b.dynamic_symbols if s.name]
    print(f'导出符号: {len(syms)} 个')
    text = b.get_section('.text')
    if text:
        print(f'.text: VA {hex(text.virtual_address)}  文件偏移 {hex(text.file_offset)}  '
              f'大小 {hex(text.size)}')
    base = os.path.basename(args.so)
    for want in ('libil2cpp.so', 'libunity.so', 'libUE4.so', 'libcocos2dcpp.so', 'libcocos2d.so'):
        if want in base:
            print(f'识别: {want}（native 库）')
            break


def cmd_find(args):
    b = load(args.so)
    if args.name:
        pat = re.compile(args.name)
        hits = 0
        for s in b.dynamic_symbols:
            if s.name and pat.search(s.name):
                print(f'{hex(s.value)}  {s.name}')
                hits += 1
                if hits >= args.limit:
                    break
        if not hits:
            print('导出符号没命中 —— il2cpp 方法名在 global-metadata.dat 里，不在符号表；'
                  '改用 --string 搜字符串，或 Frida/PC dump（game-native-il2cpp.md）')
        return
    if args.string:
        data = open(args.so, 'rb').read()
        needle = args.string.encode()
        hits = 0
        start = 0
        while hits < args.limit:
            idx = data.find(needle, start)
            if idx < 0:
                break
            try:
                va = b.offset_to_virtual_address(idx)
                va_s = hex(va) if va is not None else '?'
            except Exception:
                va_s = '?'
            ctx = data[max(0, idx - 24):idx + len(needle) + 24]
            ctx = ''.join(chr(c) if 32 <= c < 127 else '.' for c in ctx)
            print(f'offset {hex(idx)}  VA {va_s}  …{ctx}…')
            hits += 1
            start = idx + 1
        if not hits:
            print(f'没找到字符串 {args.string!r}（可能被加密/混淆，或改用 Frida 抓运行时字符串）')
        return
    raise SystemExit('find 需要 --name 正则 或 --string 文本')


def cmd_patch(args):
    b = load(args.so)
    va, desc = va_of(args, b)
    thumb = False
    if b.header.machine_type == lief.ELF.ARCH.ARM and (va & 1):
        thumb = True
        va &= ~1
        print('检测到 Thumb 函数（地址最低位=1），使用 Thumb 预设')
    patch = make_patch(b.header.machine_type.name, args.preset, thumb)
    off = b.virtual_address_to_offset(va)
    if off is None or off < 0:
        raise SystemExit(f'VA {hex(va)} 换算不出文件偏移（可能在 BSS/未映射段）')
    data = open(args.so, 'rb').read()
    if off + len(patch) > len(data):
        raise SystemExit('补丁超出文件范围')
    old = data[off:off + len(patch)]
    print(f'{desc} → 文件偏移 {hex(off)}  patch={args.preset} ({len(patch)} 字节)')
    print(f'  原字节: {old.hex()}')
    print(f'  新字节: {patch.hex()}')
    if old == patch:
        print('已经是这个补丁，跳过')
        return
    if args.dry_run:
        print('[dry-run] 未写入')
        return
    backup(args.so)
    with open(args.so, 'r+b') as f:
        f.seek(off)
        f.write(patch)
    # 回读校验
    with open(args.so, 'rb') as f:
        f.seek(off)
        now = f.read(len(patch))
    print('已写入并回读校验: ' + ('OK' if now == patch else '失败！用 restore 回滚'))
    print('下一步: 把 .so 放回 APK 的 lib/<abi>/ → 重新打包签名（build_sign.sh）→ 真机验证')


def cmd_restore(args):
    bak = args.so + '.bak'
    if not os.path.exists(bak):
        raise SystemExit('没有 .bak 备份，无法回滚')
    shutil.copy2(bak, args.so)
    print(f'已回滚: {args.so}')


def main():
    ap = argparse.ArgumentParser(description='原生 .so 定点补丁（NOP/恒真/常数返回）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    i = sub.add_parser('info', help='看架构/段/导出符号')
    i.add_argument('so')
    i.set_defaults(func=cmd_info)

    f = sub.add_parser('find', help='找符号或字符串（辅助定位）')
    f.add_argument('so')
    f.add_argument('--name', help='导出符号正则，如 ^getAmmo')
    f.add_argument('--string', help='文件内字符串，如 Ammo')
    f.add_argument('--limit', type=int, default=20)
    f.set_defaults(func=cmd_find)

    p = sub.add_parser('patch', help='按 VA/符号/偏移写补丁')
    p.add_argument('so')
    p.add_argument('--symbol')
    p.add_argument('--va', type=lambda x: int(x, 0))
    p.add_argument('--offset', type=lambda x: int(x, 0))
    p.add_argument('--preset', required=True,
                   help='nop/ret-true/ret-false/ret-void/ret-int:N/hex:...')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_patch)

    r = sub.add_parser('restore', help='从 .bak 回滚')
    r.add_argument('so')
    r.set_defaults(func=cmd_restore)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
