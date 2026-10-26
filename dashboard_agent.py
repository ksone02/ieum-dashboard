"""지도 대시보드용 에이전트 결과: 대표 페르소나 5명과 동별 페르소나를 엔진·추천 순서로 판정하고 담당자에게 보일 판단을 만듦.

자격 판정은 policy_gap_engine 그대로임. 이 모듈은 결과를 묶어 "막힘 / 방식 안 맞음 / 확인 필요 / 연결 가능"으로 나누고,
조건을 바꿨을 때 열리는 사업을 다시 계산함. 문장은 정해진 양식에 엔진 결과를 채운 것임(LLM 아님).
"""
from dataclasses import replace

import pandas as pd

import policy_gap_engine as e
import run_persona_recommend as rr

OPEN = {e.PATH_OK, e.PATH_SCREEN, e.PATH_INFO}
MODE_FUNCTION = '관계 형성'  # 방식이 맞는지는 사람을 만나게 하는 분야에서만 따짐

META = {
    'P1': dict(dong='개포2동', title='밖에는 나가는데 연락은 적은 20대', evidence=[
        ('M3', '연락: 서울 20대 여성 중 하위 2%'), ('M3', '평일 외출: 상위 10%')]),
    'P2': dict(dong='논현1동', title='연락은 많은데 밖에 잘 안 나가는 30대', evidence=[
        ('M3', '연락: 서울 30대 여성 중 상위 3%'), ('M3', '평일 외출: 하위 1%')]),
    'P3': dict(dong=None, title='가족과 살지만 사람 만날 일이 적은 40대', evidence=[
        ('카드', '사람 만나는 곳(식당·카페·술집) 소비 비중이 앞뒤 나이대보다 약 20% 낮아요')]),
    'P4': dict(dong=None, title='머무는 곳이 주말에 한산한 20대', evidence=[
        ('SK', '주말에 사람이 평일의 115% · 춘천 성별·나이대 10개 집단 중 가장 낮아요 (춘천 평균 124%)')]),
    'P5': dict(dong=None, title='혼자 끼니를 해결하는 70대', evidence=[
        ('카드', '편의점·패스트푸드 소비 비중이 같은 나이 여성의 1.4~1.6배예요')]),
}

# 페르소나 조건을 바꾸는 것 = 사업 쪽 조건을 바꾸는 것. 담당자에게는 사업 쪽 말로 보여 줌.
CHANGES = [
    ('weekday_day_ok', False, True, '저녁·주말 회차를 만들면'),
    ('household', '다인', '1인', '1인가구 요건을 풀면'),
]


SHORT = {'CLOSED': '모집 기간', 'AGE_OUT_OF_RANGE': '나이', 'HOUSEHOLD': '1인가구 요건', 'INCOME': '저소득 요건',
         'TARGET': '대상 요건', 'CHANNEL': '신청 방법', 'TIME': '평일 낮 운영', 'DEVICE': '필요한 기기', 'RESIDENCE': '거주지 요건',
         'OUTSIDE_AREA': '대상 동이 아님', 'OTHER_REGION': '다른 지역 사업'}


def _is(word):
    """받침에 맞춰 '이에요/예요'를 붙임."""
    c = word[-1]
    return word + ('이에요' if '가' <= c <= '힣' and (ord(c) - 0xAC00) % 28 else '예요')


def _reason(code, names):
    item, _, key = code.partition(':')
    # 영문 코드가 화면에 그대로 나가지 않게: 모르는 코드는 조건 항목 이름(예: 세부 거주지역)으로 보여 줌
    return SHORT.get(key) or names.get(key) or names.get(item) or '기타 조건'


def _open_by_function(rows):
    return {f: set(rows[rows.functions.str.split(';').apply(lambda fs: f in fs) & rows.path.isin(OPEN)].id)
            for f in e.FUNCTIONS}


# 위험 단계: 고립 쪽 신호가 먼저, 같은 신호 안에서는 지원 공백이 있는 쪽이 먼저. 우리가 정한 규칙이며 고립 확률이 아님.
# 2026-10-26 첫 규칙(공백 우선)에서 바꿈: 신호가 강해도 갈 곳이 있으면 3단계로 밀려서 신호가 단계에 거의 반영되지 않았음.
LOW, VERY_LOW, HIGH = 0.2, 0.05, 0.8
# 대표 사례의 신호 위치(연락·외출 예측, 서울 같은 성별·나이대 중 위치). 소비 패턴·주말 사람 흐름의 집단 경향만 있는 사례는 '보통'으로 둠.
REP_SIGNAL = {'P1': dict(contact=0.025, out=0.898), 'P2': dict(contact=0.970, out=0.0075)}
LEVEL_NAME = {1: '긴급', 2: '높음', 3: '주의', 4: '관찰'}
ACTIONS = {
    1: ['먼저 찾아가서 상황을 확인해요', '맞는 사업이 없으니 정책 추천에서 새 사업이나 조건 바꾸기를 검토해요'],
    2: ['갈 수 있는 사업을 바로 안내하고 연결해요', '연결한 뒤 다음 점검 때 신호가 나아졌는지 확인해요'],
    3: ['정책 추천에서 막힌 조건을 바꿀 수 있는지 검토해요', '공고에 빠진 정보는 운영 기관에 보완을 요청해요'],
    4: ['지금은 갈 수 있는 사업이 있어요', '다음 점검 때 신호가 더 낮아졌는지 다시 확인해요'],
}
LEVEL_RULE = ('신호 강함 = 하위 20%인 특성이 2개 이상이거나 하나라도 하위 5% (연락이 상위 20%면 강함으로 보지 않음). '
              '1 긴급: 신호 강함 + 지원 공백 / 2 높음: 신호 강함 + 갈 곳 있음 / 3 주의: 신호 보통 + 지원 공백 / 4 관찰: 신호 보통 + 갈 곳 있음. '
              '지원 공백 = 갈 곳 없음·방식 다름·확인 필요 중 하나라도 있음 (모집 종료만은 빼요)')


SOURCE_NAME = {'M3': '연락·외출 예측', 'SK': '주말 사람 흐름', '카드': '소비 패턴'}


def _actions(p):
    """단계별 할 일에 실제 사업 이름을 넣음."""
    first = lambda fn: next((x for f in p['fields'] if f['function'] == fn and f['status'] != 'blocked'
                             for x in f['programs']), None)
    # 대상 조건이 확인되지 않은 사업은 그대로 권하지 않고 확인할 일을 붙임
    check = lambda x: (' · 지역 안에는 지점이 없어요' if x.get('away') else '') + {'조건부(심사)': ' · 대상인지는 신청할 때 심사해요'}.get(x['path'], '' if x['path'] == '이용 가능' else ' · 대상 조건을 운영 기관에 확인해요')
    acts = list(ACTIONS[p['level']])
    gap = next((f['kind'] for f in p['findings'] if f['kind'] != 'closed'), None)
    if p['level'] == 1:  # 공백 종류에 맞춰 두 번째 할 일을 씀
        acts[1] = {'blocked': '갈 수 있는 사업이 없으니 정책 추천에서 새 사업이나 조건 바꾸기를 검토해요',
                   'mismatch': '맞는 방식의 사업이 없으니 정책 추천에서 새 사업을 검토해요',
                   'unknown': '공고에 빠진 정보를 운영 기관에 확인해서 갈 수 있는지 판단해요'}.get(gap, acts[1])
    if p['level'] == 1 and first('발굴·안부'):
        x = first('발굴·안부')
        acts[0] = f"「{x['name']}」로 먼저 안부와 상황을 확인해요{check(x)}"
    if p['level'] == 2:
        fits = list({x['name']: x for f in p['fields'] if f['status'] == 'open' for x in f['programs'] if x['fits']}.values())
        if fits:
            acts[0] = f"「{fits[0]['name']}」부터 안내하고 연결해요{check(fits[0])}"
            if len(fits) > 1:
                acts.insert(1, f"안 맞으면 「{fits[1]['name']}」도 있어요{check(fits[1])}")
    return acts


def signals():
    """페르소나 id → 신호 위치(0에 가까울수록 고립 쪽). 없는 항목은 빠짐."""
    out = {k: v for k, v in REP_SIGNAL.items()}
    dong = pd.read_csv(rr.OUT / 'dong_personas.csv')
    for r in dong.itertuples():
        out[r.id] = {k: v for k, v in (('contact', r.contact_pct), ('out', r.out_pct), ('sk', r.sk_pct)) if pd.notna(v)}
    return out


# 주말 사람 흐름이 다른 이유로 낮을 수 있는 동(지도에서 확인)
CAUTION = {'교동': '한림대가 있는 동이라 주말에 한산한 건 대학가 영향일 수 있어요',
           '효자2동': '강원대가 있는 동이라 주말에 한산한 건 대학가 영향일 수 있어요'}


def counted_lows(sig):
    """고립 쪽으로 세는 신호. 주말 사람 흐름은 동 전체 값이라 외출이 상위 50%인 집단에는 세지 않음."""
    return {k: v for k, v in sig.items() if v <= LOW and not (k == 'sk' and sig.get('out', 0) >= 0.5)}


def level_of(sig, findings):
    lows = counted_lows(sig)
    personal = sorted(v for k, v in lows.items() if k != 'sk')
    # 연락이 상위 20%면 고립 쪽 신호를 강하게 보지 않음. 동 전체 값(주말 사람 흐름)만으로는 강함이 되지 않음
    strong = sig.get('contact', 0) < HIGH and bool(personal) and (len(lows) >= 2 or personal[0] <= VERY_LOW)
    kinds = [f['kind'] for f in findings if f['kind'] != 'closed']
    gap = 'blocked' if 'blocked' in kinds else 'partial' if kinds else 'open'
    level = (1 if gap != 'open' else 2) if strong else (3 if gap != 'open' else 4)
    return level, bool(strong), gap


def persona_specs():
    """(id, 종류, 제목, 특성, 근거, Persona) 목록. 대표 5명 + 동별 페르소나(run_dong_personas.py 결과)."""
    specs = [(code, 'rep', META[code]['title'], trait, META[code]['evidence'], persona)
             for code, _, trait, persona in rr.PERSONAS]
    dong = pd.read_csv(rr.OUT / 'dong_personas.csv', dtype={'adm_cd': str})
    for r in dong.itertuples():
        # 동별 페르소나의 가정: 혼자 살고, 60세 미만은 평일 낮에 일해서 못 감. 가정은 화면에 그대로 보여 줌.
        persona = e.Persona(r.region, int(r.age), r.sex, '1인', '일반', '일반(모든 채널 가능)',
                            r.age_band == '60세 이상', dong=r.dong)
        evidence = [tuple(x.split('::', 1)) for x in r.evidence.split(' | ')]
        specs.append((r.id, 'dong', r.title, r.trait, evidence, persona))
    return specs


def build_agent(data, reason_names):
    programs = rr.load_programs_with_area()
    sites = data['sites']
    centers = data['centers'].set_index('dong')
    specs = persona_specs()
    ranked = rr.recommend([(c, t, tr, p) for c, _, t, tr, _, p in specs])
    rows, port = e.evaluate([s[-1] for s in specs], programs)
    names = dict(zip(programs.id, programs.program))
    site_in = dict(zip(programs.id, programs.site_in_region))  # N: 지역 안에 시설이 없음
    urls = data['sources']
    out = []
    for i, (code, kind, title, trait, evidence, persona) in enumerate(specs):
        dong_name = persona.dong or None
        prow, pport = rows[rows.persona == i], port[port.persona == i]
        first_mode = rr.RULES[trait][0]
        # 조건을 바꿔 다시 판정
        simulations = []
        before = _open_by_function(prow)
        for field, old, new, text in CHANGES:
            if getattr(persona, field) != old:
                continue
            alt, _ = e.evaluate([replace(persona, **{field: new})], programs)
            after = _open_by_function(alt)
            gained = {f: sorted(after[f] - before[f]) for f in e.FUNCTIONS if after[f] - before[f]}
            simulations.append(dict(change=text, opened={f: [dict(id=x, name=names[x]) for x in ids] for f, ids in gained.items()}))
        fields, findings = [], []
        for _, pf in pport.iterrows():
            f = pf.function
            rec = ranked[(ranked.persona == code) & (ranked.function == f)].sort_values('rank')
            blocked = prow[(prow.path == e.PATH_CONFLICT) & prow.functions.str.split(';').apply(lambda fs: f in fs)]
            reasons = pd.Series([_reason(c, reason_names) for r in blocked.reason for c in r.split(';')]).value_counts()
            opens_if = [dict(change=s['change'], programs=s['opened'][f]) for s in simulations if f in s['opened']]
            if pf.portfolio in (e.PORT_CONFLICT, e.PORT_NONE):
                status = 'blocked'
            elif pf.portfolio in (e.PORT_UNKNOWN, e.PORT_OUTREACH):
                status = 'unknown'
            elif f == MODE_FUNCTION and not (rec.delivery == first_mode).any():
                status = 'mismatch'
            else:
                status = 'open'
            items = []
            for _, r in rec.iterrows():
                s = sites[sites.id == r.id]
                items.append(dict(rank=int(r['rank']), id=r.id, name=r.program, delivery=r.delivery, delivery_sure=r.sure,
                                  path=r.path, schedule=r.schedule, fits=r.delivery == first_mode, source=(urls.get(r.id) or [''])[0],
                                  away=r.delivery == '나가서 만남' and site_in.get(r.id) == 'N',
                                  sites=[dict(lat=float(x.latitude), lng=float(x.longitude), place=str(x.display_name).split(',')[0],
                                              outside=bool(x.outside_region)) for _, x in s.iterrows()]))
            fields.append(dict(function=f, status=status, portfolio=pf.portfolio, total=int(pf.n_programs),
                               programs=items, reasons=[dict(reason=k, count=int(v)) for k, v in reasons.head(3).items()],
                               blocked=[dict(name=names[x], reasons=[_reason(c, reason_names) for c in r.split(';')],
                                             sites=[dict(lat=float(s.latitude), lng=float(s.longitude), place=str(s.display_name).split(',')[0],
                                                         outside=bool(s.outside_region)) for _, s in sites[sites.id == x].iterrows()])
                                        for x, r in zip(blocked.id, blocked.reason)],
                               opens_if=opens_if))
            top = reasons.index[0] if len(reasons) else ''
            if status == 'blocked':
                closed = len(blocked) > 0 and all('CLOSED' in r for r in blocked.reason)  # 모든 사업이 모집 종료
                fix = f"{opens_if[0]['change']} {len(opens_if[0]['programs'])}개가 열려요" if opens_if else (
                    '다음 모집이 열리면 신청할 수 있어요' if closed else '조건이 맞는 새 지원을 만들어야 해요')
                findings.append(dict(kind='closed' if closed and not opens_if else 'blocked', function=f, title=f'{f} 사업에 갈 수 없어요' if not closed else f'{f} 모집이 끝났어요',
                                     why=('올해 신청 기간이 지났어요' if closed else f'가장 많이 걸리는 조건은 {_is(top)}') if top else '이 분야 사업이 아직 없어요', action=fix))
            elif status == 'mismatch':
                findings.append(dict(kind='mismatch', function=f, title=f'{f} 사업은 있지만 방식이 맞지 않아요',
                                     why=f'이 사람에게는 「{first_mode}」 방식이 먼저 맞는데, 갈 수 있는 {len(rec)}개는 {"모두 " if len(rec) > 1 else ""}다른 방식이에요',
                                     action=f'「{first_mode}」 {f} 사업이 생기면 바로 연결할 수 있어요'))
            elif status == 'unknown':
                fix = f" {opens_if[0]['change']} {len(opens_if[0]['programs'])}개가 열려요" if opens_if else ''
                findings.append(dict(kind='unknown', function=f, title=f'{f} 사업은 공고를 더 확인해야 해요',
                                     why='공고에 운영 시간이 적혀 있지 않아서 이 사람이 갈 수 있는지 판단하기 어려워요',
                                     action=f'공고에 운영 시간을 적어 달라고 요청할 수 있어요.{fix}'))
        center = centers.loc[dong_name] if dong_name in centers.index else None
        out.append(dict(id=code, kind=kind, region=persona.region, dong=dong_name, title=title, age_band=persona.age,
                        trait=trait, mode_order=rr.RULES[trait], evidence=[dict(source=SOURCE_NAME.get(s, s), text=t) for s, t in evidence]
                        + ([dict(source='주의', text=CAUTION[dong_name])] if kind == "dong" and dong_name in CAUTION else []),
                        assumptions=[f'{persona.age}세 {persona.sex}성', '혼자 살아요' if persona.household == '1인' else '가족과 같이 살아요',
                                     '평일 낮에 갈 수 있어요' if persona.weekday_day_ok else '평일 낮에는 못 가요',
                                     '방문·전화로만 신청해요' if persona.access.startswith('디지털') else '앱·온라인도 쓸 수 있어요'],
                        location=None if center is None else dict(lat=float(center.latitude), lng=float(center.longitude)),
                        fields=fields, findings=findings))
    order = {'blocked': 0, 'mismatch': 1, 'unknown': 2, 'closed': 3}
    sig_all = signals()
    names_sig = {'contact': '연락', 'out': '외출', 'sk': '주말 사람 흐름'}
    n_programs = programs.region.value_counts().to_dict()
    for p in out:
        p['findings'].sort(key=lambda x: order[x['kind']])
        sig = sig_all.get(p['id'], {})
        p['level'], strong, gap = level_of(sig, p['findings'])
        p['level_name'] = LEVEL_NAME[p['level']]
        counted = counted_lows(sig)
        lows = [f"{names_sig[k]} 하위 {max(v * 100, 1):.0f}%" for k, v in counted.items()]
        srcs = '·'.join(dict.fromkeys(e['source'] for e in p['evidence']))
        sig_text = (', '.join(lows) if lows else '하위 20% 안에 드는 신호가 없어요' if sig else f'{srcs}의 성별·나이대 경향만 있어요') + f" → 신호 {'강함' if strong else '보통'}"
        if 'sk' in sig and sig['sk'] <= LOW and 'sk' not in counted:
            note = f"주말 사람 흐름 하위 {max(sig['sk'] * 100, 1):.0f}%는 이 집단이 외출을 많이 해서 세지 않았어요"
            sig_text = f'{note} → 신호 보통' if not lows else sig_text + f' ({note})'
        elif list(counted) == ['sk']:
            sig_text += ' (주말 사람 흐름은 동 전체 값이라 이것만으로는 강함으로 보지 않아요)'
        if lows and sig.get('contact', 0) >= HIGH:
            sig_text += f" (연락이 상위 {max((1 - sig['contact']) * 100, 1):.0f}%라 강함으로 보지 않아요)"
        top = next((f for f in p['findings'] if f['kind'] != 'closed'), None)
        ended = [f['function'] for f in p['findings'] if f['kind'] == 'closed']
        n_gap = sum(f['kind'] != 'closed' for f in p['findings'])
        gap_text = (top['title'] + (f' · 다른 분야 {n_gap - 1}개도 공백이에요' if n_gap > 1 else '') if top else
                    f"{', '.join(ended)} 분야는 올해 모집이 끝났고, 나머지 분야는 갈 수 있는 사업이 있어요" if ended
                    else '모든 분야에 갈 수 있는 사업이 있어요')
        p['level_why'] = dict(signal=sig_text, gap=gap_text)
        p['fits_field'] = next((f['function'] for f in p['fields'] if f['status'] == 'open' for x in f['programs'] if x['fits']), None)
        p['actions'] = _actions(p)
        by_change = {}
        for f in p['fields']:
            for o in f['opens_if']:
                by_change.setdefault(o['change'], {'new': [], 'more': []})['more' if f['status'] == 'open' else 'new'].append(f['function'])
        opened = [c + ' ' + ', '.join(filter(None, [', '.join(d['new']) + ' 분야가 새로 열려요' if d['new'] else '',
                                                     ', '.join(d['more']) + ' 분야는 갈 곳이 더 늘어나요' if d['more'] else '']))
                  for c, d in by_change.items()]
        p['trace'] = [
            f"{p['region']} 사업 {n_programs.get(p['region'], 0)}개의 신청 조건을 모았어요",
            '이 사람의 조건(나이·성별·가구·소득·평일 낮·신청 방법' + ('·사는 동' if p['dong'] else '') + ')으로 사업마다 신청할 수 있는지 하나씩 확인했어요',
            f'고립 쪽 신호를 봤어요: {sig_text}',
            f'지원 공백을 찾았어요: {gap_text}',
            '조건을 바꾸면 갈 수 있는지 다시 따져 봤어요: ' + (' / '.join(opened) if opened else '바꿔도 새로 열리는 사업이 없어요'),
            f"{p['level']}단계({p['level_name']})로 정했어요",
        ]
        kinds = [f['kind'] for f in p['findings']]
        p['severity'] = next((tone for k, tone in (('blocked', 'bad'), ('mismatch', 'warn'), ('unknown', 'muted')) if k in kinds), 'ok')  # 지원 공백만 본 상태
    regions = {}
    sk = pd.read_csv(rr.OUT / 'sk_weekend_by_dong.csv')  # 살펴본 동 × 성별 × 나이대 집단
    for r in ('강남', '춘천'):
        ps = [p for p in out if p['region'] == r]
        dongs = {}
        for p in ps:
            if p['kind'] != 'dong':
                continue
            d = dongs.setdefault(p['dong'], dict(dong=p['dong'], location=p['location'], personas=[], counts={k: 0 for k in order}))
            d['personas'].append(p['id'])
            for f in p['findings']:
                d['counts'][f['kind']] += 1
        for d in dongs.values():
            sev = [next(x for x in ps if x['id'] == i)['severity'] for i in d['personas']]
            d['severity'] = next((s for s in ('bad', 'warn', 'muted') if s in sev), 'ok')
            d['level'] = min(next(x for x in ps if x['id'] == i)['level'] for i in d['personas'])
            d['gaps'] = max(sum(f['kind'] != 'closed' for f in next(x for x in ps if x['id'] == i)['findings']) for i in d['personas'])
            d['levels'] = {lv: sum(next(x for x in ps if x['id'] == i)['level'] == lv for i in d['personas']) for lv in (1, 2, 3, 4)}
        narrow = None
        for lv in (1, 2):  # 같은 단계 사람들에게 맞는 사업이 모두 같으면, 추천이 아니라 공급이 좁다는 발견으로 보여 줌
            grp = [p for p in ps if p['level'] == lv]
            fits = [tuple(dict.fromkeys(x['name'] for f in p['fields'] if f['status'] == 'open' for x in f['programs']
                                        if x['fits'] and f['function'] == p['fits_field'])) for p in grp if p.get('fits_field')]
            if len(grp) >= 3 and len(fits) == len(grp) and len(set(fits)) == 1:
                narrow = dict(level=lv, count=len(grp), function=grp[0]['fits_field'], programs=list(fits[0]))
                break
        scan = dict(groups=int((sk.region == r).sum()), found=sum(p['kind'] == 'dong' for p in ps),
                    programs=int(n_programs.get(r, 0)))
        regions[r] = dict(geojson=data['maps'][r]['geojson'], scan=scan, narrow=narrow, personas=[p['id'] for p in ps if p['kind'] == 'rep'],
                          dongs=sorted(dongs.values(), key=lambda d: (d['level'], -d['levels'][d['level']], -d['gaps'], -len(d['personas']))),  # 가장 높은 단계 인원이 많은 동, 다음은 공백 분야가 많은 동
                          dong_personas=sum(len(d['personas']) for d in dongs.values()),
                          levels={lv: sum(p['level'] == lv for p in ps) for lv in (1, 2, 3, 4)},
                          counts={k: sum(f['kind'] == k for p in ps if p['kind'] == 'rep' for f in p['findings']) for k in order},
                          dong_counts={k: sum(f['kind'] == k for p in ps if p['kind'] == 'dong' for f in p['findings']) for k in order})
    assert sum(p['kind'] == 'rep' for p in out) == 5 and all(p['fields'] for p in out)
    return dict(personas=out, regions=regions, functions=e.FUNCTIONS, checked_at='2026-10-26',
                level_rule=LEVEL_RULE,
                notice='모두 가상 인물이에요. 실제 주민 수나 고립된 사람 수를 뜻하지 않아요. 사업 공고에 적힌 조건으로 판정했어요.',
                rule='동별 페르소나: 동 × 성별 × 나이대 집단 중 연락·외출 예측(서울 같은 성별·나이대 대비)과 주말 사람 흐름(평일 유입을 감안해 같은 지역 동끼리 비교)에서 하나라도 하위 20%인 곳. 연락이 상위 20%면 빼요')


def summary(agent):
    """지도·목록용 가벼운 목록. 상세는 persona_detail로 따로 받음."""
    keep = ('id', 'kind', 'region', 'dong', 'title', 'trait', 'location', 'severity', 'age_band', 'level', 'level_name')
    return dict(regions=agent['regions'], functions=agent['functions'], notice=agent['notice'], rule=agent['rule'],
                checked_at=agent['checked_at'], level_rule=agent['level_rule'],
                personas=[{**{k: p[k] for k in keep},
                           'findings': [dict(kind=f['kind'], function=f['function'], title=f['title']) for f in p['findings']]}
                          for p in agent['personas']])


def persona_detail(agent, pid):
    hit = next((p for p in agent['personas'] if p['id'] == pid), None)
    if hit is None:
        raise ValueError('페르소나를 찾지 못했어요.')
    return hit
