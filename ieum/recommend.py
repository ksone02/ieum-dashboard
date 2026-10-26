"""페르소나 5개를 정책 엔진에 넣고, 데이터 근거 특성으로 추천 순서를 정함.

자격 판정은 엔진 그대로임. 순서 규칙은 갈 수 있는 사업 안에서 무엇을 먼저 보여 줄지만 정함.
순서: ① 특성에 맞는 서비스 방식 ② 평일 낮이 안 되면 야간·주말 운영 먼저 ③ 이용 가능 > 심사 > 정보 미확인.

    python -m ieum.recommend
"""

import pandas as pd

from ieum import engine as e
from ieum.engine import load_programs
from ieum.paths import PERSONAS as OUT

MEET, REMOTE, HOME = '나가서 만남', '전화·온라인', '집으로 찾아옴'

# 특성 → 먼저 보여 줄 서비스 방식. 결과를 보기 전에 정한 규칙임.
RULES = {
    '연락 적음·외출 많음': [MEET, REMOTE, HOME],  # 밖에는 나가니 만남의 자리로 연결
    '연락 많음·외출 적음': [HOME, MEET, REMOTE],  # 연락은 이미 많으니 전화보다 찾아가서 밖으로 이끄는 것부터
    '연락·외출 모두 적음': [HOME, REMOTE, MEET],  # 스스로 나오기 어려우니 찾아가는 것부터
    '사람 만나는 소비 적음': [MEET, REMOTE, HOME],
    '혼자 끼니 해결': [MEET, HOME, REMOTE],  # 함께하는 자리 먼저, 그다음 찾아오는 서비스
    '주말 활동 약세': [MEET, REMOTE, HOME],
    '연락 적음': [MEET, HOME, REMOTE],  # 전화 연결이 약하니 만남·방문부터
    '외출 적음': [REMOTE, HOME, MEET],  # 나오기 어려우니 집에서 받는 것부터
}

P = e.Persona
PERSONAS = [
    (
        'P1',
        '강남 개포2동 20대 여성',
        '연락 적음·외출 많음',
        P('강남', 25, '여', '1인', '일반', '일반(모든 채널 가능)', False, dong='개포2동'),
    ),
    (
        'P2',
        '강남 논현1동 30대 여성',
        '연락 많음·외출 적음',
        P('강남', 33, '여', '1인', '일반', '일반(모든 채널 가능)', True, dong='논현1동'),
    ),
    (
        'P3',
        '강남 40대 남성(가족 동거)',
        '사람 만나는 소비 적음',
        P('강남', 45, '남', '다인', '일반', '일반(모든 채널 가능)', False),
    ),
    ('P4', '춘천 20대 여성', '주말 활동 약세', P('춘천', 24, '여', '1인', '일반', '일반(모든 채널 가능)', False)),
    (
        'P5',
        '춘천 70대 남성(혼자 삶)',
        '혼자 끼니 해결',
        P('춘천', 72, '남', '1인', '일반', '디지털 취약(방문·전화만)', True),
    ),
]
STATUS_RANK = {e.PATH_OK: 0, e.PATH_SCREEN: 1, e.PATH_INFO: 2}


def load_programs_with_area():
    """동·단지 한정 사업의 대상 동을 붙임. 페르소나에 동이 있을 때만 엔진이 씀."""
    area = pd.read_csv(OUT / 'program_area.csv')[['id', 'area_dongs']]
    return load_programs().merge(area, on='id', how='left').fillna({'area_dongs': ''})


def recommend(personas=None):
    personas = personas or PERSONAS
    programs = load_programs_with_area()
    delivery = pd.read_csv(OUT / 'program_delivery.csv')
    assert set(programs.id) <= set(delivery.id), set(programs.id) - set(delivery.id)
    rows, _ = e.evaluate([p for *_, p in personas], programs)
    rows = rows[rows.path.isin(STATUS_RANK)].drop(columns='function')
    # 두 분야에 걸친 사업(예: 노인맞춤돌봄 = 돌봄+관계 형성)은 분야마다 한 줄씩 둠
    rows = rows.assign(function=rows.functions.str.split(';')).explode('function')
    rows = rows.merge(delivery, on='id').merge(programs[['id', 'program', 'schedule']], on='id')
    site_in = dict(zip(programs.id, programs.site_in_region, strict=False))
    out = []
    for i, (code, label, trait, persona) in enumerate(personas):
        order = RULES[trait]
        r = rows[rows.persona == i].copy()
        r['k_delivery'] = r.delivery.map(order.index)
        # 지역 안에 시설이 없는 '나가서 만남' 사업(예: 서울마음편의점은 강남 지점 없음)은 같은 방식 안에서 뒤로
        r['k_site'] = ((r.delivery == '나가서 만남') & r.id.map(site_in.get).eq('N')).astype(int)
        r['k_time'] = 0 if persona.weekday_day_ok else (r.schedule != '야간·주말포함').astype(int)
        r['k_status'] = r.path.map(STATUS_RANK)
        r = r.sort_values(['function', 'k_delivery', 'k_site', 'k_time', 'k_status', 'id'])
        r['rank'] = r.groupby('function').cumcount() + 1
        out.append(r.assign(persona=code, label=label, trait=trait, rule=' > '.join(order)))
    cols = [
        'persona',
        'label',
        'trait',
        'rule',
        'function',
        'rank',
        'id',
        'program',
        'delivery',
        'sure',
        'schedule',
        'path',
    ]
    return pd.concat(out)[cols]


if __name__ == '__main__':
    result = recommend()
    OUT.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT / 'persona_recommendations.csv', index=False, encoding='utf-8-sig')
    for code, g in result[result.function.isin(['관계 형성', '발굴·안부', '상담'])].groupby('persona'):
        print(f'== {code} {g.label.iat[0]} | {g.trait.iat[0]} → {g.rule.iat[0]}')
        for _, x in g.iterrows():
            print(f'   {x.function} {x["rank"]}. {x.program} [{x.delivery}/{x.schedule}/{x.path}]')
