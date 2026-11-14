#!/usr/bin/env python3
"""轻量证据台账：把「观察 / 结论 / 卡点」落盘，避免凭记忆下结论。

用法:
  python3 scripts/ledger.py observe  "看到什么" --kind static --evidence 文件:行
  python3 scripts/ledger.py conclude "结论是什么" --kind server-side --proof 依据
  python3 scripts/ledger.py stuck    "卡在哪" --tried "试过什么"
  python3 scripts/ledger.py query
  python3 scripts/ledger.py --file work/ledger.json query

台账默认写到 ./work/ledger.json（可用 --file 指定）。纯标准库，无依赖。
"""
import argparse
import datetime
import json
import os
import sys

DEFAULT = os.path.join('work', 'ledger.json')


def load(path):
    if not os.path.exists(path):
        return {'entries': []}
    try:
        return json.load(open(path, encoding='utf-8'))
    except Exception:
        print(f'! 台账损坏，已备份并重建: {path}')
        os.replace(path, path + '.broken')
        return {'entries': []}


def save(path, data):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(description='证据台账')
    ap.add_argument('--file', default=DEFAULT)
    ap.add_argument('action', choices=['observe', 'conclude', 'stuck', 'query'])
    ap.add_argument('text', nargs='?', default='')
    ap.add_argument('--kind', default='')
    ap.add_argument('--evidence', default='')
    ap.add_argument('--proof', default='')
    ap.add_argument('--tried', default='')
    a = ap.parse_args()

    data = load(a.file)
    if a.action == 'query':
        if not data['entries']:
            print('台账为空')
            return 0
        for e in data['entries']:
            print(f"[{e['ts']}] {e['action']:<8} {e['text'][:80]}" + (f"  ({e.get('kind')})" if e.get('kind') else ''))
        return 0

    if not a.text:
        print('需要一段描述文字')
        return 2
    entry = {
        'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'action': a.action,
        'text': a.text,
    }
    if a.kind: entry['kind'] = a.kind
    if a.evidence: entry['evidence'] = a.evidence
    if a.proof: entry['proof'] = a.proof
    if a.tried: entry['tried'] = a.tried
    data['entries'].append(entry)
    save(a.file, data)
    print(f"✓ 已记入台账（{a.action}）：{a.text[:60]}  -> {a.file}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
