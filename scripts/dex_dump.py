#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内存 DEX 导出（自研 Frida 脚本驱动，不依赖 frida-dexdump，无 GPL 代码）。

用法:
    python3 dex_dump.py --package com.example.app
    python3 dex_dump.py --pid 1234 --out /sdcard/Download/dsh-dex-dump
    python3 dex_dump.py --package com.example.app --host 127.0.0.1:27043 --rounds 2 --interval 5
    python3 dex_dump.py --package com.example.app --protections 'rw-,r-x,rwx'   # 只扫可写/可执行
    python3 dex_dump.py --package com.example.app --protections 'r--,rw-,r-x' --timeout 180

前置:
    - 手机已 root，frida-server 已启动（技能里 adb_device.sh frida start / status 可查）
    - frida-python 与 frida-server 主版本一致（本机 frida 17.x）
    - 目标 App 已启动并完成壳解密（加壳 App 建议 --rounds 2/3 提高命中率）
输出:
    - 每个 DEX 一个文件，已校验 magic/version/header_size/file_size/endian/adler32
    - 同名内容自动去重（同一 DEX 的多个内存映射只落一份）
    - 退出码: 0=至少导出 1 个有效 DEX；1=没找到；2=连接/脚本错误
"""
import argparse
import hashlib
import os
import re
import sys
import threading
import time
import zlib

try:
    import frida
except ImportError:
    print('错误: 需要 frida-python（pip install frida）', file=sys.stderr)
    raise SystemExit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
JS_PATH = os.path.join(HERE, 'dex_dump.js')

MIN_DEX = 0x70
HEADER_SIZE = 0x70
ENDIAN_LE = 0x12345678


def valid_dex(data):
    """严格校验一个 DEX：magic/version/header_size/file_size/endian/adler32。"""
    if len(data) < MIN_DEX or data[:4] != b'dex\n':
        return False, 'magic'
    if not (data[4:7].isdigit() and data[7] == 0):
        return False, 'version'
    file_size = int.from_bytes(data[0x20:0x24], 'little')
    header_size = int.from_bytes(data[0x24:0x28], 'little')
    endian_tag = int.from_bytes(data[0x28:0x2c], 'little')
    checksum = int.from_bytes(data[0x08:0x0c], 'little')
    if header_size != HEADER_SIZE:
        return False, 'header_size(%d)' % header_size
    if file_size != len(data):
        return False, 'file_size(%d)!=len(%d)' % (file_size, len(data))
    if endian_tag != ENDIAN_LE:
        return False, 'endian(0x%x)' % endian_tag
    if (zlib.adler32(data[12:]) & 0xffffffff) != checksum:
        return False, 'adler32'
    return True, ''


def _resolve_pid(device, package):
    """按包名找 PID。Android 进程名不一定是包名（可能是应用显示名，如「全球网测」），
    所以优先用 enumerate_applications 的 identifier，再退回进程名匹配。"""
    try:
        for app in device.enumerate_applications():
            if app.identifier == package and app.pid:
                return app.pid
    except Exception:
        pass
    for proc in device.enumerate_processes():
        if proc.name == package:
            return proc.pid
    return None


def attach(device, args):
    try:
        if args.package:
            try:
                return device.attach(args.package)
            except frida.ProcessNotFoundError:
                pid = _resolve_pid(device, args.package)
                if pid is None:
                    print('错误: 找不到包 %s 的运行进程。请先启动 App（例如 adb shell monkey -p %s 1）后再试；'
                          '若已在运行，用 --pid 指定。' % (args.package, args.package), file=sys.stderr)
                    return None
                return device.attach(pid)
        return device.attach(args.pid)
    except Exception as exc:
        print('错误: 无法 attach %s: %s' % (args.package or args.pid, exc), file=sys.stderr)
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog='dex_dump.py', description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--package', help='目标包名（attach 已运行进程）')
    g.add_argument('--pid', type=int, help='目标 PID')
    ap.add_argument('--host', default='127.0.0.1:27043', help='frida-server 地址（默认 127.0.0.1:27043）')
    ap.add_argument('--out', default='/sdcard/Download/dsh-dex-dump', help='输出目录')
    ap.add_argument('--timeout', type=int, default=120, help='整轮总等待秒数（默认 120）')
    ap.add_argument('--rounds', type=int, default=1, help='扫描轮数；加壳 App 建议 2-3（默认 1）')
    ap.add_argument('--interval', type=float, default=3.0, help='轮间隔秒数（默认 3）')
    ap.add_argument('--protections', default='r--,rw-,r-x,rwx',
                    help="扫描的内存保护段，逗号分隔（默认 'r--,rw-,r-x,rwx'；壳解密后的 DEX 常在 rw-/rwx/r-x）")
    ap.add_argument('--max-bytes', type=int, default=0, help='单轮发送字节上限（默认 0=脚本内置 256MB）')
    args = ap.parse_args(argv)

    # ── 参数校验（旧版 --rounds 0 / 非法 --protections 会静默跑成空结果）──
    errs = []
    if args.rounds < 1:
        errs.append('--rounds 至少为 1（当前 %d）：轮数不能是 0 或负数' % args.rounds)
    if args.interval < 0:
        errs.append('--interval 不能是负数（当前 %s）' % args.interval)
    if args.timeout < 1:
        errs.append('--timeout 至少为 1 秒（当前 %d）' % args.timeout)
    if args.max_bytes < 0:
        errs.append('--max-bytes 不能是负数（当前 %d；0 表示用脚本内置 256MB）' % args.max_bytes)
    prot_tokens = [p.strip() for p in args.protections.split(',') if p.strip()]
    if not prot_tokens:
        errs.append("--protections 不能为空，示例: 'r--,rw-,r-x,rwx'")
    else:
        bad = [p for p in prot_tokens if not re.fullmatch(r'[r-][w-][x-]', p)]
        if bad:
            errs.append('--protections 含非法段 %s：每段必须是 rwx 三个字符（r=可读，-=无），'
                        "如 'r--'、'rw-'、'r-x'、'rwx'，逗号分隔" % bad)
        else:
            unreadable = [p for p in prot_tokens if p[0] != 'r']
            if unreadable:
                errs.append('--protections 里这些段不可读，扫不出 DEX: %s（第一字符必须是 r）' % unreadable)
            args.protections = ','.join(dict.fromkeys(prot_tokens))
    if errs:
        for e in errs:
            print('错误: %s' % e, file=sys.stderr)
        return 2

    # 输出目录延迟创建：扫描/连接全失败时不留空目录
    created_out = not os.path.isdir(args.out)
    device = frida.get_device_manager().add_remote_device(args.host)
    session = attach(device, args)
    if session is None:
        return 2

    lock = threading.Lock()
    saved = []           # [(path, size, sha256, version)]
    seen_sha = set()
    rejected = {}        # 原因 -> 次数
    script_errors = []
    skipped_dup = 0
    done_stats = []
    pkg_bytes = args.package.encode() if args.package else None

    def on_message(message, data):
        nonlocal skipped_dup
        mtype = message.get('type')
        if mtype == 'error':
            with lock:
                script_errors.append(str(message.get('stack') or message.get('description') or message))
            return
        payload = message.get('payload') or {}
        kind = payload.get('type')
        if kind == 'dex':
            if data is None:
                with lock:
                    rejected['无数据'] = rejected.get('无数据', 0) + 1
                return
            raw = bytes(data)
            ok, why = valid_dex(raw)
            if not ok:
                with lock:
                    rejected[why] = rejected.get(why, 0) + 1
                return
            sha = hashlib.sha256(raw).hexdigest()
            with lock:
                if sha in seen_sha:
                    skipped_dup += 1
                    return
                seen_sha.add(sha)
                idx = len(saved) + 1
                version = raw[4:7].decode('ascii', 'replace')
                path = os.path.join(args.out, 'classes_dump_%02d_%s.dex' % (idx, sha[:8]))
                try:
                    if created_out:
                        os.makedirs(args.out, exist_ok=True)
                    with open(path, 'wb') as f:
                        f.write(raw)
                except OSError as exc:
                    script_errors.append('写文件失败 %s: %s' % (path, exc))
                    return
                is_app = bool(pkg_bytes) and pkg_bytes in raw
                saved.append((path, len(raw), sha, version, is_app))
            print('[+] %s %d bytes, dex %s, addr %s%s' % (
                path, len(raw), version, payload.get('address', '?'),
                '  [APP]' if (payload.get('isApp') or is_app) else ''), flush=True)
        elif kind == 'error':
            with lock:
                script_errors.append(payload.get('message') or 'script error')

    with open(JS_PATH, 'r', encoding='utf-8') as f:
        js = f.read()
    # 告诉脚本由 Python 驱动，别在加载后自动扫一轮
    js = 'globalThis.__DSH_DEX_MANAGED = true;\n' + js
    script = session.create_script(js)
    script.on('message', on_message)
    try:
        script.load()
    except Exception as exc:
        print('错误: 脚本加载失败: %s' % exc, file=sys.stderr)
        return 2

    deadline = time.time() + args.timeout
    try:
        for rnd in range(1, args.rounds + 1):
            if time.time() >= deadline:
                script_errors.append('超时，未开始第 %d 轮' % rnd)
                break
            msg = {'protections': args.protections}
            if args.max_bytes > 0:
                msg['maxBytes'] = args.max_bytes
            holder = {}

            def _do_scan(msg=msg, holder=holder):
                try:
                    holder['stats'] = script.exports_sync.scan(msg)
                except Exception as exc:  # noqa: BLE001 - 任何 RPC 失败都报给用户
                    holder['error'] = str(exc)

            th = threading.Thread(target=_do_scan, daemon=True)
            th.start()
            th.join(timeout=max(1.0, deadline - time.time()))
            if th.is_alive():
                script_errors.append('第 %d 轮扫描超时（总超时 %.0fs）' % (rnd, args.timeout))
                break
            if 'error' in holder:
                script_errors.append('第 %d 轮扫描失败: %s' % (rnd, holder['error']))
                break
            st = holder.get('stats') or {}
            done_stats.append(st)
            print('[*] 第 %d 轮: 扫描 %s 个 range, magic 命中 %s, 候选 %s, 发送 %s 个/%s bytes, '
                  '重复 %s, 读失败 %s, range 扫描失败 %s, 跨段尝试 %s(成功 %s/失败 %s), 用时 %sms' % (
                      rnd, st.get('ranges', '?'), st.get('matches', '?'), st.get('candidates', '?'),
                      st.get('sent', '?'), st.get('bytes', '?'), st.get('dup', '?'),
                      st.get('readFail', '?'), st.get('scanFail', '?'),
                      st.get('crossRangeTry', '?'), st.get('crossRangeOk', '?'),
                      st.get('crossRangeFail', '?'), st.get('elapsedMs', '?')),
                  flush=True)
            if st.get('budgetHit'):
                print('[!] 达到 --max-bytes 上限，后面的候选没发送；要扫全请调大该值（当前 %s）'
                      % (args.max_bytes or '脚本内置 256MB'), flush=True)
            if rnd < args.rounds:
                time.sleep(max(0.0, args.interval))
    finally:
        try:
            session.detach()
        except Exception:
            pass

    # 一个有效 DEX 都没有时，删掉「本次新建的空输出目录」，别留空壳
    if created_out and not saved:
        try:
            os.rmdir(args.out)
        except OSError:
            pass

    if script_errors:
        print('脚本错误: %s' % '; '.join(script_errors[:5]), file=sys.stderr)

    print('[=] 结果: 有效 DEX %d 个 -> %s' % (len(saved), args.out))
    if rejected:
        print('    丢弃的候选: %s' % ', '.join('%s×%d' % (k, v) for k, v in sorted(rejected.items())))
    if skipped_dup:
        print('    内容重复跳过: %d' % skipped_dup)
    app_count = sum(1 for x in saved if x[4])
    for path, size, sha, ver, is_app in saved:
        print('    %s  %d bytes  dex %s%s  sha256:%s' % (
            path, size, ver, '  [APP]' if is_app else '', sha), flush=True)
    if pkg_bytes:
        print('    其中含目标包名 %s 的: %d / %d（其余多为系统框架/boot vdex 等内存 DEX）' % (
            args.package, app_count, len(saved)))

    if not saved:
        print('未发现有效 DEX。排查建议: 确认目标进程已启动且壳已解密（加 --rounds 2/3）、'
              '或放宽 --protections、加 --rounds、检查 frida-server 与 frida-python 版本一致。',
              file=sys.stderr)
        return 2 if script_errors else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
