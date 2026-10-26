"""정책 추천: 페르소나 전체를 놓고 무엇을 바꾸면 몇 명에게 길이 열리는지 계산함.

세 종류로 나눔.
- condition: 사업 하나의 조건을 바꿨을 때(기존 H3 변환 규칙을 그 사업에만 적용) 새로 열리는 페르소나·분야
- new: 조건을 바꿔도 안 열리거나, 열려도 방식이 안 맞는 공백. 다른 지역 사례(벤치마크)를 근거로 붙임
- notice: 공고에 운영 시간이 없어서 판정이 막힌 사업
숫자는 가상 페르소나 수이며 실제 주민 수가 아님. 판정 기준은 엔진 그대로임.
"""
from collections import Counter

import pandas as pd

import policy_gap_engine as e
import run_persona_recommend as rr
from dashboard_agent import persona_specs
from run_policy_gap_analysis import scenarios

# 기존 H3 변환 이름 → 담당자가 할 일로 바꾼 말
ACTIONS = {'S1 온라인·전화 신청 추가': '온라인·전화로도 신청받기', 'S2 저녁·주말 회차 추가': '저녁·주말 회차 열기',
           'S3 1인가구 요건 완화': '1인가구 요건 풀기', 'S4 소득 요건 완화': '소득 요건 풀기',
           'S5 64세 상한을 69세로': '나이 상한을 69세로 올리기'}
BENCH = rr.OUT.parent / 'extra/벤치마크_형태차이.csv'
# 다른 지역 사례의 제공 방식 글자로 서비스 방식을 맞춤
MODE_WORDS = {'전화·온라인': ('전화', 'AI', '온라인', '비대면'), '나가서 만남': ('대면', '집단', '모임'), '집으로 찾아옴': ('방문', '가정', '집에서', '청소')}


def _people(ids, spec_by_id, kinds):
    """페르소나 id 목록 → 동별 수(지도용, 동별 페르소나만 셈 — 동 배지 숫자와 맞춤)와 전체 목록."""
    dongs = Counter(spec_by_id[i].dong for i in ids if kinds[i] == 'dong')
    return dict(count=len(ids), personas=sorted(ids), dongs=dict(dongs.most_common()))


def build_policy(agent, sources):
    specs = persona_specs()
    spec_by_id = {s[0]: s[-1] for s in specs}
    kinds = {s[0]: s[1] for s in specs}
    programs = rr.load_programs_with_area()
    names = dict(zip(programs.id, programs.program))
    detail = {p['id']: p for p in agent['personas']}
    bench = pd.read_csv(BENCH)
    out = {}
    for region in ('강남', '춘천'):
        rs = [s for s in specs if s[-1].region == region]
        ps, ids = [s[-1] for s in rs], [s[0] for s in rs]
        progs = programs[programs.region == region].reset_index(drop=True)
        rows, base = e.evaluate(ps, progs)
        before = base.set_index(['persona', 'function']).is_open
        recs = []

        # 1) 조건 바꾸기: 변환 규칙을 사업 하나에만 적용
        whole = {}
        for scen, changed_all in scenarios(progs).items():
            if scen not in ACTIONS:
                continue
            diff = (changed_all.astype(str) != progs.astype(str)).any(axis=1)
            _, port_all = e.evaluate(ps, changed_all)
            gained_all = (~before) & port_all.set_index(['persona', 'function']).is_open
            whole[ACTIONS[scen]] = int(gained_all.groupby(level=0).any().sum())
            for idx in progs.index[diff]:
                one = progs.copy()
                one.loc[idx] = changed_all.loc[idx]
                _, port = e.evaluate(ps, one)
                gained = (~before) & port.set_index(['persona', 'function']).is_open
                hit = gained[gained]
                if hit.empty:
                    continue
                who = sorted({ids[i] for i, _ in hit.index})
                funcs = sorted({f for _, f in hit.index})
                pid = progs.loc[idx, 'id']
                recs.append(dict(kind='condition', id=f'{region}-{pid}-{scen[:2]}', program_id=pid, program=names[pid],
                                 action=ACTIONS[scen], functions=funcs,
                                 title=f'{names[pid]} · {ACTIONS[scen]}',
                                 why=f'{", ".join(funcs)} 분야에서 페르소나 {len(who)}명이 새로 갈 수 있어요',
                                 source=(sources.get(pid) or [''])[0], **_people(who, spec_by_id, kinds)))

        # 2) 새 사업이 필요한 곳: 방식이 안 맞거나, 조건을 바꿔도 안 열리는 분야
        gaps = {}
        for pid in ids:
            for f in detail[pid]['fields']:
                fd = next((x for x in detail[pid]['findings'] if x['function'] == f['function']), None)
                if f['status'] == 'mismatch':
                    key = (f['function'], detail[pid]['mode_order'][0])
                elif f['status'] == 'blocked' and not f['opens_if'] and not (fd and fd['kind'] == 'closed'):
                    key = (f['function'], '')
                else:
                    continue
                gaps.setdefault(key, []).append(pid)
        for (func, mode), who in gaps.items():
            mine = bench[bench.review_region == region]
            ex = (mine[mine.channel_form.str.contains('|'.join(MODE_WORDS[mode])) | mine.time_form.str.contains('집에서')]
                  if mode else mine[mine.function == func])
            if mode == '나가서 만남':
                ex = ex[~ex.channel_form.str.contains('|'.join(MODE_WORDS['집으로 찾아옴'] + ('AI',)))]
            recs.append(dict(kind='new', id=f'{region}-new-{func}-{mode}', function=func, mode=mode, functions=[func],
                             title=f'「{mode}」 {func} 사업 만들기' if mode else f'{func} 사업 새로 만들기',
                             why=(f'갈 수 있는 {func} 사업이 모두 다른 방식이라 맞는 곳이 없어요' if mode
                                  else f'지금 조건으로는 갈 수 있는 {func} 사업이 없고, 조건을 바꿔도 열리지 않아요'),
                             examples=[dict(region=r.region, program=r.program, form=r.channel_form, time=r.time_form,
                                            url=r.source_url, checked=r.verification) for r in ex.itertuples()],
                             **_people(who, spec_by_id, kinds)))

        # 3) 공고 보완: 운영 시간이 없어서 판정이 막힌 사업
        unk = rows[rows.path.eq(e.PATH_UNKNOWN) & rows.reason.str.contains('TIME_UNVERIFIED')]
        for pid, g in unk.groupby('id'):
            # 그 분야에서 아직 갈 곳이 없는 사람만 셈(다른 사업으로 이미 열린 사람은 공고가 바뀌어도 달라지지 않음)
            who = sorted({ids[i] for i, fs in zip(g.persona, g.functions)
                          if any(not before.get((i, f), True) for f in fs.split(';'))})
            if not who:
                continue
            recs.append(dict(kind='notice', id=f'{region}-notice-{pid}', program_id=pid, program=names[pid],
                             functions=sorted(set(';'.join(g.functions).split(';'))),
                             title=f'{names[pid]} · 공고에 운영 시간 적기',
                             why=f'운영 시간이 공고에 없어서, 평일 낮에 못 가는 페르소나 {len(who)}명이 갈 수 있는지 판단할 수 없어요',
                             source=(sources.get(pid) or [''])[0], **_people(who, spec_by_id, kinds)))

        # 4) 모집이 끝난 분야: 조건 문제가 아니라 회차가 없음
        ended = {}
        for pid in ids:
            for fd in detail[pid]['findings']:
                if fd['kind'] == 'closed':
                    ended.setdefault(fd['function'], []).append(pid)
        for func, who in ended.items():
            recs.append(dict(kind='round', id=f'{region}-round-{func}', functions=[func], title=f'{func} 사업 · 다음 모집 열기',
                             why=f'올해 모집이 끝나서 페르소나 {len(who)}명 모두 지금은 신청할 수 없어요', **_people(who, spec_by_id, kinds)))

        # 지역 페르소나 전원에게 해당하는 모집 종료는 추천이 아니라 안내로 따로 뺌(누구에게나 같은 말이라 변별력이 없음)
        ended = [r['functions'][0] for r in recs if r['kind'] == 'round' and r['count'] == len(ids)]
        recs = [r for r in recs if not (r['kind'] == 'round' and r['count'] == len(ids))]
        order = {'condition': 0, 'new': 1, 'notice': 2, 'round': 3}
        recs.sort(key=lambda r: (order[r['kind']] == 3, -r['count'], order[r['kind']]))  # 모집 회차는 맨 뒤
        out[region] = dict(recs=recs, whole=whole, personas=len(ids), ended=ended)
    assert out['강남']['recs'] and out['춘천']['recs']
    return out
