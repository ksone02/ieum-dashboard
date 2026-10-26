"""단계 규칙과 화면 문구 규칙. 입력 자료 없이 돎."""

from ieum.agent import _reason, level_of


def test_levels_follow_fixed_rule():
    assert level_of({'contact': 0.03}, [{'kind': 'blocked'}])[0] == 1  # 하위 5% + 갈 곳 없음
    assert level_of({'sk': 0.15}, [{'kind': 'blocked'}])[0] == 3  # 신호 보통 + 갈 곳 없음
    assert level_of({'contact': 0.1, 'out': 0.1}, [{'kind': 'mismatch'}])[0] == 1
    assert level_of({'contact': 0.03}, [])[0] == 2  # 신호 강함 + 갈 곳 있음
    assert level_of({'sk': 0.15}, [{'kind': 'closed'}])[0] == 4  # 모집 종료만은 공백으로 안 셈
    assert level_of({'contact': 0.97, 'out': 0.01}, [{'kind': 'blocked'}])[0] == 3  # 연락이 많으면 강함 아님


def test_weekend_flow_alone_is_never_strong():
    assert level_of({'sk': 0.02, 'contact': 0.5, 'out': 0.3}, [])[0] == 4  # 동 전체 값 하나뿐
    assert level_of({'sk': 0.1, 'contact': 0.1, 'out': 0.3}, [])[0] == 2  # 개인 신호 + 동 값
    assert level_of({'sk': 0.1, 'contact': 0.1, 'out': 0.9}, [])[0] == 4  # 외출이 많으면 동 값은 안 셈


def test_reason_codes_never_shown_raw():
    assert _reason('residence:OUTSIDE_AREA', {}) == '대상 동이 아님'
    assert _reason('residence:SOME_NEW_CODE', {'residence': '세부 거주지역'}) == '세부 거주지역'
    assert _reason('x:SOME_NEW_CODE', {}) == '기타 조건'
