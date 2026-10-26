"""입력 자료(data/)로 전체를 돌려 보는 시험. 자료가 없으면 건너뜀."""

import pytest

from ieum import engine as e
from ieum import recommend as rr
from ieum.agent import build_agent
from ieum.paths import POLICY
from ieum.policy import build_policy
from ieum.sources import REASONS, load_data

pytestmark = pytest.mark.skipif(not POLICY.exists(), reason='로컬 입력(data/) 없음')


@pytest.fixture(scope='module')
def data():
    return load_data()


@pytest.fixture(scope='module')
def agent(data):
    return build_agent(data, REASONS)


def test_agent_judgements(agent):
    p = {x['id']: x for x in agent['personas']}
    assert sum(x['kind'] == 'rep' for x in agent['personas']) == 5

    def field(pid, f):
        return next(x for x in p[pid]['fields'] if x['function'] == f)

    assert field('P2', '관계 형성')['status'] == 'mismatch'  # 외출 적은데 관계 형성은 전부 나가서 만나는 방식
    assert field('P3', '주거·안전')['status'] == 'blocked'
    assert field('P3', '주거·안전')['opens_if'][0]['change'] == '1인가구 요건을 풀면'
    assert field('P4', '관계 형성')['status'] == 'unknown'
    assert all(f['kind'] == 'closed' for f in p['P1']['findings'])  # 일자리 모집 종료만 남음
    assert all(x['level'] in (1, 2, 3, 4) and len(x['trace']) == 6 for x in agent['personas'])


def test_dong_personas_use_dong_limited_programs(agent):
    dong = [p for p in agent['personas'] if p['kind'] == 'dong']
    assert dong and all(p['dong'] and p['location'] for p in dong)
    # 사는 동이 들어가면 동 한정 사업은 '확인 필요'로 남지 않음
    persona = e.Persona('강남', 70, '남', '1인', '저소득', dong='신사동')
    rows, _ = e.evaluate([persona], rr.load_programs_with_area())
    assert set(rows[rows.id.isin(['G02', 'GN-25'])].reason) == {'residence:OUTSIDE_AREA'}


def test_policy_recommendations(data, agent):
    pol = build_policy(agent, data['sources'])
    # 춘천은 저녁·주말 회차가 가장 많이 열고, 주거·안전은 새 사업이 필요함(조건을 바꿔도 안 열림)
    assert pol['춘천']['recs'][0]['kind'] in ('condition', 'new')
    assert pol['춘천']['whole']['저녁·주말 회차 열기'] > 0
    assert any(r['kind'] == 'new' and r['function'] == '주거·안전' for r in pol['춘천']['recs'])
    assert all(r['count'] == len(r['personas']) for v in pol.values() for r in v['recs'])


def test_meet_programs_without_local_site_rank_last():
    r = rr.recommend()
    gn = r[(r.function == '관계 형성') & (r.persona == 'P1')]
    assert gn.sort_values('rank').iloc[0].id != 'GN-01'  # 서울마음편의점은 강남 지점이 없음
