"""화면이 읽는 결과 JSON끼리 숫자가 맞는지 확인. 입력 자료 없이 돎."""

import json
from collections import Counter

from ieum.paths import WEB_DATA

agent = json.loads((WEB_DATA / 'agent.json').read_text())
personas = json.loads((WEB_DATA / 'personas.json').read_text())
policy = json.loads((WEB_DATA / 'policy.json').read_text())


def test_summary_matches_detail():
    for s in agent['personas']:
        d = personas[s['id']]
        assert (s['level'], s['dong'], s['region']) == (d['level'], d['dong'], d['region'])


def test_region_and_dong_counts():
    for region, r in agent['regions'].items():
        levels = Counter(p['level'] for p in personas.values() if p['region'] == region)
        assert {int(k): v for k, v in r['levels'].items() if v} == dict(levels)
        for d in r['dongs']:
            assert {int(k): v for k, v in d['levels'].items() if v} == dict(
                Counter(personas[i]['level'] for i in d['personas'])
            )


def test_policy_counts():
    for region, q in policy.items():
        for rec in q['recs']:
            assert rec['count'] == len(rec['personas'])
            assert all(personas[i]['region'] == region for i in rec['personas'])
            assert sum(rec['dongs'].values()) == sum(personas[i]['kind'] == 'dong' for i in rec['personas'])


def test_links_are_single_urls():
    for p in personas.values():
        for f in p['fields']:
            for x in f['programs']:
                assert not x['source'] or (x['source'].startswith('http') and ' ' not in x['source'])
