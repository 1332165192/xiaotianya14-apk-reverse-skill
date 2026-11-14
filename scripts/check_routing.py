#!/usr/bin/env python3
"""校验 tests/routing_cases.json：每条用例的期望文件是否存在、JSON 结构是否完整。

不修改任何文件。退出码 0 = 通过，1 = 有问题。
内部专用用例（internal_only=true）在公开版里允许缺失，只提示。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, 'tests', 'routing_cases.json')


def main():
    if not os.path.isfile(CASES):
        print('✗ 缺少 tests/routing_cases.json')
        return 1
    try:
        data = json.load(open(CASES, encoding='utf-8'))
    except Exception as e:
        print(f'✗ JSON 解析失败: {e}')
        return 1
    cases = data.get('cases')
    if not isinstance(cases, list) or not cases:
        print('✗ cases 为空')
        return 1
    errors, warns = [], []
    for i, c in enumerate(cases, 1):
        if not isinstance(c, dict) or 'task' not in c or 'route' not in c:
            errors.append(f'case {i}: 缺 task/route')
            continue
        if 'expect' in c:
            for p in c['expect']:
                if not os.path.exists(os.path.join(ROOT, p)):
                    msg = f'case {i}「{c["task"]}」缺少文件: {p}'
                    (warns if c.get('internal_only') else errors).append(msg)
        if 'expect_any' in c:
            ok = any(os.path.exists(os.path.join(ROOT, p)) for p in c['expect_any'])
            if not ok:
                msg = f'case {i}「{c["task"]}」这些文件都不存在: {c["expect_any"]}'
                (warns if c.get('internal_only') else errors).append(msg)
    for w in warns:
        print('! ' + w)
    for e in errors:
        print('✗ ' + e)
    if errors:
        print(f'✗ 路由用例检查失败：{len(errors)} 个问题')
        return 1
    print(f'✅ 路由用例检查通过（{len(cases)} 条，内部专用缺失 {len(warns)} 条）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
