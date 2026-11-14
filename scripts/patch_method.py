#!/usr/bin/env python3
"""smali 定点补丁器：改方法返回值 / 置静态字段初始值 / 查方法签名。

专治「分析权益逻辑」「数值改大」「判定恒真」这类需求：定位到方法后一条命令打补丁，
不用手改 smali。支持 dry-run 预览、自动备份、幂等（重复跑不会叠加）。

三个子命令:
  find   按正则搜方法签名（先找补丁点）
  ret    方法开头插入「返回固定值」（权益 判定 / 数值 getter / 解密返回）
  field  在 <clinit> 里置静态字段初值（已购标志 / 权益开关 / 计数器）

用法示例:
  # 1. 找权益判定方法
  python3 patch_method.py find dec --pattern 'isVip|isPro|hasPurchased|isMember' --ret Z
  # 2. 恒真（dry-run 先看）
  python3 patch_method.py ret dec --class com/app/User --method isVip --return true --dry-run
  python3 patch_method.py ret dec --class com/app/User --method isVip --return true
  # 3. 数值 getter 返回 999999
  python3 patch_method.py ret dec --class com/app/User --method getCoins --return 999999
  # 4. 已购静态标志初始化为 true
  python3 patch_method.py field dec --field 'Lz2/k;->d:Z' --value true
  # 5. 改错了回滚
  python3 patch_method.py ret dec --class com/app/User --method isVip --restore

补丁形态（插入在 .locals 之后、原指令之前；原逻辑成为不可达死代码，assembler 合法）:
    .method public isVip()Z
        .locals 1
        # === reverse-skill patch: ret=true ===
        const/4 v0, 0x1
        return v0
        ...原代码...

注意：改完必须重新打包签名（scripts/build_sign.sh），并在真机验证；
服务端权威的数值（余额、订单权益）改客户端返回值只影响显示，见
references/entitlement-analysis.md / references/value-logic-analysis.md 的可行性分级。
"""
import argparse
import difflib
import os
import re
import shutil
import sys

MARK = '# === reverse-skill patch:'
LEGACY_MARK = '# === apk-deadvertise patch:'   # 旧名标记，仍识别（避免重复打补丁）

METHOD_RE = re.compile(r'^\s*\.method\s+(.*)$')


def smali_roots(dec):
    roots = []
    for entry in sorted(os.listdir(dec)):
        if entry == 'smali' or entry.startswith('smali_'):
            p = os.path.join(dec, entry)
            if os.path.isdir(p):
                roots.append(p)
    return roots


def class_file(dec, cls):
    """com/app/User 或 Lcom/app/User; → 实际 smali 路径（找不到返回 None）"""
    name = cls.strip().lstrip('L').rstrip(';').replace('.', '/')
    for root in smali_roots(dec):
        p = os.path.join(root, name + '.smali')
        if os.path.isfile(p):
            return p
    # 兜底：按文件名搜（类名大小写/内联类异常时）
    target = os.path.basename(name) + '.smali'
    for root in smali_roots(dec):
        for dirpath, _d, files in os.walk(root):
            if target in files:
                cand = os.path.join(dirpath, target)
                if cand.replace(os.sep, '/').endswith(name + '.smali'):
                    return cand
    return None


def norm_desc(desc):
    """--desc 兼容 '(I)' 和 'I' 两种写法"""
    d = (desc or '').strip()
    if d.startswith('(') and d.endswith(')'):
        d = d[1:-1]
    return d


def read(path):
    with open(path, encoding='utf-8', errors='ignore') as f:
        return f.read()


def backup(path):
    bak = path + '.bak'
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    return bak


def parse_methods(text):
    """返回 [{start, header, name, desc, ret, locals_idx, locals_kind, locals_n}]"""
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        m = METHOD_RE.match(lines[i])
        if not m:
            i += 1
            continue
        header = m.group(1).strip()
        dm = re.search(r'\(([^)]*)\)(\S+)\s*$', header)
        name = header.split('(')[0].split()[-1]
        desc = dm.group(1) if dm else ''
        ret = dm.group(2) if dm else 'V'
        # 找 .locals/.registers
        j = i + 1
        locals_idx, locals_kind, locals_n = None, None, 0
        while j < len(lines) and not lines[j].strip().startswith('.end method'):
            s = lines[j].strip()
            if locals_idx is None and (s.startswith('.locals') or s.startswith('.registers')):
                lm = re.match(r'\.(locals|registers)\s+(\d+)', s)
                if lm:
                    locals_idx = j
                    locals_kind = lm.group(1)
                    locals_n = int(lm.group(2))
            j += 1
        out.append({'start': i, 'header': header, 'name': name, 'desc': desc,
                    'ret': ret, 'locals_idx': locals_idx,
                    'locals_kind': locals_kind, 'locals_n': locals_n,
                    'end': j if j < len(lines) else len(lines) - 1})
        i = j + 1
    return out


def insert_index(lines, m):
    """补丁插入点：.locals 之后，跳过 .param/.annotation/.prologue/# 注释"""
    idx = (m['locals_idx'] + 1) if m['locals_idx'] is not None else (m['start'] + 1)
    k = idx
    while k < len(lines):
        s = lines[k].strip()
        if (not s or s.startswith('#') or s.startswith('.param') or s.startswith('.annotation')
                or s.startswith('.end annotation') or s.startswith('.prologue') or s.startswith('.line')):
            k += 1
            continue
        break
    return k


def reg_width(desc, is_static):
    """参数占用寄存器数（long/double 算 2）"""
    n = 0 if is_static else 1
    if not desc:
        return n
    i = 0
    while i < len(desc):
        c = desc[i]
        if c == '[':
            n += 1
            i += 1
            while i < len(desc) and desc[i] == '[':
                i += 1
            if i < len(desc) and desc[i] in 'LJJD':
                if desc[i] == 'L':
                    i = desc.find(';', i) + 1
                else:
                    i += 1
            else:
                i += 1
        elif c in 'L':
            n += 1
            i = desc.find(';', i) + 1
        elif c in 'JD':
            n += 2
            i += 1
        else:
            n += 1
            i += 1
    return n


def build_ret(value, ret_type, lines, m):
    """按返回类型生成 [(指令行)]，必要时返回需要的 .locals 增量"""
    v = (value or '').strip()
    if v == 'void' or ret_type == 'V':
        return ['    return-void'], 0
    if v in ('true', 'false'):
        lit = '0x1' if v == 'true' else '0x0'
        if ret_type == 'Z':
            return [f'    const/4 v0, {lit}', '    return v0'], 1
        raise SystemExit(f'方法返回类型 {ret_type} 不是 Z，--return {v} 不合适（用 --return 1/0 或 str:xxx）')
    if v == 'null':
        return ['    const/4 v0, 0x0', '    return-object v0'], 1
    if v.startswith('str:') or v.startswith('string:'):
        s = v.split(':', 1)[1].replace('\\', '\\\\').replace('"', '\\"')
        return [f'    const-string v0, "{s}"', '    return-object v0'], 1
    # 数字
    try:
        num = int(v, 0)
    except ValueError:
        raise SystemExit(f'看不懂 --return {v}：用 true/false/void/null/number/str:文本')
    if ret_type == 'J':
        return [f'    const-wide v0, {hex(num)}L', '    return-wide v0'], 1
    if ret_type in ('F', 'D'):
        raise SystemExit('浮点返回：把 float 的 IEEE 位用 --return 0x3f800000 打（类型 F 除外用 int 表示）')
    if ret_type in ('Z', 'I', 'S', 'B'):
        if -8 <= num <= 7:
            ins = f'const/4 v0, {hex(num if num >= 0 else num & 0xf)}'
        elif -32768 <= num <= 32767:
            ins = f'const/16 v0, {hex(num if num >= 0 else num & 0xffff)}'
        else:
            ins = f'const v0, {hex(num if num >= 0 else num & 0xffffffff)}'
        return [f'    {ins}', '    return v0'], 1
    # 对象/数组返回数字 → 只接受 0（null）
    if num == 0:
        return ['    const/4 v0, 0x0', '    return-object v0'], 1
    raise SystemExit(f'方法返回 {ret_type}，--return {v} 不是合法值（对象只能 null）')


def apply_patch(path, lines, m, ins_lines, need_locals, extra_note):
    """改 .locals（不够时）→ 插指令 → 写回。返回新文本"""
    patched = lines[:]
    # 寄存器不足：.locals 直接加大；.registers 需要算参数
    if need_locals and m['locals_idx'] is not None:
        if m['locals_kind'] == 'locals' and m['locals_n'] < need_locals:
            patched[m['locals_idx']] = f'    .locals {need_locals}'
        elif m['locals_kind'] == 'registers':
            is_static = 'static' in m['header']
            need = reg_width(m['desc'], is_static) + need_locals
            if m['locals_n'] < need:
                patched[m['locals_idx']] = f'    .registers {need}'
    idx = insert_index(patched, m)
    block = [f'    {MARK} {extra_note} ==='] + ins_lines
    new = patched[:idx] + block + patched[idx:]
    return '\n'.join(new) + ('\n' if new and not new[-1].endswith('\n') else '')


def write(path, text, dry):
    if dry:
        old = read(path).splitlines()
        new = text.splitlines()
        diff = difflib.unified_diff(old, new, fromfile=path, tofile=path + ' (patched)', lineterm='')
        print('\n'.join(diff))
        return
    backup(path)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def cmd_find(args):
    dec = args.dir
    pat = re.compile(args.pattern)
    hits = 0
    for root in smali_roots(dec):
        for dirpath, _d, files in os.walk(root):
            for fn in sorted(files):
                if not fn.endswith('.smali'):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    txt = read(p)
                except OSError:
                    continue
                if not pat.search(txt) and not pat.search(fn):
                    continue
                for m in parse_methods(txt):
                    sig = f"{m['name']}({m['desc']}){m['ret']}"
                    if not pat.search(sig):
                        continue
                    if args.ret and m['ret'] != args.ret:
                        continue
                    print(f"{os.path.relpath(p, dec)}  ::  {sig}")
                    hits += 1
                    if hits >= args.limit:
                        return
    if hits == 0:
        print('  无命中 —— 名字被 R8 混淆时改用 --pattern 搜调用点/字符串，或走 Frida 动态找')


def cmd_ret(args):
    dec = args.dir
    path = class_file(dec, args.cls)
    if not path:
        raise SystemExit(f'找不到类 smali: {args.cls}（先跑 find 子命令或检查 smali_classes* 里是否存在）')
    txt = read(path)
    cands = [m for m in parse_methods(txt) if m['name'] == args.method]
    if args.desc:
        cands = [m for m in cands if m['desc'] == norm_desc(args.desc)]
    if not cands:
        sigs = ', '.join(sorted({f"{m['name']}({m['desc']}){m['ret']}" for m in parse_methods(txt)}))[:600]
        raise SystemExit(f'{args.cls} 里没有方法 {args.method}。同名候选/全部方法:\n  {sigs}')
    if len(cands) > 1 and not args.all:
        raise SystemExit('有多个同名方法，用 --desc 指定，或 --all 全部打：\n' +
                         '\n'.join(f"  {m['name']}({m['desc']}){m['ret']}" for m in cands))
    if args.restore:
        bak = path + '.bak'
        if not os.path.exists(bak):
            raise SystemExit('没有备份，无法回滚')
        shutil.copy2(bak, path)
        print(f'已回滚: {path}')
        return
    if args.return_ is None:
        raise SystemExit('需要 --return（true/false/void/null/整数/str:文本）')

    if any(m['locals_idx'] is None for m in cands):
        raise SystemExit('目标是 abstract/native 方法（没有 .locals，无方法体），不能插补丁；'
                         '改它的实现方/调用方')
    targets = cands if args.all else cands[:1]
    for t in targets:
        sig = f"{t['name']}({t['desc']}){t['ret']}"
        marker = f'{MARK} ret={args.return_} {sig} ==='
        cur = read(path)
        if (marker in cur or marker.replace(MARK, LEGACY_MARK) in cur) and not args.force:
            print(f'跳过（已打过）: {sig}')
            continue
        lines = cur.splitlines()
        m = next((x for x in parse_methods(cur) if f"{x['name']}({x['desc']}){x['ret']}" == sig), None)
        if m is None:
            raise SystemExit(f'重新解析后找不到方法 {sig}')
        ins, need = build_ret(args.return_, m['ret'], lines, m)
        patched = apply_patch(path, lines, m, ins, need, f"ret={args.return_} {sig}")
        write(path, patched, args.dry_run)
        print(f"{'[dry-run] ' if args.dry_run else '已补丁: '}{os.path.relpath(path, dec)} :: "
              f"{sig} → {args.return_}")
    if not args.dry_run:
        print('下一步: bash scripts/build_sign.sh <解码目录> /path/out.apk')


def cmd_field(args):
    dec = args.dir
    m = re.match(r'^L?([\w/$]+);->([\w$]+):(\S+)$', args.field.strip())
    if not m:
        raise SystemExit('--field 格式: Lcom/app/Flag;->isVip:Z')
    cls, fname, ftype = m.group(1), m.group(2), m.group(3)
    path = class_file(dec, cls)
    if not path:
        raise SystemExit(f'找不到类 smali: {cls}')
    txt = read(path)
    if not re.search(rf'\.field[^\n]*\b{re.escape(fname)}:{re.escape(ftype)}', txt):
        raise SystemExit(f'{cls} 里没有字段 {fname}:{ftype}')
    if not re.search(rf'\.field[^\n]*static[^\n]*\b{re.escape(fname)}:{re.escape(ftype)}', txt):
        raise SystemExit(f'{fname}:{ftype} 不是 static 字段，sput 不适用（实例字段要改构造器/定义处）')
    if args.restore:
        bak = path + '.bak'
        if not os.path.exists(bak):
            raise SystemExit('没有备份，无法回滚')
        shutil.copy2(bak, path)
        print(f'已回滚: {path}')
        return
    if args.value is None:
        raise SystemExit('需要 --value（true/false/整数）')
    marker = f'{MARK} field {fname}={args.value.strip()} ==='
    if (marker in txt or marker.replace(MARK, LEGACY_MARK) in txt) and not args.force:
        print(f'跳过（已打过）: {fname}={args.value.strip()}')
        return

    v = args.value.strip()
    if ftype == 'Z':
        lit = '0x1' if v in ('true', '1') else '0x0'
        ins = [f'    const/4 v0, {lit}', f'    sput-boolean v0, L{cls};->{fname}:Z']
    elif ftype in ('I', 'S', 'B'):
        num = int(v, 0)
        lit = hex(num if num >= 0 else (num & 0xffffffff))
        ins = [f'    const v0, {lit}', f'    sput v0, L{cls};->{fname}:{ftype}']
    elif ftype == 'J':
        num = int(v, 0)
        ins = [f'    const-wide v0, {hex(num)}L', f'    sput-wide v0, L{cls};->{fname}:J']
    elif ftype.startswith('L') or ftype.startswith('['):
        if v != 'null':
            raise SystemExit('对象字段只支持 --value null')
        ins = ['    const/4 v0, 0x0', f'    sput-object v0, L{cls};->{fname}:{ftype}']
    else:
        raise SystemExit(f'不支持的字段类型 {ftype}')

    lines = txt.splitlines()
    clinit = [mth for mth in parse_methods(txt) if mth['name'] == '<clinit>']
    if clinit:
        mth = clinit[0]
        patched = apply_patch(path, lines, mth, ins, 1, f"field {fname}={v}")
    else:
        # 没有 <clinit>：追加一个静态构造器
        body = ['', '.method static constructor <clinit>()V', '    .locals 1',
                f'    {MARK} field {fname}={v} ==='] + ins + ['    return-void', '.end method',
                                                             '']
        patched = txt + '\n'.join(body)
    write(path, patched, args.dry_run)
    print(f"{'[dry-run] ' if args.dry_run else '已补丁: '}{os.path.relpath(path, dec)} "
          f"<clinit> 置 L{cls};->{fname}:{ftype} = {v}")
    if not args.dry_run:
        print('下一步: bash scripts/build_sign.sh <解码目录> /path/out.apk')


def main():
    ap = argparse.ArgumentParser(description='smali 定点补丁器（返回值 / 静态字段初值）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    f = sub.add_parser('find', help='按正则搜方法签名')
    f.add_argument('dir', help='apktool 解码目录')
    f.add_argument('--pattern', required=True, help='正则，如 isVip|isPro|hasPurchased')
    f.add_argument('--ret', help='只看某返回类型，如 Z / I / J')
    f.add_argument('--limit', type=int, default=40)
    f.set_defaults(func=cmd_find)

    r = sub.add_parser('ret', help='方法返回固定值（权益 恒真 / 数值改大）')
    r.add_argument('dir')
    r.add_argument('--class', dest='cls', required=True, help='com/app/User 或 Lcom/app/User;')
    r.add_argument('--method', required=True)
    r.add_argument('--desc', help='参数描述符，如 (Landroid/content/Context;) 或 ()')
    r.add_argument('--return', dest='return_',
                   help='true/false/void/null/整数(可 0x)/str:文本（--restore 时不需要）')
    r.add_argument('--all', action='store_true', help='同名方法全打')
    r.add_argument('--dry-run', action='store_true')
    r.add_argument('--restore', action='store_true')
    r.add_argument('--force', action='store_true')
    r.set_defaults(func=cmd_ret)

    d = sub.add_parser('field', help='<clinit> 里置静态字段初值')
    d.add_argument('dir')
    d.add_argument('--field', required=True, help='Lcom/app/Flag;->isVip:Z')
    d.add_argument('--value', help='true/false/整数（--restore 时不需要）')
    d.add_argument('--dry-run', action='store_true')
    d.add_argument('--restore', action='store_true')
    d.add_argument('--force', action='store_true')
    d.set_defaults(func=cmd_field)

    args = ap.parse_args()
    if not os.path.isdir(args.dir):
        sys.exit(f'不是目录: {args.dir}')
    args.func(args)


if __name__ == '__main__':
    main()
