"""06 페이지 '반드시 구현할 규칙'과 09 페이지 독립 기대 판정(EX-01~04)을 확인한다."""
import pandas as pd

import policy_gap_engine as e

BASE = dict(id='P', region='춘천', function='관계 형성', function_secondary='', status_2026='운영중', age_known='Y',
            age_min=19, age_max=64, residence_scope='지역전체', household_req='무관', income_req='없음', target_req='없음',
            screening='없음', ch_online='N', ch_phone='N', ch_visit='Y', ch_app='N', ch_outreach='N',
            device_req='없음', schedule='평일주간')


def prog(**kw):
    return {**BASE, **kw}


def path(p, g):
    return e.l2(e.l1(p, g))[0]


def item(p, g, name):
    return next(c for c in e.l1(p, g) if c.item == name)


P50 = e.Persona(region='춘천', age=52)


def test_ex01_schedule_missing_is_unknown_not_conflict():
    c = item(P50, prog(schedule='미확인'), 'time')
    assert (c.state, c.code) == (e.UNKNOWN, 'POLICY_FACT_MISSING')


def test_ex02_weekday_day_only_conflicts_for_person_unavailable_then():
    p = e.Persona(region='춘천', age=52, weekday_day_ok=False)
    assert item(p, prog(), 'time').state == e.CONFLICT
    assert path(p, prog()) == e.PATH_CONFLICT


def test_ex03_phone_or_visit_is_met_when_one_works():
    p = e.Persona(region='춘천', age=52, access='디지털 취약(방문·전화만)')
    assert item(p, prog(ch_visit='N', ch_phone='Y'), 'channel').state == e.MET


def test_ex04_separate_selection_is_review():
    assert path(P50, prog(screening='있음')) == e.PATH_SCREEN


def test_and_rule_conflict_only_blocks_that_path():
    progs = pd.DataFrame([prog(id='A', household_req='1인가구'), prog(id='B')])
    p = e.Persona(region='춘천', age=52, household='다인')
    rows, port = e.evaluate([p], progs, ['관계 형성'])
    assert dict(zip(rows.id, rows.path)) == {'A': e.PATH_CONFLICT, 'B': e.PATH_OK}
    assert port.portfolio.iloc[0] == e.PORT_OK


def test_app_refusal_only_removes_app_channel():
    p = e.Persona(region='춘천', age=52, access='디지털 취약(방문·전화만)')
    assert item(p, prog(ch_app='Y', ch_visit='Y'), 'channel').state == e.MET
    assert item(p, prog(ch_app='Y', ch_visit='N'), 'channel').state == e.CONFLICT


def test_unknown_is_neither_eligible_nor_ineligible():
    g = prog(income_req='미확인')
    assert path(P50, g) == e.PATH_UNKNOWN
    rows, port = e.evaluate([P50], pd.DataFrame([g]), ['관계 형성'])
    assert port.portfolio.iloc[0] == e.PORT_UNKNOWN


def test_different_function_is_not_an_alternative():
    progs = pd.DataFrame([prog(id='A', age_max=39), prog(id='B', function='돌봄')])
    rows, port = e.evaluate([P50], progs, ['관계 형성'])
    assert port.portfolio.iloc[0] == e.PORT_CONFLICT


def test_no_program_in_function_is_separate_gap():
    rows, port = e.evaluate([P50], pd.DataFrame([prog()]), ['상담'])
    assert port.portfolio.iloc[0] == e.PORT_NONE


def test_secondary_function_counts_as_same_function():
    rows, port = e.evaluate([P50], pd.DataFrame([prog(function='돌봄', function_secondary='관계 형성')]), ['관계 형성'])
    assert port.portfolio.iloc[0] == e.PORT_OK


def test_outreach_only_program_is_its_own_category():
    g = prog(ch_visit='N', ch_outreach='Y')
    assert item(P50, g, 'channel').code == 'OUTREACH_ONLY'
    assert path(P50, g) == e.PATH_OUTREACH
    rows, port = e.evaluate([P50], pd.DataFrame([g]), ['관계 형성'])
    assert port.portfolio.iloc[0] == e.PORT_OUTREACH and not port.is_open.iloc[0]


def test_unverified_channel_is_checked_before_outreach():
    p = e.Persona(region='춘천', age=52, access='대면·전화 부담(온라인만)')
    assert item(p, prog(ch_visit='N', ch_online='미확인', ch_outreach='Y'), 'channel').state == e.UNKNOWN


def test_unknown_target_is_unknown_not_met():
    assert item(P50, prog(target_req='미확인'), 'target').state == e.UNKNOWN
    assert item(P50, prog(target_req=None), 'target').state == e.UNKNOWN


def test_attribute_target_is_unknown_and_screen_target_is_review():
    assert path(P50, prog(target_req='주거취약(저층·반지하·옥탑)')) == e.PATH_UNKNOWN
    assert path(P50, prog(target_req='고립은둔')) == e.PATH_SCREEN


def test_round_closed_is_unknown():
    assert item(P50, prog(status_2026='모집종료'), 'status').code == 'ROUND_UNVERIFIED'
    assert path(P50, prog(status_2026='모집종료')) == e.PATH_UNKNOWN


def test_dokgeo_without_stated_age_does_not_hide_age_rule():
    g = prog(household_req='독거노인', age_known='N', age_min=None, age_max=None)
    assert item(e.Persona(region='춘천', age=60), g, 'household').state == e.MET
    assert path(e.Persona(region='춘천', age=60), g) == e.PATH_UNKNOWN


def test_household_exceptions_go_to_review():
    multi = e.Persona(region='춘천', age=70, household='다인', income='저소득')
    assert item(multi, prog(household_req='1인가구(다인 예외심사)'), 'household').state == e.REVIEW
    assert item(multi, prog(household_req='독거노인(저소득 2인 예외)'), 'household').state == e.REVIEW
    rich = e.Persona(region='춘천', age=70, household='다인', income='일반')
    assert item(rich, prog(household_req='독거노인(저소득 2인 예외)'), 'household').state == e.CONFLICT


def test_unknown_schedule_is_core_for_time_constrained_person():
    busy = e.Persona(region='춘천', age=52, weekday_day_ok=False)
    assert path(busy, prog(schedule='미확인')) == e.PATH_UNKNOWN
    assert path(P50, prog(schedule='미확인')) == e.PATH_INFO


def test_phone_call_service_is_not_blocked_by_call_burden():
    p = e.Persona(region='춘천', age=70, access='대면·전화 부담(온라인만)')
    assert item(p, prog(device_req='전화수신'), 'device').state == e.MET


def test_android_requirement_blocks_iphone_user_only():
    g = prog(device_req='안드로이드', ch_app='Y', schedule='해당없음')
    assert path(e.Persona(region='춘천', age=46, access='아이폰 사용'), g) == e.PATH_CONFLICT
    assert path(e.Persona(region='춘천', age=46), g) == e.PATH_OK


def test_other_region_program_is_ignored():
    rows, port = e.evaluate([e.Persona(region='강남', age=52)], pd.DataFrame([prog()]), ['관계 형성'])
    assert port.portfolio.iloc[0] == e.PORT_NONE


def test_basic_pension_level_income_is_screened_for_general_income():
    g = prog(income_req='기초연금수준')
    assert item(e.Persona(region='춘천', age=70, income='일반'), g, 'income').state == e.REVIEW
    assert item(e.Persona(region='춘천', age=70, income='저소득'), g, 'income').state == e.MET


def test_multiple_secondary_functions():
    g = prog(function='돌봄', function_secondary='발굴·안부;관계 형성;상담')
    assert e.functions_of(g) == ['돌봄', '발굴·안부', '관계 형성', '상담']
    rows, port = e.evaluate([P50], pd.DataFrame([g]), ['상담'])
    assert port.portfolio.iloc[0] == e.PORT_OK


def test_every_target_in_final_table_is_declared():
    import pathlib
    f = pathlib.Path(__file__).resolve().parents[1] / 'data' / 'policy' / 'policy_programs_final.csv'
    g = pd.read_csv(f, encoding='utf-8-sig', dtype=str)
    assert set(g.target_req.dropna()) - {'미확인'} <= set(e.TARGET_TYPE)
