"""강남·춘천 고립 지원사업 공백 분석: H1~H3 판정과 거시 분석.

입력: data/policy/policy_programs_final.csv (build_policy_programs_final.py 결과)
출력: data/policy/analysis/ 아래 표(csv), 그림(png), 판정 요약(json)

가상 주민은 조건 조합(지역 × 나이 × 성별 × 가구 × 소득 × 접근 방식 × 평일 낮 가능 여부)이다.
칸 수는 '조건 조합의 수'이지 사람 수가 아니다.

'열림'은 포트폴리오가 경로 있음(이용 가능 / 심사 필요 / 부가정보 미확인) 중 하나인 칸이다.
'기관 발굴로만 연결'과 '확인 필요만 남음'은 열림이 아니다.

    .analysis-venv/bin/python run_policy_gap_analysis.py
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import matplotlib
import matplotlib.ticker
import pandas as pd

import policy_gap_engine as e

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

ROOT = Path(__file__).resolve().parent
PROGRAMS = ROOT / 'data' / 'policy' / 'policy_programs_final.csv'
OUT = ROOT / 'data' / 'policy' / 'analysis'
FONT = ROOT / 'data' / 'reference' / 'NanumGothic-Regular.ttf'
REGIONS = ['강남', '춘천']

AGES = [22, 30, 38, 45, 52, 60, 64, 66, 72, 80]
AGE_BAND = {22: '청년', 30: '청년', 38: '청년', 45: '중장년', 52: '중장년', 60: '중장년', 64: '중장년',
            66: '노년', 72: '노년', 80: '노년'}
ATTRS = ['age', 'sex', 'household', 'income', 'access', 'weekday_day_ok']
ATTR_KO = {'age': '나이', 'sex': '성별', 'household': '가구', 'income': '소득', 'access': '접근 방식', 'weekday_day_ok': '평일 낮 참여'}


def personas() -> list[e.Persona]:
    grid = itertools.product(REGIONS, AGES, ['남', '여'], ['1인', '다인'], ['저소득', '일반'],
                             list(e.ACCESS), [True, False])
    return [e.Persona(region=r, age=a, sex=s, household=h, income=i, access=ac, weekday_day_ok=w)
            for r, a, s, h, i, ac, w in grid]


def load_programs() -> pd.DataFrame:
    g = pd.read_csv(PROGRAMS, encoding='utf-8-sig', dtype=str)
    for c in ('age_min', 'age_max'):
        g[c] = pd.to_numeric(g[c], errors='coerce')
    return g


def pair_groups(port: pd.DataFrame, attr: str):
    """조건 attr만 다르고 나머지 조건이 같은 주민 묶음."""
    others = ['region', 'function'] + [a for a in ATTRS if a != attr]
    return port.groupby(others)


# ---------- H1: 같은 지원 필요라도 주민 조건에 따라 경로가 달라지는가 ----------
def h1(port: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """판정 기준(분석 전 정함): 조건 하나만 다른 주민 묶음 안에서 같은 기능의 포트폴리오가
    '경로 있음'과 '공백(조건 충돌)'으로 갈리는 기능이 두 지역 모두 1개 이상이면 지지.
    보조(사후 분석): 열림(경로 있음)과 닫힘(그 밖)으로 갈리는 기능 수와 조건별 비율."""
    rows = []
    for attr in ATTRS:
        for _, grp in pair_groups(port, attr):
            r = grp.iloc[0]
            rows.append({'region': r.region, 'function': r.function, 'attr': attr,
                         'open_vs_conflict': grp.is_open.any() and (grp.portfolio == e.PORT_CONFLICT).any(),
                         'open_split': grp.is_open.nunique() > 1})
    f = pd.DataFrame(rows)
    fn = f.groupby(['region', 'function'])[['open_vs_conflict', 'open_split']].any().reset_index()

    def funcs(col):
        return {r: sorted(fn[(fn.region == r) & fn[col]].function) for r in REGIONS}

    main = funcs('open_vs_conflict')
    cnt = f[f.open_vs_conflict].groupby(['region', 'attr']).size().unstack(fill_value=0).rename(columns=ATTR_KO)
    share = f.groupby(['region', 'attr']).open_split.mean().unstack().rename(columns=ATTR_KO).round(3)
    supported = all(len(main[r]) >= 1 for r in REGIONS)
    return {'verdict': '지지' if supported else '지지하지 않음',
            'rule': '분석 전 정한 기준: 두 지역 모두에서, 조건 하나만 바꿨을 때 포트폴리오가 경로 있음과 공백(조건 충돌)으로 갈리는 기능이 1개 이상',
            'functions_open_vs_conflict': main,
            'groups_by_attr_open_vs_conflict': {r: cnt.loc[r].to_dict() for r in cnt.index},
            'supplementary_post_hoc': {'rule': '사후 보조 분석: 열림/닫힘으로 갈리는 기능(확인 필요 포함)',
                                       'functions_open_split': funcs('open_split'),
                                       'split_share_by_attr': share.to_dict('index')}}, f


# ---------- H2: 같은 기능의 대안까지 보면 판단이 달라지는가 ----------
def h2(port: pd.DataFrame) -> dict:
    out = {}
    hc = port[port.n_충돌 > 0]
    for r in REGIONS:
        a = hc[hc.region == r]
        loose = a[a.is_open]
        strict = a[a.n_이용_가능 > 0] if 'n_이용_가능' in a else a[a['n_이용 가능'] > 0]
        out[r] = {'cells_with_any_conflict': int(len(a)), 'open_with_alternative': int(len(loose)),
                  'share_open': round(len(loose) / len(a), 3) if len(a) else None,
                  'strict_alternative_usable': int(len(strict)),
                  'share_strict': round(len(strict) / len(a), 3) if len(a) else None}
    supported = all(out[r]['open_with_alternative'] > 0 for r in REGIONS)
    return {'verdict': '지지' if supported else '지지하지 않음',
            'rule': '사업 하나가 충돌인 칸 중 같은 기능의 다른 사업으로 열린 경로가 남는 칸이 두 지역 모두 1개 이상(분석 전 정함)',
            'note': '사업이 2개 이상인 기능이면 쉽게 충족되는 약한 기준이다. 엄격 기준(대안이 이용 가능)도 함께 보고한다.',
            'by_region': out}


# ---------- H3: 운영 조건을 바꾼다고 가정하면 공백이 달라지는가 ----------
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


def h3(ps, g, base_port) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    rows, trans = [], []
    b = base_port.set_index(['persona', 'function'])
    for name, sg in scenarios(g).items():
        _, port = e.evaluate(ps, sg)
        a = port.set_index(['persona', 'function'])
        m = pd.DataFrame({'region': b.region, 'before': b.portfolio, 'after': a.portfolio,
                          'open_before': b.is_open, 'open_after': a.is_open})
        for r in REGIONS:
            x = m[m.region == r]
            rows.append({'scenario': name, 'region': r,
                         'open_before': int(x.open_before.sum()), 'open_after': int(x.open_after.sum()),
                         'newly_open': int((~x.open_before & x.open_after).sum()),
                         'conflict_before': int((x.before == e.PORT_CONFLICT).sum()),
                         'conflict_after': int((x.after == e.PORT_CONFLICT).sum())})
        t = m[m.before != m.after].groupby(['region', 'before', 'after']).size().rename('n').reset_index()
        trans.append(t.assign(scenario=name))
    t = pd.DataFrame(rows)
    t['conflict_reduced'] = t.conflict_before - t.conflict_after
    real = t[~t.scenario.str.startswith('S6')]
    supported = (real.conflict_reduced > 0).any()
    return {'verdict': '지지' if supported else '지지하지 않음',
            'rule': '분석 전 정한 기준: 운영조건 변경(S1~S5) 중 하나 이상이 공백(조건 충돌) 칸 수를 줄임(정원·참여율·효과는 계산하지 않음)',
            'note': '새로 열린 칸(newly_open)은 사후 보조 분석. S6은 정보 공개 가정이라 판정에서 뺌.',
            'table': rows}, t, pd.concat(trans)


# ---------- 민감도·의존도 ----------
def sensitivity(paths: pd.DataFrame) -> pd.DataFrame:
    """미확인을 모두 충족으로(낙관) 또는 모두 충돌로(비관) 두었을 때 열린 칸 비율."""
    l1 = [c for c in paths.columns if c.startswith('l1_')]
    st = paths[l1]
    conflict = (st == e.CONFLICT).any(axis=1)
    unknown = (st == e.UNKNOWN).any(axis=1)
    outreach_only = paths.reason.str.contains('OUTREACH_ONLY', na=False)
    p = paths.assign(opt=~conflict & ~outreach_only, pes=~conflict & ~unknown & ~outreach_only,
                     base=paths.path.isin(e.OPEN_PATHS))
    long = p.assign(fn=p.functions.str.split(';')).explode('fn')
    cell = long.groupby(['region', 'persona', 'fn'])[['base', 'opt', 'pes']].any()
    total = len(set(paths.persona)) // len(REGIONS) * len(e.FUNCTIONS)
    out = cell.groupby('region').sum() / total
    return out.round(3).rename(columns={'base': '현재', 'opt': '낙관(미확인=충족)', 'pes': '비관(미확인=충돌)'}).reset_index()


def structure_sensitivity(ps, g: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    """보조기능을 모두 뺀 경우, 서울시 돌봄SOS(GN-32)를 뺀 경우의 기능별 열린 비율."""
    variants = {'현재': base}
    _, variants['보조기능 없음'] = e.evaluate(ps, g.assign(function_secondary=''))
    _, variants['GN-32 제외'] = e.evaluate(ps, g[g.id != 'GN-32'])
    out = [v.groupby(['region', 'function']).is_open.mean().rename(k) for k, v in variants.items()]
    return pd.concat(out, axis=1).round(3).reset_index()


def leave_one_out(port: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    """열린 경로가 사업 하나에만 기대는 칸 수(그 사업이 빠지면 닫힘)."""
    o = port[port.is_open].open_ids.str.split(',')
    single = o[o.str.len() == 1].str[0]
    t = single.value_counts().rename('sole_open_cells').reset_index().rename(columns={'open_ids': 'id', 'index': 'id'})
    t = t.merge(g[['id', 'region', 'program', 'provider', 'site_in_region']], on='id', how='left')
    # 같은 운영기관 묶음: 늘봄청소년(C01·C03·CC-16)
    nb = o.apply(lambda ids: set(ids) <= {'C01', 'CC-16'})
    extra = pd.DataFrame([{'id': 'C01+CC-16', 'sole_open_cells': int(nb.sum()), 'region': '춘천',
                           'program': '늘봄청소년 운영 사업(C01·CC-16)만으로 열린 칸(어느 한쪽 단독 포함)', 'provider': '자체·광역', 'site_in_region': 'Y'}])
    return pd.concat([t, extra], ignore_index=True)


# ---------- 거시 분석 ----------
def macro(g: pd.DataFrame, port: pd.DataFrame, ps) -> dict[str, pd.DataFrame]:
    m = {}
    m['M1_기능별_사업수'] = pd.crosstab([g.region, g.provider], g.function).reset_index()
    port = port.assign(age_band=port.age.map(AGE_BAND))
    t = port.groupby(['region', 'function', 'age_band']).portfolio.value_counts(normalize=True).unstack(fill_value=0)
    m['M2_연령대별_포트폴리오비율'] = t.reindex(columns=[c for c in e.PORT_ORDER if c in t.columns]).round(3).reset_index()
    life = []
    for r in REGIONS:
        for f in e.FUNCTIONS:
            sub = g[(g.region == r) & g.apply(lambda x: e.has_function(x, f), axis=1)]
            for age in range(19, 91):
                known = sub[sub.age_known == 'Y']
                ok = known[(known.age_min.isna() | (known.age_min <= age)) & (known.age_max.isna() | (known.age_max >= age))]
                life.append({'region': r, 'function': f, 'age': age,
                             'n_age_met_operating': int((ok.status_2026 == '운영중').sum()),
                             'n_age_met_not_closed': int((ok.status_2026 != '종료').sum()),
                             'n_age_unknown': int((sub.age_known != 'Y').sum()),
                             'age_unknown_ids': ','.join(sub[sub.age_known != 'Y'].id)})
    m['M3_생애주기_연령충족사업수'] = pd.DataFrame(life)
    local = g[g.provider == '자체']
    _, lp = e.evaluate(ps, local)
    cmp = pd.DataFrame({'전체': port.groupby('region').portfolio.value_counts(),
                        '자체 사업만': lp.groupby('region').portfolio.value_counts()}).fillna(0).astype(int)
    m['M4_광역의존도'] = cmp.reset_index()
    ch = g.assign(채널=g.apply(lambda x: '/'.join(c for c in ('online', 'phone', 'visit', 'app', 'outreach') if x[f'ch_{c}'] == 'Y') or '확인된 채널 없음', axis=1))
    m['M5_채널구조'] = ch.groupby(['region', '채널']).size().rename('n').reset_index()
    restrict = pd.DataFrame({
        'id': g.id, 'region': g.region, 'function': g.function,
        '가구한정': g.household_req.isin(['1인가구', '독거노인', '여성1인가구', '1인가구(다인 예외심사)', '독거노인(저소득 2인 예외)']),
        '저소득필수': g.income_req.isin(['저소득필수', '기초연금수준']),
        '지역한정': g.residence_scope.isin(['동한정', '단지한정', '배달가능지역']),
        '선정심사': g.screening.eq('있음'),
        '기기필요': g.device_req.isin(['스마트폰', '안드로이드']),
        '대상특성': ~g.target_req.isin(['없음', '미확인']),
    })
    restrict['조건수'] = restrict.iloc[:, 3:].sum(axis=1)
    m['M6_조건겹침'] = restrict
    chcols = ['ch_online', 'ch_phone', 'ch_visit', 'ch_app', 'ch_outreach']

    def gap(x):
        return pd.Series({'운영상태': x.status_2026.eq('미확인').mean(), '나이': x.age_known.ne('Y').mean(),
                          '가구': x.household_req.eq('미확인').mean(), '소득': x.income_req.eq('미확인').mean(),
                          '선정': x.screening.eq('미확인').mean(), '신청채널(칸 기준)': x[chcols].eq('미확인').to_numpy().mean(),
                          '기기': x.device_req.eq('미확인').mean(), '운영시간': x.schedule.eq('미확인').mean()})
    info = []
    for r in REGIONS:
        for scope, x in (('전체', g[g.region == r]), ('자체만', g[(g.region == r) & (g.provider == '자체')]),
                         ('광역·국가만', g[(g.region == r) & (g.provider != '자체')])):
            info.append(gap(x).rename(f'{r}·{scope}'))
    m['M7_정보공백'] = pd.DataFrame(info).T.round(3).reset_index().rename(columns={'index': '조건'})
    m['M8_운영상태'] = pd.crosstab(g.region, g.status_2026).reset_index()
    return m


# 엑셀 「시나리오_대조」 S01~S10을 엔진 입력으로 옮긴 사례(S02는 주민등록·생활권 구분이 엔진 속성에 없어 제외).
CASES = [
    ('S01', '강남 38세 1인가구, 대면 부담', e.Persona('강남', 38, '남', '1인', '일반', '대면·전화 부담(온라인만)'), ['관계 형성', '상담']),
    ('S03', '강남 52세 반지하 1인가구, 고립 고위험', e.Persona('강남', 52, '여', '1인', '저소득'), ['주거·안전', '상담']),
    ('S04', '강남 68세 1인가구(수서주공1단지 밖), 우울 위험', e.Persona('강남', 68, '여', '1인', '일반'), ['관계 형성', '상담']),
    ('S05', '춘천 38세 1인가구, 취업·교육 6개월 미참여, 관계 단절', e.Persona('춘천', 38, '남', '1인', '일반'), ['관계 형성', '일자리']),
    ('S06', '춘천 52세 1인가구, 소득 높음, 전화 부담', e.Persona('춘천', 52, '남', '1인', '일반', '대면·전화 부담(온라인만)'), ['관계 형성', '상담']),
    ('S07', '춘천 66세 저소득 독거, 스마트폰 없음', e.Persona('춘천', 66, '여', '1인', '저소득', '디지털 취약(방문·전화만)'), ['관계 형성', '발굴·안부', '돌봄']),
    ('S08', '춘천 46세 독거, 아이폰만 사용', e.Persona('춘천', 46, '남', '1인', '일반', '아이폰 사용'), ['발굴·안부']),
    ('S09', '춘천 48세 1인가구, 원거리 거주', e.Persona('춘천', 48, '남', '1인', '일반'), ['발굴·안부']),
    ('S10', '춘천 53세, 외로움 심하나 신체 돌봄 필요 없음', e.Persona('춘천', 53, '여', '1인', '일반'), ['관계 형성', '돌봄']),
]


def cases(g: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cid, desc, p, fns in CASES:
        paths, port = e.evaluate([p], g, fns)
        for f in fns:
            sub = paths[paths.functions.str.split(';').apply(lambda fs: f in fs)]
            pr = port[port.function == f].iloc[0]
            rows.append({'case': cid, 'desc': desc, 'function': f, 'portfolio': pr.portfolio,
                         'paths': ' | '.join(f'{r.id} {r.path}' + (f'({r.reason})' if r.reason else '') for r in sub.itertuples())})
    return pd.DataFrame(rows)


def figures(port, h3t, m, sens):
    font_manager.fontManager.addfont(str(FONT))
    plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(FONT)).get_name()
    plt.rcParams['axes.unicode_minus'] = False
    # 1. 기능별 포트폴리오 구성(지역별 가로 누적 막대)
    colors = {e.PORT_OK: '#1b5e20', e.PORT_SCREEN: '#66bb6a', e.PORT_INFO: '#c5e1a5', e.PORT_OUTREACH: '#90a4ae',
              e.PORT_UNKNOWN: '#e0e0e0', e.PORT_CONFLICT: '#ef6c00', e.PORT_NONE: '#b71c1c'}
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), sharey=True)
    for ax, r in zip(axes, REGIONS):
        t = port[port.region == r].groupby('function').portfolio.value_counts(normalize=True).unstack(fill_value=0)
        t = t.reindex(index=e.FUNCTIONS[::-1], columns=[c for c in e.PORT_ORDER], fill_value=0)
        left = 0
        for c in t.columns:
            ax.barh(t.index, t[c], left=left, color=colors[c], label=c, edgecolor='white', linewidth=1)
            left = left + t[c]
        ax.set_xlim(0, 1)
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        ax.set_title(f'{r}: 기능별 판정 구성(조건 조합 640개 기준)')
    axes[1].legend(loc='upper center', bbox_to_anchor=(-0.05, -0.08), ncol=4, frameon=False)
    fig.savefig(OUT / 'fig1_portfolio_mix.png', dpi=160, bbox_inches='tight')
    plt.close(fig)
    # 2. H3 시나리오별 새로 열린 칸
    fig, ax = plt.subplots(figsize=(8, 4))
    t = h3t.pivot(index='scenario', columns='region', values='newly_open')
    t.plot.barh(ax=ax, color=['#4C72B0', '#DD8452'], width=0.7)
    ax.set_xlabel('새로 열린 조합 수(닫힘 → 경로 있음)')
    ax.set_ylabel('')
    ax.set_title('운영 조건·정보 공개를 바꾼다고 가정했을 때 새로 열리는 경로')
    ax.legend(title='지역')
    fig.savefig(OUT / 'fig2_h3_scenarios.png', dpi=160, bbox_inches='tight')
    plt.close(fig)
    # 3. 정보 공백(자체/광역·국가 구분)
    t = m['M7_정보공백'].set_index('조건')
    fig, ax = plt.subplots(figsize=(8, 4.6))
    t.plot.barh(ax=ax, width=0.8, color=['#1f4e79', '#4C72B0', '#9fb9d9', '#8c3b0b', '#DD8452', '#f2c6a0'])
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel('공개 자료로 확인되지 않은 비율')
    ax.set_ylabel('')
    ax.set_title('조건별 정보 공백')
    ax.legend(title='지역·사업 범위', fontsize=8)
    fig.savefig(OUT / 'fig3_info_gap.png', dpi=160, bbox_inches='tight')
    plt.close(fig)
    # 4. 미확인 민감도
    fig, ax = plt.subplots(figsize=(7, 3.4))
    sens.set_index('region').T.plot.bar(ax=ax, color=['#4C72B0', '#DD8452'], rot=0)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_ylabel('경로가 열린 조합 비율')
    ax.set_title('미확인 정보를 어떻게 보느냐에 따른 범위')
    ax.legend(title='지역')
    fig.savefig(OUT / 'fig4_sensitivity.png', dpi=160, bbox_inches='tight')
    plt.close(fig)


def write_report(g, summary, m, sens, loo):
    """표와 보고서를 같은 실행에서 갱신한다. H1–H3 기준은 계산 함수 그대로 둔다."""
    def table(df):
        d = df.fillna('계산 불가').astype(str)
        clean = lambda v: v.replace('|', '／').replace('\n',' ')
        return '\n'.join(['| '+' | '.join(map(clean,d.columns))+' |',
            '| '+' | '.join(['---']*len(d.columns))+' |']+
            ['| '+' | '.join(map(clean,row))+' |' for row in d.itertuples(index=False,name=None)])

    def pct(v):
        return f'{v*100:.1f}%'

    origins = pd.crosstab(g.origin,g.region).reindex(columns=REGIONS,fill_value=0)
    origins = origins.reindex(['엑셀','신규(조사)','신규(전문가 리뷰)','신규(교차확인)'],fill_value=0)
    origins.index = ['엑셀 사업(중복 정리 후)','새로 찾은 사업','전문가 리뷰 추가','교차확인 추가']
    origins.loc['합계'] = origins.sum()
    h1r,h2r,h3r = summary['H1'],summary['H2'],summary['H3']
    h3t = pd.read_csv(OUT / 'h3_scenarios.csv')
    lines = ['# 강남·춘천 고립 지원사업 공백 분석 (2026-10-19, 공고 기준 최신본)', '',
      '## 0. 이 문서를 읽는 법', '',
      '직접 사용자는 지자체 사회적 고립 정책·복지 담당자다. 가상 주민은 담당자가 지원경로와 조건 변경을 점검할 시나리오다. 담당자는 사업 전체를 같은 기능으로 비교하여 공백 후보, 집중, 한 사업에 대한 의존을 확인할 수 있다. 실제 주민의 고립이나 서비스 성과를 추정하지 않는다.', '',
      '지역 2개×나이 10개×성별 2개×가구 2개×소득 2개×접근 방식 4개×평일 낮 참여 여부 2개로 총 1,280개 시나리오를 만들었다. 지역마다 640개이며, 7개 기능을 검토하므로 지역별 4,480칸이다. 표의 칸 수는 사람 수·수요·주민 비율이 아니다. 공백은 조사 범위에서 조건이 맞는 사업을 찾지 못했다는 뜻이다.', '',
      '주 분석은 사용자가 정한 “공고에 없으면 없는 것” 규칙을 적용한 policy_programs_final.csv다. 나이·소득·가구·선정·기기 미기재는 제한 없음, 신청채널 미기재는 그 채널 없음으로 처리한다. 나이가 말로만 있으면 사업표의 법령·조례 해석을 따른다. 모집종료와 운영 미확인은 현재 종료로 처리한다. 운영시간·세부 거주지역·대상 속성의 미확인은 남긴다. 미기재를 미확인으로 두는 엄격 표는 비교용이다. 두 규칙의 차이는 효능 보고서 E4에 제시한다.', '',
      '사업별 경로는 이용 가능, 심사 필요, 부가정보 미확인, 기관 발굴로만 연결, 확인 필요, 충돌로 구분한다. 같은 기능의 다른 사업까지 보아 이용 가능·심사 필요·부가정보 미확인 중 하나가 남으면 경로 있음이다. 기관 발굴로만 연결과 확인 필요는 열린 경로로 세지 않는다. 경로 있음이 실제 선정이나 이용을 보장하지 않는다.', '',
      '## 1. 분석에 넣은 사업', '', table(origins.rename_axis('구분').reset_index()), '']
    for r in REGIONS:
        counts = g[g.region.eq(r)].provider.value_counts()
        lines += [f"{r}의 자체·광역·국가 사업은 각각 {counts.get('자체',0)}개·{counts.get('광역',0)}개·{counts.get('국가',0)}개다.", '']
    lines += ['기존 49개 사업에 GN-06·GN-07·GN-12·GN-13·GN-14를 추가하여 54개 사업이다. 최초 후보 58개의 판정 기록은 candidate_decisions.csv에 남아 있으며, 후속 교차확인은 crosscheck_x1–x4.csv에 따로 있다. C03은 C01의 사업명과 겹쳐 합쳤다. 신규 사업은 지역 주민 이용 경로, 고립 목적·대상, 독립 경로, 운영 근거, 일반 복지·일회성 행사 제외라는 기존 기준을 따랐다.', '',
      '## 2. 필수 판정: 가설 H1–H3 (분석 전에 정한 기준)', '',
      '| 가설 | 판정 | 분석 전에 정한 판정 기준 | 결과 |',
      '|---|---|---|---|',
      f"| H1 같은 지원이 필요해도 주민 조건에 따라 이용할 수 있는 경로가 달라진다 | {h1r['verdict']} | 두 지역 모두에서, 조건 하나만 바꿨을 때 경로 있음과 공백(조건 충돌)으로 갈리는 기능이 1개 이상 | 강남 {len(h1r['functions_open_vs_conflict']['강남'])}개, 춘천 {len(h1r['functions_open_vs_conflict']['춘천'])}개 기능 |",
      f"| H2 같은 기능의 대안까지 보면 사업 하나만 볼 때와 판단이 달라진다 | {h2r['verdict']} | 사업 하나가 충돌인 칸 중 다른 사업으로 열린 경로가 남는 칸이 두 지역 모두 1개 이상 | 강남 {pct(h2r['by_region']['강남']['share_open'])}, 춘천 {pct(h2r['by_region']['춘천']['share_open'])} |",
      f"| H3 운영 조건을 바꾼다고 가정하면 공백이 달라진다 | {h3r['verdict']} | 운영조건 변경 S1–S5 중 하나 이상이 공백(조건 충돌) 칸 수를 줄임 | 강남 S3, 춘천 S1·S2·S3·S5에서 감소 |", '',
      '세 가설의 판정기준은 바꾸지 않았다. 최소 한 기능 또는 한 칸만 달라도 지지되는 기준이므로 변화의 크기를 함께 읽어야 한다.', '', '**H1 해석**', '']
    for r in REGIONS:
        lines += [f"{r}에서 경로 있음과 조건 충돌 공백으로 갈리는 기능은 {', '.join(h1r['functions_open_vs_conflict'][r])}이다. 조건 하나만 다른 비교 묶음 중 갈린 묶음은 "+', '.join(f'{k} {v}개' for k,v in h1r['groups_by_attr_open_vs_conflict'][r].items())+'다.', '']
    lines += ['**H2 해석**', '']
    for r in REGIONS:
        h = h2r['by_region'][r]
        lines += [f"{r}은 하나 이상 충돌 사업이 있는 시나리오×기능 {h['cells_with_any_conflict']:,}칸 중 대안이 남는 경우가 {h['open_with_alternative']:,}칸이다. 대안이 이용 가능인 경우만 세면 {h['strict_alternative_usable']:,}칸으로 {pct(h['share_strict'])}다. 효능 지표 E3은 시나리오×사업이 단위이므로 이 H2 비율과 다르다.", '']
    lines += ['**H3 해석**', '']
    for r in REGIONS:
        changes = h3t[h3t.region.eq(r) & ~h3t.scenario.str.startswith('S6') & h3t.conflict_reduced.gt(0)]
        lines += [f"{r}의 조건 충돌 공백은 "+'; '.join(f"{x.scenario.split()[0]}에서 {x.conflict_before:,}→{x.conflict_after:,}칸({x.conflict_reduced:,}칸 감소)" for x in changes.itertuples())+'다.', '']
    lines += ['### 2-1. 사후 보조 분석 (판정에 쓰지 않음)', '',
      '아래는 결과를 본 뒤 추가한 보조 분석이다. 판정에는 쓰지 않았다. 기준 변경 과정은 판정기준_변경기록.md를 따른다.', '',
      '**H1 보조: “열림/닫힘”으로 넓혀 본 경우.** 확인 필요와 기관 발굴로만 연결도 닫힘에 포함한다.', '']
    aux = h1r['supplementary_post_hoc']
    for r in REGIONS:
        lines += [f"{r}에서 열림과 닫힘이 갈리는 기능은 {len(aux['functions_open_split'][r])}개로, {', '.join(aux['functions_open_split'][r])}이다.", '']
    split = pd.DataFrame(aux['split_share_by_attr']).map(pct).rename_axis('조건').reset_index()
    lines += [table(split), '', '위 비율의 분모는 해당 조건만 다른 비교 묶음 수다. 인구 비율이 아니다.', '',
      '**H3 보조: “새로 열린 칸”으로 본 경우.** 새로 열린 칸에는 확인 필요 또는 기관 발굴만 가능에서 열린 경로로 바뀐 칸도 포함한다. 공백 감소 칸과 구분한다.', '',
      table(h3t[['scenario','region','newly_open','conflict_reduced']].rename(columns={'scenario':'가정한 변경','region':'지역','newly_open':'새로 열린 칸','conflict_reduced':'충돌 공백 감소 칸'})), '',
      'S2에서는 춘천 236칸이 새로 열린다. 현재 표에는 CC-04 등 평일 주간 조건도 반영되어 있어 CC-21 한 사업에서만 발생한 변화라고 해석하지 않는다. S3의 1인가구 요건 완화는 법·조례와 사업 목적의 검토가 필요하다. S4는 현재의 저소득 필수 조건만 우선순위로 바꾸는 가정이며 다른 제약이 남아 열림이 늘지 않는다. S6은 주 분석에서 나이·소득 미기재를 이미 제한 없음으로 처리하므로 추가 변화가 없다. 원문에서 제한 없음을 확인했다는 뜻은 아니다.', '',
      '## 3. 공백을 넓게 본 인사이트', '', '### 3-1. 기능별, 연령대별로 열린 경로의 비율', '']
    bands = m['M2_연령대별_포트폴리오비율'].copy()
    open_cols = [c for c in bands.columns if c in e.PORT_OPEN]
    bands['열린 비율'] = bands[open_cols].sum(axis=1).map(pct)
    lines += [table(bands[['region','function','age_band','열린 비율']].rename(columns={'region':'지역','function':'기능','age_band':'연령대'})), '',
      '각 비율은 해당 지역·기능·연령대의 시나리오 중 열린 칸의 비율이다. 실제 주민의 비율이 아니다. 일자리는 두 지역 모두 현재 회차가 종료되어 열린 칸이 없다. 강남 청년·중장년 관계 형성을 모두 확인 필요라고 했던 이전 설명은 공고 기준 표에서 더 이상 맞지 않는다. 춘천에도 이용 가능 480칸이 있으므로 전부 심사 경로라고 할 수 없다.', '',
      '### 3-2. 생애주기: 나이에 따라 지원 형태가 바뀐다', '',
      '아래는 다른 조건을 판정하기 전, 숫자 나이 조건이 맞고 운영 중인 사업의 개수다. 무조건 이용 가능한 사업 수와 다르다.', '']
    life = m['M3_생애주기_연령충족사업수']
    selected = life[life.age.isin([39,40,64,65])][['region','function','age','n_age_met_operating']]
    lines += [table(selected.rename(columns={'region':'지역','function':'기능','age':'나이(세)','n_age_met_operating':'나이 충족 운영 사업 수'})), '',
      '춘천 64세 이하의 고독사 예방과 65세 이상 노인맞춤돌봄은 대상 선정과 제도 근거가 다르다. 담당자는 나이 전환에서 같은 기능의 대안이 실제로 이어지는지 확인할 수 있다. 나이 제한 미기재를 제한 없음으로 처리한 사업도 포함되어 있으므로 공식 무제한 확인과 구분한다.', '',
      '### 3-3. 정보 공백', '', table(m['M7_정보공백']), '',
      '표의 값은 해당 범위 사업 중 미확인 입력의 비율(0–1)이다. 신청채널은 채널 칸 전체가 분모다. 나이·소득 등 미확인이 0인 이유는 주 분석의 공고 미기재 처리 규칙이다. 원문 충실도가 100%라는 뜻은 아니다. 엄격 표와의 차이는 E4에서 비교한다. 남아 있는 운영시간 정보는 담당자가 별도로 확인할 항목이다.', '',
      table(m['M4_광역의존도'].rename(columns={'region':'지역','portfolio':'같은 기능 전체 판정','전체':'전체 사업 칸 수','자체 사업만':'자체 사업만 남긴 칸 수'})), '',
      '자체 사업만 보았을 때 경로가 줄어드는 정도는 광역·국가 사업을 담당자의 통합 검토에 포함할 필요를 보여 준다.', '',
      table(sens.rename(columns={'region':'지역'})), '',
      '민감도 표는 모든 시나리오×기능 중 열린 칸의 비율(0–1)이다. 남아 있는 미확인 요건을 모두 충족 또는 모두 충돌로 바꾼 계산이다. 지역별 단순 순위를 정하기 위한 지표가 아니다.', '',
      '### 3-4. 1인가구 요건', '']
    restrict = m['M6_조건겹침']
    for r in REGIONS:
        sub = restrict[restrict.region.eq(r)]
        n = int(sub['가구한정'].sum())
        lines += [f"{r}은 {len(sub)}개 중 {n}개 사업({pct(n/len(sub))})에 1인가구·독거노인·여성 1인가구 또는 다인가구 예외심사 요건이 있다.", '']
    lines += ['동행서비스와 응급안전의 다인가구 예외는 심사로 처리한다. 노인맞춤돌봄은 가구 형태 무관으로 본다. 담당자는 가구 형태 외에 실질적 돌봄 공백을 예외 조건으로 둘 수 있는지 검토할 수 있다.', '',
      '### 3-5. 한 사업에 의존하는 경로', '',
      '사업 하나를 제외하면 닫히는 시나리오×기능 칸의 수다. 마지막의 C01+CC-16은 같은 운영기관에 묶인 경로를 함께 제외한 별도 참고 행이다. 개별 사업 수와 합산하지 않는다.', '',
      table(loo[['region','id','program','sole_open_cells']].rename(columns={'region':'지역','id':'사업 ID','program':'사업','sole_open_cells':'제외 시 닫히는 칸'})), '',
      '강남 돌봄SOS는 504칸, 춘천 일상돌봄은 936칸, 춘천 노인맞춤돌봄은 588칸에 단독 의존이 남아 있다. 담당자는 대체 공급자를 협의하거나 중단 시 대응을 마련할 수 있다. C01·CC-16의 같은 운영기관에만 의존하는 칸은 36칸이다.', '',
      '### 3-6. 광역 사업의 위치와 신청 방식', '',
      '서울잇다플레이스는 성동구, 강남 배정 청년기지개 권역센터는 송파구다. 서울마음편의점과 서울연결처방은 강남 소재 프로그램 공간이 확인되지 않는다. 이동형 운영이나 강남 접수 창구를 실제 상설 이용 장소와 구분해야 한다. 이 엔진은 거리를 자격 판정에 사용하지 않는다. 별도의 추가 분석은 대면 장소의 직선거리와 누락을 제시한다. 발굴형 경로는 주민이 직접 신청하는 경로와 구분한다.', '',
      '### 3-7. 운영 안정성', '', table(m['M8_운영상태'].rename(columns={'region':'지역'})), '',
      '단위는 사업 개수다. 공고 기준에서 종료에는 현재 모집이 끝난 회차와 운영 근거 미확인도 포함된다. 따라서 사업 자체가 영구 폐지됐다는 뜻이 아니다. 추가 분석의 연도별 지속성과 구분한다.', '',
      '### 3-8. 결과가 일부 사업의 코딩에 얼마나 기대는가(구조 민감도)', '',
      table(pd.read_csv(OUT / 'M12_구조민감도.csv').rename(columns={'region':'지역','function':'기능'})), '',
      '표는 각 지역·기능별 열린 비율(0–1)이다. 강남 돌봄은 돌봄SOS를 제외하면 100%에서 30%로 줄지만, 의료 접근은 현재 다른 대안으로 100%를 유지한다. 춘천 상담은 보조기능을 빼면 100%에서 13.8%로 줄어든다. 담당자는 전담 기능과 다른 사업의 부가 서비스에 기대는 기능을 구분할 수 있다.', '',
      '## 4. 판정을 막는 정보', '']
    unknown = pd.read_csv(OUT / 'unknown_reasons.csv').rename(columns={'reason':'미확인 원인','n_paths':'시나리오×사업 경로 수'})
    unknown['미확인 원인'] = unknown['미확인 원인'].replace({'time:TIME_UNVERIFIED':'참여 가능한 운영시간 확인 필요',
        'residence:SERVICE_AREA_UNVERIFIED':'동·단지·배달 지역의 세부 주소 확인 필요','target:TARGET_ATTR_UNKNOWN':'주거취약·외출 어려움 등 대상 속성 확인 필요'})
    lines += [table(unknown), '',
      '한 경로에 여러 원인이 붙을 수 있다. 담당자는 주민 조건 시나리오에 더 필요한 속성과 공고에 더 필요한 정보를 구분할 수 있다. 나이·소득 미기재는 공고 기준 표에서 미확인으로 남지 않으므로, 위 표만 보고 공고 정보가 완전하다고 해석하지 않는다.', '',
      '## 5. 전문가 리뷰 반영 내역', '',
      '기존 리뷰에 따라 경로 상태 구분, 시간 미확인의 처리, 대상 속성의 확인 필요, 신청채널의 또는 조건, 다인가구 예외, 보조기능, C01·C03 중복을 반영했다. 이후 사용자의 공고 기준 규칙과 교차확인 5개 사업을 적용한 현재 표를 기준으로 보고서 수치를 갱신했다. 미기재를 엄격하게 처리한 표는 비교용으로 남긴다. H1–H3는 분석 전에 정한 기준을 유지했다.', '',
      '## 6. 한계', '',
      '공개 자료를 조사한 54개 사업이며 전수 조사가 아니다. 가상 시나리오의 수는 실제 사람 수·수요·유병률이 아니다. 주민 주소와 장애 여부 등은 단순화했다. 정원·대기·선정률·기관의 실제 운영을 모두 확인하지 못했다. 공고에 조건이 없다는 것과 실제로 조건이 없다는 것은 다르다. 보조기능 분류에 결과가 의존한다. 두 지역은 조사 사업 수와 제공 방식이 달라 단순 순위 비교에 적합하지 않다. 조건 변경은 계산 가정이며 법령·예산·현장 실현 가능성이나 고립 감소 효과를 증명하지 않는다.', '',
      '## 7. 파일', '',
      '`data/policy/policy_programs_final.csv`는 주 분석 54개 사업 표이고 `policy_programs_strict.csv`는 비교용이다. `data/policy/research/`에는 출처·인용·대조 결과가 있다. `data/policy/analysis/`에는 summary.json, paths.csv, portfolio.csv, h1_pair_groups.csv, h3_scenarios.csv, h3_transitions.csv, M1–M12 표, 그림과 판정기준_변경기록.md가 있다. `data/policy/efficacy/효능지표_보고서.md`는 담당자 검토 지표이고 `data/policy/extra/추가분석_보고서.md`는 사후 추가 분석이다. 계산 코드는 policy_gap_engine.py, run_policy_gap_analysis.py, run_efficacy_indicators.py, run_policy_extra_analyses.py다.', '']
    (OUT / '공백분석_보고서.md').write_text('\n'.join(lines),encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    g = load_programs()
    ps = personas()
    paths, port = e.evaluate(ps, g)
    paths.to_csv(OUT / 'paths.csv', index=False, encoding='utf-8-sig')
    port.to_csv(OUT / 'portfolio.csv', index=False, encoding='utf-8-sig')
    r1, h1rows = h1(port)
    h1rows.to_csv(OUT / 'h1_pair_groups.csv', index=False, encoding='utf-8-sig')
    r2 = h2(port)
    r3, h3t, h3trans = h3(ps, g, port)
    h3t.to_csv(OUT / 'h3_scenarios.csv', index=False, encoding='utf-8-sig')
    h3trans.to_csv(OUT / 'h3_transitions.csv', index=False, encoding='utf-8-sig')
    m = macro(g, port, ps)
    for k, v in m.items():
        v.to_csv(OUT / f'{k}.csv', index=False, encoding='utf-8-sig')
    sens = sensitivity(paths)
    sens.to_csv(OUT / 'M10_미확인민감도.csv', index=False, encoding='utf-8-sig')
    structure_sensitivity(ps, g, port).to_csv(OUT / 'M12_구조민감도.csv', index=False, encoding='utf-8-sig')
    loo = leave_one_out(port, g)
    loo.to_csv(OUT / 'M11_단일사업의존.csv', index=False, encoding='utf-8-sig')
    cases(g).to_csv(OUT / 'M9_시나리오사례.csv', index=False, encoding='utf-8-sig')
    # 확인 필요 경로를 막는 원인 코드(단위: 주민×사업 경로 수, 한 경로에 원인이 여럿일 수 있음)
    unk = paths[paths.path == e.PATH_UNKNOWN].reason.str.split(';').explode().value_counts()
    unk.rename_axis('reason').rename('n_paths').reset_index().to_csv(OUT / 'unknown_reasons.csv', index=False, encoding='utf-8-sig')
    summary = {'n_programs': g.groupby('region').size().to_dict(), 'n_personas': len(ps),
               'portfolio_counts': port.groupby('region').portfolio.value_counts().unstack(fill_value=0).to_dict('index'),
               'H1': r1, 'H2': r2, 'H3': r3}
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=int), encoding='utf-8')
    figures(port, h3t, m, sens)
    write_report(g, summary, m, sens, loo)
    print(json.dumps({k: summary[k] for k in ('n_programs', 'portfolio_counts')}, ensure_ascii=False, indent=1))
    for h in ('H1', 'H2', 'H3'):
        print(h, summary[h]['verdict'])


if __name__ == '__main__':
    main()
