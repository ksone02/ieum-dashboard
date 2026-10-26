"""강남·춘천 고립 지원사업의 지원경로 판정 엔진(노션 06 페이지의 4계층 규칙).

L1 요건: 사업 조건 하나하나를 가상 주민 조건과 비교해 MET / CONFLICT / REVIEW / UNKNOWN / N/A 를 낸다.
L2 경로: 사업 하나에 대해 L1을 묶는다. 충돌이 하나라도 있으면 그 경로만 '충돌'이다.
L3 포트폴리오: 같은 지원 기능의 사업들을 함께 보고, 그 주민에게 남는 가장 나은 경로를 낸다.

정보가 없으면 UNKNOWN이다. 부적격도 적격도 아니다. 공백은 "이번 조사 범위에서 조건이 맞는 사업을 찾지 못함"이지
"지원이 없다"가 아니다. 가상 주민은 조건 조합이며 실제 사람 수가 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ieum.paths import POLICY

MET, CONFLICT, REVIEW, UNKNOWN, NA = 'MET', 'CONFLICT', 'REVIEW', 'UNKNOWN', 'N/A'
FUNCTIONS = ['발굴·안부', '관계 형성', '상담', '돌봄', '일자리', '주거·안전', '의료 접근']
# 자격 판단의 핵심 정보. 미확인이면 경로는 '확인 필요'다.
CORE = {'status', 'age', 'residence', 'household', 'income', 'target', 'channel'}
# 부가 정보. 미확인이면 '조건부(정보 미확인)'로 둔다. 단, 시간 제약이 있는 주민에게 운영시간 미확인은 핵심 정보다(code TIME_UNVERIFIED).
MINOR = {'screening', 'device', 'time'}

# L2 경로 판정
PATH_OK = '이용 가능'
PATH_SCREEN = '조건부(심사)'
PATH_INFO = '조건부(부가정보 미확인)'
PATH_OUTREACH = '기관 발굴로만 연결'
PATH_UNKNOWN = '확인 필요'
PATH_CONFLICT = '충돌'
PATH_ORDER = [PATH_OK, PATH_SCREEN, PATH_INFO, PATH_OUTREACH, PATH_UNKNOWN, PATH_CONFLICT]
OPEN_PATHS = {PATH_OK, PATH_SCREEN, PATH_INFO}

# L3 포트폴리오 판정: 같은 기능에서 가장 나은 경로를 따른다.
PORT_OK = '경로 있음(이용 가능)'
PORT_SCREEN = '경로 있음(심사 필요)'
PORT_INFO = '경로 있음(부가정보 미확인)'
PORT_OUTREACH = '기관 발굴로만 연결'
PORT_UNKNOWN = '확인 필요만 남음'
PORT_CONFLICT = '공백(조건 충돌)'
PORT_NONE = '공백(해당 기능 사업 없음)'
PORT_ORDER = [PORT_OK, PORT_SCREEN, PORT_INFO, PORT_OUTREACH, PORT_UNKNOWN, PORT_CONFLICT, PORT_NONE]
PORT_OPEN = {PORT_OK, PORT_SCREEN, PORT_INFO}
_P2P = dict(zip(PATH_ORDER, PORT_ORDER, strict=False))

# 접근 방식 묶음: 주민이 스스로 쓸 수 있는 신청 채널과 기기.
ACCESS = {
    '일반(모든 채널 가능)': dict(channels={'visit', 'phone', 'online', 'app'}, smartphone=True, android=True),
    '아이폰 사용': dict(channels={'visit', 'phone', 'online', 'app'}, smartphone=True, android=False),
    '대면·전화 부담(온라인만)': dict(channels={'online', 'app'}, smartphone=True, android=True),
    '디지털 취약(방문·전화만)': dict(channels={'visit', 'phone'}, smartphone=False, android=False),
}

# 대상 특성의 종류. '심사'는 선정 과정에서 확인하는 특성(위험도·필요도), '속성'은 주민이 갖췄는지가 자격인 특성이다.
# 가상 주민에게는 '속성'이 없으므로 확인 필요가 된다.
TARGET_TYPE = {
    '없음': '없음',
    '장애인': '장애인',
    # 주민이 갖췄는지가 자격인 속성(가상 주민에게 없음 → 확인 필요)
    '대졸(예정) 청년': '속성',
    '주거취약(저층·반지하·옥탑)': '속성',
    '혼자 외출 어려움': '속성',
    '고립은둔·미취업': '속성',
    # 선정 과정에서 위험도·필요도로 확인하는 특성(→ 심사)
    '고립위험': '심사',
    '고립은둔': '심사',
    '고독사위험': '심사',
    '우울위험': '심사',
    '우울·고립감': '심사',
    '무연고·우울': '심사',
    '돌봄필요': '심사',
    '구직단념': '심사',
    '위기징후': '심사',
    '건강관리필요': '심사',
    '고립은둔·가족돌봄': '심사',
    '관계망 형성 필요': '심사',
    '고위험': '심사',
}


@dataclass(frozen=True)
class Persona:
    region: str
    age: int
    sex: str = '여'
    household: str = '1인'  # 1인 / 다인
    income: str = '일반'  # 저소득 / 일반
    access: str = '일반(모든 채널 가능)'
    weekday_day_ok: bool = True  # 평일 낮에 참여할 수 있는가
    disabled: bool = False
    dong: str = ''  # 사는 동. 비어 있으면 동·단지 한정 사업은 확인 필요(기존 판정과 같음)

    @property
    def channels(self):
        return ACCESS[self.access]['channels']


@dataclass
class Check:
    item: str
    state: str
    code: str = ''
    note: str = ''


def _y(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return '미확인'
    s = str(v).strip()
    return s if s else '미확인'


def _age(p: Persona, g: dict) -> Check:
    if _y(g['age_known']) != 'Y':
        return Check('age', UNKNOWN, 'AGE_UNSTATED')
    lo, hi = g.get('age_min'), g.get('age_max')
    ok = (pd.isna(lo) or p.age >= int(lo)) and (pd.isna(hi) or p.age <= int(hi))
    return Check('age', MET if ok else CONFLICT, '' if ok else 'AGE_OUT_OF_RANGE')


def _household(p: Persona, g: dict) -> Check:
    h = _y(g['household_req'])
    one = p.household == '1인'
    if h == '무관':
        return Check('household', MET)
    if h in ('1인가구', '독거노인'):
        # 독거노인의 나이 조건은 나이 항목에서 본다(나이 미확인 사업에 65세를 몰래 적용하지 않는다).
        return Check('household', MET if one else CONFLICT, '' if one else 'HOUSEHOLD')
    if h == '1인가구(다인 예외심사)':
        return Check('household', MET if one else REVIEW, '' if one else 'HOUSEHOLD_EXCEPTION')
    if h == '독거노인(저소득 2인 예외)':
        if one:
            return Check('household', MET)
        return Check(
            'household',
            REVIEW if p.income == '저소득' else CONFLICT,
            'HOUSEHOLD_EXCEPTION' if p.income == '저소득' else 'HOUSEHOLD',
        )
    if h == '여성1인가구':
        ok = one and p.sex == '여'
        return Check('household', MET if ok else CONFLICT, '' if ok else 'HOUSEHOLD')
    return Check('household', UNKNOWN, 'POLICY_FACT_MISSING')


def _income(p: Persona, g: dict) -> Check:
    i = _y(g['income_req'])
    if i in ('없음', '우선순위'):
        return Check('income', MET)
    if i == '저소득필수':
        return Check('income', MET if p.income == '저소득' else CONFLICT, '' if p.income == '저소득' else 'INCOME')
    if i == '기초연금수준':
        # 기초연금은 65세 이상 소득 하위 약 70%가 받는다. '일반' 소득 주민도 해당될 수 있어 심사로 둔다.
        return Check('income', MET if p.income == '저소득' else REVIEW, '' if p.income == '저소득' else 'INCOME_SCREEN')
    return Check('income', UNKNOWN, 'POLICY_FACT_MISSING')


def _target(p: Persona, g: dict) -> Check:
    t = _y(g.get('target_req'))
    if t == '미확인':
        return Check('target', UNKNOWN, 'POLICY_FACT_MISSING')
    if t not in TARGET_TYPE:
        raise ValueError(f'TARGET_TYPE에 없는 대상 특성: {t}')
    kind = TARGET_TYPE[t]
    if kind == '없음':
        return Check('target', MET)
    if kind == '장애인':
        return Check('target', MET if p.disabled else CONFLICT, '' if p.disabled else 'TARGET')
    if kind == '속성':
        return Check('target', UNKNOWN, 'TARGET_ATTR_UNKNOWN', t)
    return Check('target', REVIEW, 'TARGET_SCREEN', t)


def _channel(p: Persona, g: dict) -> Check:
    """신청 채널은 OR. 쓸 수 있는 채널이 하나라도 확인되면 충족. 미확인 채널이 남아 있으면 확인 필요.
    주민이 직접 열 수 있는 채널이 없고 기관이 찾아오는 경로만 확인되면 '기관 발굴로만 연결'."""
    chs = {c: _y(g[f'ch_{c}']) for c in ('online', 'phone', 'visit', 'app', 'outreach')}
    usable = {c for c in p.channels if chs[c] == 'Y'}
    if usable:
        return Check('channel', MET, '', '/'.join(sorted(usable)))
    if any(chs[c] == '미확인' for c in p.channels):
        return Check('channel', UNKNOWN, 'CHANNEL_UNVERIFIED')
    if chs['outreach'] == 'Y':
        return Check('channel', REVIEW, 'OUTREACH_ONLY')
    return Check('channel', CONFLICT, 'CHANNEL')


def _device(p: Persona, g: dict) -> Check:
    d = _y(g['device_req'])
    a = ACCESS[p.access]
    # 전화 수신은 누구나 가능하다고 본다. 전화가 부담스러운 것은 선호이지 접근 실패가 아니다.
    dev = {
        '없음': True,
        'IoT장비': True,
        '전화수신': True,
        '스마트폰': a['smartphone'],
        '안드로이드': a['android'],
    }.get(d)
    if dev is None:
        return Check('device', UNKNOWN, 'DEVICE_UNVERIFIED')
    return Check('device', MET if dev else CONFLICT, '' if dev else 'DEVICE')


def _time(p: Persona, g: dict) -> Check:
    when = _y(g['schedule'])
    if when == '해당없음':
        return Check('time', NA)
    if when == '미확인':
        # 평일 낮에 못 오는 주민에게 운영시간 미확인은 이용 여부를 가르는 핵심 정보다.
        return Check('time', UNKNOWN, 'POLICY_FACT_MISSING' if p.weekday_day_ok else 'TIME_UNVERIFIED')
    if when == '평일주간':
        return Check('time', MET if p.weekday_day_ok else CONFLICT, '' if p.weekday_day_ok else 'TIME')
    return Check('time', MET)  # 주말·야간 포함, 24시간


def _residence(p: Persona, g: dict, r: str) -> Check:
    if r in ('지역전체', '광역', '생활권허용'):
        return Check('residence', MET)
    area = [d for d in str(g.get('area_dongs') or '').split(';') if d]
    # 사는 동과 사업 대상 동을 둘 다 알 때만 판정. 단지 한정은 동이 맞아도 단지는 모르니 심사로 둠.
    if p.dong and area and r in ('동한정', '단지한정'):
        if p.dong not in area:
            return Check('residence', CONFLICT, 'OUTSIDE_AREA')
        return Check('residence', MET) if r == '동한정' else Check('residence', REVIEW, 'COMPLEX_ONLY')
    # 동·단지·배달 지역 한정은 가상 주민의 세부 주소가 없어 확인 필요로 둔다.
    return Check(
        'residence',
        UNKNOWN,
        'SERVICE_AREA_UNVERIFIED' if r in ('동한정', '단지한정', '배달가능지역') else 'POLICY_FACT_MISSING',
    )


def l1(p: Persona, g: dict) -> list[Check]:
    """사업 g(조건 표의 한 행)를 주민 p에 대해 요건별로 판정한다."""
    s = _y(g['status_2026'])
    r = _y(g['residence_scope'])
    sc = _y(g['screening'])
    return [
        Check(
            'status',
            {'운영중': MET, '종료': CONFLICT}.get(s, UNKNOWN),
            {'종료': 'CLOSED', '모집종료': 'ROUND_UNVERIFIED', '미확인': 'STATUS_UNVERIFIED'}.get(s, ''),
        ),
        Check(
            'region', MET if g['region'] == p.region else CONFLICT, '' if g['region'] == p.region else 'OTHER_REGION'
        ),
        _age(p, g),
        _residence(p, g, r),
        _household(p, g),
        _income(p, g),
        _target(p, g),
        Check(
            'screening',
            {'있음': REVIEW, '없음': MET}.get(sc, UNKNOWN),
            {'있음': 'SCREENING', '없음': ''}.get(sc, 'SCREENING_UNVERIFIED'),
        ),
        _channel(p, g),
        _device(p, g),
        _time(p, g),
    ]


def l2(checks: list[Check]) -> tuple[str, str]:
    """사업 하나의 경로 판정과 그 이유 코드."""

    def why(cs):
        return ';'.join(f'{c.item}:{c.code}' for c in cs)

    bad = [c for c in checks if c.state == CONFLICT]
    if bad:
        return PATH_CONFLICT, why(bad)
    core = [c for c in checks if c.state == UNKNOWN and (c.item in CORE or c.code == 'TIME_UNVERIFIED')]
    if core:
        return PATH_UNKNOWN, why(core)
    if any(c.item == 'channel' and c.code == 'OUTREACH_ONLY' for c in checks):
        return PATH_OUTREACH, 'channel:OUTREACH_ONLY'
    info = [c for c in checks if c.state == UNKNOWN and c.item in MINOR]
    screen = [c for c in checks if c.state == REVIEW]
    if info:
        return PATH_INFO, why(screen + info)
    if screen:
        return PATH_SCREEN, why(screen)
    return PATH_OK, ''


def l3(paths: list[str], n_programs: int) -> str:
    """같은 기능 사업들의 경로 중 가장 나은 것을 포트폴리오 판정으로 낸다."""
    if n_programs == 0:
        return PORT_NONE
    return _P2P[min(paths, key=PATH_ORDER.index)]


def functions_of(g: dict) -> list[str]:
    """주기능과 보조기능(세미콜론으로 여러 개)."""
    sec = _y(g.get('function_secondary'))
    return [g['function']] + ([x.strip() for x in sec.split(';') if x.strip()] if sec != '미확인' else [])


def has_function(g: dict, f: str) -> bool:
    return f in functions_of(g)


def evaluate(personas: list[Persona], programs: pd.DataFrame, functions=FUNCTIONS):
    """모든 (주민, 사업) 경로와 (주민, 기능) 포트폴리오를 계산한다."""
    rows, port = [], []
    progs = programs.to_dict('records')
    for pi, p in enumerate(personas):
        cache = {}
        for g in progs:
            if g['region'] != p.region:
                continue
            ch = l1(p, g)
            state, why = l2(ch)
            cache[g['id']] = state
            rows.append(
                {
                    'persona': pi,
                    'id': g['id'],
                    'function': g['function'],
                    'functions': ';'.join(functions_of(g)),
                    'path': state,
                    'reason': why,
                    **{f'l1_{c.item}': c.state for c in ch},
                }
            )
        for f in functions:
            ids = [g['id'] for g in progs if g['region'] == p.region and has_function(g, f)]
            st = [cache[i] for i in ids]
            port.append(
                {
                    'persona': pi,
                    'function': f,
                    'n_programs': len(ids),
                    **{f'n_{k}': st.count(k) for k in PATH_ORDER},
                    'portfolio': l3(st, len(ids)),
                    'is_open': l3(st, len(ids)) in PORT_OPEN,
                    'open_ids': ','.join(i for i, s in zip(ids, st, strict=False) if s in OPEN_PATHS),
                }
            )
    pdf = pd.DataFrame([{'persona': i, **p.__dict__} for i, p in enumerate(personas)])
    rows = pd.DataFrame(rows, columns=None if rows else ['persona', 'id', 'function', 'functions', 'path', 'reason'])
    return rows.merge(pdf, on='persona'), pd.DataFrame(port).merge(pdf, on='persona')


def load_programs() -> pd.DataFrame:
    g = pd.read_csv(POLICY / 'policy_programs_final.csv', encoding='utf-8-sig', dtype=str)
    for c in ('age_min', 'age_max'):
        g[c] = pd.to_numeric(g[c], errors='coerce')
    return g


def scenarios(g: pd.DataFrame) -> dict[str, pd.DataFrame]:
    s = {}
    self_apply = g[['ch_online', 'ch_phone', 'ch_visit', 'ch_app']].isin(['Y', '미확인']).any(axis=1)
    a = g.copy()
    a.loc[self_apply, ['ch_online', 'ch_phone']] = 'Y'  # 신청형 사업에만 추가(발굴형은 신청 채널이 없으므로 그대로)
    s['S1 온라인·전화 신청 추가'] = a
    a = g.copy()
    a.loc[a.schedule == '평일주간', 'schedule'] = '야간·주말포함'
    s['S2 저녁·주말 회차 추가'] = a
    a = g.copy()
    a.loc[a.household_req.isin(['1인가구', '1인가구(다인 예외심사)']), 'household_req'] = '무관'
    # 독거노인 요건은 가구만 풀고 나이 조건은 그대로 둔다(나이 미확인 사업에 나이를 채워 넣지 않는다).
    a.loc[a.household_req.isin(['독거노인', '독거노인(저소득 2인 예외)']), 'household_req'] = '무관'
    s['S3 1인가구 요건 완화'] = a
    a = g.copy()
    a.loc[a.income_req == '저소득필수', 'income_req'] = '우선순위'
    s['S4 소득 요건 완화'] = a
    a = g.copy()
    a.loc[a.age_max == 64, 'age_max'] = 69
    s['S5 64세 상한을 69세로'] = a
    a = g.copy()
    a.loc[a.age_known != 'Y', 'age_known'] = 'Y'  # 나이를 '누구나'로 공개했다고 가정
    a.loc[a.income_req == '미확인', 'income_req'] = '없음'
    s['S6 나이·소득 미확인 사업이 제한 없음으로 공개'] = a
    return s
