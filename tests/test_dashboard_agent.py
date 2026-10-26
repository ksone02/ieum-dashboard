import dashboard_server as s


def test_agent_judgements():
    agent = s.build_agent(s.load_data(), s.REASONS)
    p = {x['id']: x for x in agent['personas']}
    assert sum(x['kind'] == 'rep' for x in agent['personas']) == 5
    field = lambda pid, f: next(x for x in p[pid]['fields'] if x['function'] == f)
    assert field('P2', '관계 형성')['status'] == 'mismatch'      # 외출 적은데 관계 형성은 전부 나가서 만나는 방식
    assert field('P3', '주거·안전')['status'] == 'blocked'
    assert field('P3', '주거·안전')['opens_if'][0]['change'] == '1인가구 요건을 풀면'
    assert field('P4', '관계 형성')['status'] == 'unknown'
    assert all(f['kind'] == 'closed' for f in p['P1']['findings'])  # 일자리 모집 종료만 남음


def test_dong_personas_use_dong_limited_programs():
    agent = s.build_agent(s.load_data(), s.REASONS)
    dong = [p for p in agent['personas'] if p['kind'] == 'dong']
    assert dong and all(p['dong'] and p['location'] for p in dong)
    # 사는 동이 들어가면 동 한정 사업은 '확인 필요'로 남지 않음
    import policy_gap_engine as e, run_persona_recommend as rr
    rows, _ = e.evaluate([e.Persona('강남', 70, '남', '1인', '저소득', dong='신사동')], rr.load_programs_with_area())
    assert set(rows[rows.id.isin(['G02', 'GN-25'])].reason) == {'residence:OUTSIDE_AREA'}


def test_policy_recommendations():
    import dashboard_policy as dp
    data = s.load_data()
    pol = dp.build_policy(s.build_agent(data, s.REASONS), data['sources'])
    cc = {r['title']: r for r in pol['춘천']['recs']}
    # 춘천은 저녁·주말 회차가 가장 많이 열고, 주거·안전은 새 사업이 필요함(조건을 바꿔도 안 열림)
    assert pol['춘천']['recs'][0]['kind'] in ('condition', 'new') and pol['춘천']['whole']['저녁·주말 회차 열기'] > 0
    assert any(r['kind'] == 'new' and r['function'] == '주거·안전' for r in pol['춘천']['recs'])
    assert all(r['count'] == len(r['personas']) for v in pol.values() for r in v['recs'])


def test_levels_follow_fixed_rule():
    import dashboard_agent as a
    assert a.level_of({'contact': 0.03}, [{'kind': 'blocked'}])[0] == 1          # 하위 5% + 갈 곳 없음
    assert a.level_of({'sk': 0.15}, [{'kind': 'blocked'}])[0] == 3               # 신호 보통 + 갈 곳 없음
    assert a.level_of({'contact': 0.1, 'out': 0.1}, [{'kind': 'mismatch'}])[0] == 1
    assert a.level_of({'contact': 0.03}, [])[0] == 2                              # 신호 강함 + 갈 곳 있음
    assert a.level_of({'sk': 0.15}, [{'kind': 'closed'}])[0] == 4                # 모집 종료만은 공백으로 안 셈
    assert a.level_of({'contact': 0.97, 'out': 0.01}, [{'kind': 'blocked'}])[0] == 3   # 연락이 많으면 신호 강함 아님
    agent = s.build_agent(s.load_data(), s.REASONS)
    assert all(p['level'] in (1, 2, 3, 4) and len(p['trace']) == 6 for p in agent['personas'])


def test_reason_codes_never_shown_raw():
    from dashboard_agent import _reason
    assert _reason('residence:OUTSIDE_AREA', {}) == '대상 동이 아님'
    assert _reason('residence:SOME_NEW_CODE', {'residence': '세부 거주지역'}) == '세부 거주지역'
    assert _reason('x:SOME_NEW_CODE', {}) == '기타 조건'


def test_meet_programs_without_local_site_rank_last():
    import run_persona_recommend as rr
    r = rr.recommend()
    gn = r[(r.label.str.len() > 0) & (r.function == '관계 형성') & r.persona.isin(['P1'])]
    assert gn.sort_values('rank').iloc[0].id != 'GN-01'  # 서울마음편의점은 강남 지점이 없음


def test_weekend_flow_alone_is_never_strong():
    from dashboard_agent import level_of
    assert level_of({'sk': .02, 'contact': .5, 'out': .3}, [])[0] == 4  # 동 전체 값 하나뿐
    assert level_of({'sk': .1, 'contact': .1, 'out': .3}, [])[0] == 2  # 개인 신호 + 동 값
    assert level_of({'sk': .1, 'contact': .1, 'out': .9}, [])[0] == 4  # 외출이 많으면 동 값은 안 셈
