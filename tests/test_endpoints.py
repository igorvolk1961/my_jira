"""Инвариант: набор маршрутов (rule, endpoint) не должен меняться при рефакторинге.

Файл tests/endpoints_baseline.txt фиксирует исходный набор. Любое изменение
URL или имени endpoint (от которого зависит url_for) сломает этот тест.
"""

import os

import main

BASELINE = os.path.join(os.path.dirname(__file__), 'endpoints_baseline.txt')


def _current():
    return sorted((r.rule, r.endpoint) for r in main.app.url_map._rules)


def _baseline():
    with open(BASELINE, encoding='utf-8') as f:
        out = []
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue
            rule, endpoint = line.split('\t')
            out.append((rule, endpoint))
    return sorted(out)


def test_endpoints_match_baseline():
    current = _current()
    base = _baseline()
    missing = sorted(set(base) - set(current))
    added = sorted(set(current) - set(base))
    assert not missing, f'Пропали маршруты: {missing}'
    assert not added, f'Появились новые маршруты: {added}'
    assert len(current) == len(base)
