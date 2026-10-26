"""동마다 페르소나를 만듦: 동 × 성별 × 나이대 집단 중 고립 쪽 특성이 두드러진 곳.

신호 세 가지(0에 가까울수록 고립 쪽).
- 연락(M3): 서울 같은 성별·나이대 중 위치. 강남만.
- 외출(M3): 평일·휴일 이동 중 높은 쪽의 위치 = 둘 다 적어야 낮게 나옴. 강남만.
- 머무는 곳의 주말 활동(SK): 평일 유입(유동 ÷ 인구)을 뺀 나머지를 같은 지역·성별·나이대 동끼리 비교. 강남·춘천.
페르소나 = 하나라도 하위 20%(LOW). 연락이 상위 20%(HIGH)면 제외.

2026-10-26 첫 기준(하나라도 하위 20%, 외출은 낮은 쪽, SK 순위 그대로)에서 바꿈. 바꾼 이유:
- SK 주말/평일 비율이 평일 유입과 강하게 얽힘(강남 상관 -0.59) → 사무실 동이 위로 올라옴
- 연락이 상위 1%인 집단이 "외출 적음"으로 걸림 → 연락이 많으면 고립 쪽으로 보지 않음
- 동 22~25개의 순위를 %로 바꾸면 가장 낮은 동이 자동으로 하위 5% → 순위 대신 값의 차이(정규분포 위치)로 씀
카드 결과는 구·시 단위라 페르소나를 만드는 데는 쓰지 않고 근거로만 붙임.
이 페르소나들은 가상 인물이며 그 동의 실제 주민 수·고립 여부를 뜻하지 않음.

    python -m ieum.personas
"""

from statistics import NormalDist

import numpy as np
import pandas as pd

from ieum.paths import DATA
from ieum.paths import PERSONAS as OUT

LOW, HIGH = 0.2, 0.8
LAYERS = DATA / 'external/gn_cc_dong_layers.csv'  # 동 추정 인구
AGE = {'20대': 25, '30대': 35, '40대': 45, '50대': 55, '60세 이상': 70}
CARD = {
    ('강남', '남', '40대'): '사람 만나는 곳(식당·카페·술집) 소비 비중이 앞뒤 나이대보다 약 20% 낮아요 (강남구 전체)',
    ('강남', '남', '60세 이상'): '편의점·패스트푸드 소비 비중이 같은 나이 여성의 1.4~1.6배예요 (강남구 전체)',
    ('춘천', '남', '60세 이상'): '편의점·패스트푸드 소비 비중이 같은 나이 여성의 1.4~1.6배예요 (춘천시 전체)',
}
TITLE = {
    '연락·외출 모두 적음': '연락도 외출도 적은',
    '연락 적음·외출 많음': '밖에는 나가는데 연락은 적은',
    '연락 많음·외출 적음': '연락은 많은데 밖에 잘 안 나가는',
    '연락 적음': '연락이 적은',
    '외출 적음': '밖에 잘 안 나가는',
    '주말 활동 약세': '머무는 곳이 주말에 한산한',
}


def trait(contact, out, sk):
    lo = lambda v: pd.notna(v) and v <= LOW
    hi = lambda v: pd.notna(v) and v >= HIGH
    if hi(contact):
        return ''
    if lo(contact) and lo(out):
        return '연락·외출 모두 적음'
    if lo(contact) and hi(out):
        return '연락 적음·외출 많음'
    if lo(contact):
        return '연락 적음'
    if lo(out):
        return '외출 적음'
    if lo(sk):
        return '주말 활동 약세'
    return ''


def pos(v):
    """서울 같은 성별·나이대 중 위치를 '하위/상위 몇 %'로 씀(0에 가까울수록 적음)."""
    return f'하위 {max(v * 100, 1):.0f}%' if v <= 0.5 else f'상위 {max((1 - v) * 100, 1):.0f}%'


def sk_adjusted(sk):
    """주말/평일 비율에서 평일 유입 효과를 빼고, 같은 지역·성별·나이대 안에서 값의 위치(0~1)를 냄.

    평일 유입 = 그 동 SK 유동 합 ÷ 추정 인구(로그). 지역마다 성별·나이대를 고정하고 기울기 하나로 뺌.
    """
    pop = pd.read_csv(LAYERS, dtype={'adm_cd': str}).set_index('adm_cd').population_est
    inflow = np.log(sk.groupby('adm_cd').flow.sum() / pop).reindex(sk.adm_cd).to_numpy()
    assert not np.isnan(inflow).any(), '모든 동에 인구 추정값이 있어야 함'
    sk = sk.assign(inflow=inflow)
    out = pd.Series(index=sk.index, dtype=float)
    for _, g in sk.groupby('region'):
        cell = g.groupby(['sex', 'age'])
        r = g.weekend_weekday - cell.weekend_weekday.transform('mean')
        x = g.inflow - cell.inflow.transform('mean')
        resid = r - (r * x).sum() / (x * x).sum() * x
        z = resid / resid.groupby([g.sex, g.age]).transform('std')
        out[g.index] = z.map(NormalDist().cdf)
    return out, sk.inflow


def build():
    sk = pd.read_csv(OUT / 'sk_weekend_by_dong.csv', dtype={'adm_cd': str})
    sk['pct_adj'], sk['inflow'] = sk_adjusted(sk)
    m3 = pd.read_csv(OUT / 'm3_group_profiles.csv')
    m3 = m3.assign(
        sex=m3.sex.str[0],
        age=m3.age_floor.map({20: '20대', 30: '30대', 40: '40대', 50: '50대', 60: '60세 이상'}),
        out=m3[['weekday_move_seoul_peer_percentile', 'holiday_move_seoul_peer_percentile']].max(axis=1),
    )
    m3 = m3[
        [
            'dong',
            'sex',
            'age',
            'contact_seoul_peer_percentile',
            'weekday_move_seoul_peer_percentile',
            'holiday_move_seoul_peer_percentile',
            'out',
            'quality_warning',
        ]
    ]
    df = sk.merge(m3, on=['dong', 'sex', 'age'], how='left')
    assert (df[df.region == '강남'].contact_seoul_peer_percentile.notna()).all(), '강남 220칸이 M3와 모두 이어져야 함'
    rows = []
    for r in df.itertuples():
        t = trait(r.contact_seoul_peer_percentile, r.out, r.pct_adj)
        if not t:
            continue
        ev = []
        if pd.notna(r.contact_seoul_peer_percentile):
            ev.append(('M3', f'연락: 서울 같은 성별·나이대 중 {pos(r.contact_seoul_peer_percentile)}'))
            ev.append(
                (
                    'M3',
                    f'외출: 평일 {pos(r.weekday_move_seoul_peer_percentile)} · 휴일 {pos(r.holiday_move_seoul_peer_percentile)}',
                )
            )
        n = 22 if r.region == '강남' else 25
        ev.append(
            (
                'SK',
                f'주말에 사람이 평일의 {r.weekend_weekday * 100:.0f}% · 평일 유입을 감안하면 {r.region} {n}개 동 중 {pos(r.pct_adj)}',
            )
        )
        if (r.region, r.sex, r.age) in CARD:
            ev.append(('카드', CARD[(r.region, r.sex, r.age)]))
        sexw = '여성' if r.sex == '여' else '남성'
        agew = '60대 이상' if r.age == '60세 이상' else r.age
        rows.append(
            dict(
                id=f'{r.region}-{r.dong}-{r.sex}{r.age[:2]}',
                region=r.region,
                adm_cd=r.adm_cd,
                dong=r.dong,
                sex=r.sex,
                age_band=r.age,
                age=AGE[r.age],
                trait=t,
                title=f'{TITLE[t]} {agew} {sexw}',
                contact_pct=r.contact_seoul_peer_percentile,
                out_pct=r.out,
                sk_pct=r.pct_adj,
                sk_ratio=r.weekend_weekday,
                quality_warning=bool(r.quality_warning) if pd.notna(r.quality_warning) else False,
                evidence=' | '.join(f'{s}::{x}' for s, x in ev),
            )
        )
    out = pd.DataFrame(rows)
    assert out.id.is_unique
    assert trait(0.97, 0.01, 0.01) == '' and trait(0.5, 0.15, 0.5) == '외출 적음' and trait(0.5, 0.5, 0.5) == ''
    return out


if __name__ == '__main__':
    out = build()
    out.to_csv(OUT / 'dong_personas.csv', index=False, encoding='utf-8-sig')
    print(len(out), 'personas')
    print(out.groupby(['region', 'trait']).size().to_string())
    print(out.groupby('region').dong.nunique().to_string())
    print(out.groupby(['region', 'dong']).size().describe().round(1).to_string())
