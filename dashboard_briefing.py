"""확정 기획의 집단별 정책 점검과 검토용 서식. 개인 위험 판단은 하지 않음."""
from pathlib import Path
import pandas as pd
import policy_gap_engine as e

AGE_BANDS=['20대','30대','40대','50대','60세 이상']
REASON_NAMES={'CLOSED':'모집 종료 또는 계속 운영 미확인','AGE_OUT_OF_RANGE':'나이 범위 밖',
              'HOUSEHOLD':'가구 요건','HOUSEHOLD_EXCEPTION':'가구 예외 심사',
              'INCOME':'소득 요건','TARGET':'사업 대상 요건','CHANNEL':'이용 가능한 신청 방법 없음',
              'DEVICE':'필요 기기 요건','TIME':'평일 낮만 운영'}


def load_briefing_sources(policy:Path):
    return {name:pd.read_csv(policy/path).fillna('') for name,path in {
        'weights':'weighted/weights.csv','portfolio':'analysis/portfolio.csv','paths':'analysis/paths.csv',
        'operators':'efficacy/E6_지역별.csv','dependency':'analysis/M12_구조민감도.csv'}.items()}


def group_table(data,region):
    if region=='강남':
        result=[]
        for g in data['cells'].to_dict('records'):
            result.append(dict(sex=g['sex'],age_band=g['age_band'],function=g['function'],
                open_share=float(g['open_share']),conflict_share=float(g['conflict_share']),
                agency_share=float(g['기관 발굴로만 연결']),unknown_share=float(g['확인 필요만 남음']),
                reasons=[g[f'conflict_reason_{i}'] for i in range(1,4) if g[f'conflict_reason_{i}']],
                notice='강남 전체 성·연령별 추정 비율이며 동마다 같은 값임. 동별 주민 수로 합산하지 않음.'))
        return result
    source=data['briefing_sources'];weights=source['weights'];weights=weights[(weights.variant=='main')&(weights.region==region)]
    port=source['portfolio'];port=port[port.region==region].merge(weights[['persona','region','weight']],on=['persona','region'],validate='many_to_one')
    port['age_band']=port.age.map(lambda age:'60세 이상' if age>=60 else f'{max(20,age//10*10)}대')
    paths=source['paths'];paths=paths[(paths.region==region)&(paths.path=='충돌')].merge(weights[['persona','region','weight']],on=['persona','region'],validate='many_to_one')
    paths['age_band']=paths.age.map(lambda age:'60세 이상' if age>=60 else f'{max(20,age//10*10)}대')
    paths=paths.assign(function=paths.functions.str.split(';'),code=paths.reason.str.split(';')).explode('function').explode('code')
    paths['code']=paths.code.str.split(':').str[-1]
    paths['reason_name']=paths.code.map(REASON_NAMES).fillna('부가 조건 확인 필요')
    ranked={key:grp.groupby('reason_name').weight.sum().sort_values(ascending=False).head(3).index.tolist() for key,grp in paths.groupby(['sex','age_band','function'])}
    result=[]
    for (sex,band,function),grp in port.groupby(['sex','age_band','function'],sort=False):
        total=grp.weight.sum()
        def share(states):return float(grp.loc[grp.portfolio.isin(states),'weight'].sum()/total) if total else 0.
        result.append(dict(sex=sex,age_band=band,function=function,open_share=share(e.PORT_OPEN),
            conflict_share=share(['공백(조건 충돌)','공백(해당 기능 사업 없음)']),agency_share=share(['기관 발굴로만 연결']),
            unknown_share=share(['확인 필요만 남음']),reasons=ranked.get((sex,band,function),[]),
            notice='성·연령별 조건에 해당하는 주민 수를 반영한 추정 비율임. 실제 고립·지원 필요 인원이 아님.'))
    return result


def policy_briefing(data,region):
    if region not in ['강남','춘천']:raise ValueError('지역 값을 확인해 주세요.')
    indicators=data['indicators'];current=indicators[(indicators.region==region)&(indicators.variant=='main')]
    def metric(indicator,detail):
        rows=current[(current.indicator==indicator)&current.detail.str.contains(detail,regex=False)]
        return float(rows.iloc[0].value) if len(rows) else None
    def sources(function):
        ids=[p['id'] for p in data['programs'].to_dict('records') if p['region']==region and e.has_function(p,function)]
        return list(dict.fromkeys(url for pid in ids for url in data['sources'][pid]))[:4]
    def issue(identifier,title,function,value,explanation,kind,change=None):
        return dict(id=identifier,title=title,function=function,value=value,explanation=explanation,
                    category=kind,change=change,sources=sources(function))
    groups=group_table(data,region)
    issues=[issue('housing','주거·안전에서 막힌 조건','주거·안전',metric('portfolio','주거·안전 / 공백(조건 충돌)'),
                  '가구·나이·신청 방법 등 사업 요건이 겹쳐 남는 경로가 없는 조건입니다. 강남의 주요 이유는 1인가구 대상 요건입니다.' if region=='강남' else '조사 범위의 주거·안전 사업 요건이 겹쳐 남는 경로가 없는 조건입니다.','정책 공백','S3'),
            issue('employment','올해 신청할 일자리 회차 없음','일자리',metric('portfolio','일자리 / 공백(조건 충돌)'),
                  '조사본에서 모집 종료 또는 계속 운영 미확인으로 처리했습니다. 사업이 영구 폐지됐다는 뜻은 아닙니다.','정책 공백'),
            issue('information','공고 정보가 부족한 경로','관계 형성',metric('portfolio','관계 형성 / 확인 필요만 남음'),
                  '운영시간 등 추가 확인이 필요해 판정을 확정하지 못한 조건입니다. 조건 충돌과 구분합니다.','정보 부족','S2'),
            issue('catalog','공식 목록 하나에서 놓치는 사업','관계 형성',metric('E2','평균 누락 비율'),
                  '열린 경로가 있는 주민 조건에서 공식 목록 하나에 없는 사업의 비율을 평균한 사후 보조 분석입니다.','공식 목록 범위')]
    if region=='강남':
        dep=data['briefing_sources']['dependency'];r=dep[(dep.region==region)&(dep.function=='돌봄')].iloc[0]
        issues.append(issue('dependency','돌봄SOS 한 사업에 기대는 구조','돌봄',float(r['현재'])-float(r['GN-32 제외']),
                            f"기존 조건별 분석에서 돌봄 경로 있음이 {float(r['현재']):.0%}에서 돌봄SOS 제외 시 {float(r['GN-32 제외']):.0%}로 줄었습니다. 주민 수를 반영한 비율과는 다른 계산입니다.",'단일 사업 의존'))
    operators=data['briefing_sources']['operators'];operators=operators[operators.region==region]
    return dict(region=region,signal_basis='policy_gap',group_count=220 if region=='강남' else 10,
        checked_cells=(220 if region=='강남' else 10)*7,groups=groups,issues=issues,
        age_bands=AGE_BANDS,functions=e.FUNCTIONS,persona_slots=[None]*5,recommendation_order_ready=False,priority_ready=False,
        m3_ready=False,llm={'connected':False,'message':'대시보드 모델 호출 미연결. 현재 문장과 초안은 규칙·서식 기반이며 LLM 생성 결과가 아닙니다.'},
        metrics=dict(alternative_share=metric('E3','대안이 남는 비율'),information_sites=metric('E1','평균 안내 도메인 수'),
                     operator_count=int(operators.iloc[0].n_operators),catalog_missing_share=metric('E2','평균 누락 비율')),
        scenarios=[dict(change=code,title=title,value=metric('E7',code+' '),
                        basis='변경 전 지역 주민 추정 수 × 7개 분야가 분모인 사후 보조 분석. 같은 주민이 여러 분야에 반복될 수 있음.')
                   for code,title in [('S3','1인가구 요건 완화'),('S2','저녁·주말 회차 추가')]],
        notice='정책 요건으로 막힌 조건을 찾는 점검입니다. 개인의 고립 위험을 판정하지 않습니다. 비율은 해당 조건의 추정 주민 비율이며 실제 지원 필요 인원이 아닙니다.',
        group_notice='강남의 동별 표시는 지역 전체 성·연령별 정책 비율을 연결한 것입니다. 동별 차이나 우선순위를 뜻하지 않습니다.' if region=='강남' else '춘천은 성별·나이대별 정책 조건을 점검합니다. M3 연락·외출 자료는 강남만 대상입니다.')


def review_draft(data,payload,diagnose_fn=None):
    if not isinstance(payload,dict):raise ValueError('초안 입력을 확인해 주세요.')
    kinds={'guidance':'주민 안내문','referral':'기관 연결 요청문','improvement':'정책 보완안','cooperation':'부서 협조 요청문'}
    if payload.get('kind') not in kinds:raise ValueError('초안 종류를 확인해 주세요.')
    if set(payload)=={'region','kind','issue_id'}:
        report=policy_briefing(data,payload['region']);issue=next((i for i in report['issues'] if i['id']==payload['issue_id']),None)
        if not issue:raise ValueError('보고 항목을 확인해 주세요.')
        ratio='확인 필요' if issue['value'] is None else f"{issue['value']*100:.1f}%"
        sources=issue['sources'];paragraphs=[f"{report['region']} {kinds[payload['kind']]} — {issue['title']}",
            f"검토 근거: {issue['function']} · {ratio}. {issue['explanation']}",
            '비율은 분석 조건에 해당하는 추정 주민 비율입니다. 실제 지원 필요 인원이나 사업 효과를 뜻하지 않습니다.',
            '요청 초안: 담당 부서에서 대상 요건·운영시간·모집 상태의 현재 근거를 확인하고, 조건 보완 가능성과 부서 간 대안을 함께 검토해 주시기 바랍니다.',
            '확인 필요: 담당 부서, 회신 기한, 예산과 운영 가능성. 담당자 검토 후 확정합니다.']
    elif set(payload)=={'kind','conditions','program_id'} and payload['kind'] in ['guidance','referral'] and diagnose_fn is not None:
        result=diagnose_fn(data,payload['conditions'])
        program=next((p for p in result['programs'] if p['id']==payload['program_id']),None)
        if program is None:raise ValueError('현재 조건의 사업을 골라 주세요.')
        condition=payload['conditions'];sources=program['sources']
        paragraphs=[f"{kinds[payload['kind']]} — {program['program']}",
            f"검토 조건: {condition['region']} · {condition['age']}세 · {condition['sex']} · {condition['household']}가구. 공고 기준 판정: {program['path']}. 이 판정만으로 실제 선정을 확정할 수 없습니다.",
            '확인 요청: 현재 모집 여부와 정원, 대상 요건, 참여 가능한 시간, 신청 방법을 기관에 확인해 주시기 바랍니다.' if payload['kind']=='referral' else '안내 초안: 아래 공고를 참고해 신청 가능 여부를 기관에 확인해 주세요. 심사와 추가 확인이 남은 조건은 확정 이용과 구분합니다.',
            f"담당 기관: {program['operator'] or program['provider']}. 공개 자료에 없는 담당자·연락처·회신 기한은 확인 필요입니다."]
    else:raise ValueError('초안의 지역·보고 항목을 확인해 주세요.')
    citation='\n'.join(sources)
    text='\n\n'.join(f'{p}\n근거: {citation}' for p in paragraphs)
    return dict(title=kinds[payload['kind']],text=text,sources=sources,generation='template',requires_review=True,
                notice='규칙·서식 기반 검토 초안입니다. LLM 생성·외부 발송·정책 변경을 수행하지 않았습니다.')
