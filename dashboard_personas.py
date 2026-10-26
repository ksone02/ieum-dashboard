"""사용자가 작성한 페르소나 초안을 정책 엔진의 7개 분야와 연결함."""
from pathlib import Path
import policy_gap_engine as e

SOURCE='페르소나_5개_초안.md'
DRAFTS=[
    dict(id='P1',region='강남',dong='개포2동',age_band='20대',age=25,sex='여',household='1인',weekday_day_ok=False,
         title='외출은 하지만 연락은 적은 청년',observed=['같은 성·연령 대비 연락이 적고 평일 외출이 많은 편'],evidence='M3 초안에 기재된 개포2동 비교 · 원본 대조 대기',default_function='관계 형성'),
    dict(id='P2',region='강남',dong='논현1동',age_band='30대',age=35,sex='여',household='1인',weekday_day_ok=True,
         title='연락은 하지만 외출은 적은 청년',observed=['같은 성·연령 대비 연락이 많고 평일 외출이 적은 편'],evidence='M3 초안에 기재된 논현1동 비교 · 원본 대조 대기',default_function='관계 형성'),
    dict(id='P3',region='강남',dong=None,age_band='40대',age=45,sex='남',household='다인',weekday_day_ok=False,
         title='가족과 살며 낮에는 참여하기 어려운 중년',observed=['40대 남성 집단의 대인접촉 업종 소비 비중이 낮은 경향'],evidence='카드 연구의 성·연령별 경향 · 동네 단위 관측이 아님',default_function='주거·안전'),
    dict(id='P4',region='춘천',dong=None,age_band='50대',age=55,sex='여',household='1인',weekday_day_ok=False,
         title='평일 낮에는 참여하기 어려운 중년',observed=['춘천 일부 상업지역에서 저녁 체류가 많은 경향'],evidence='지역 단위 SK 연구 · 이 가상 인물의 외출 관측이 아님',default_function='관계 형성'),
    dict(id='P5',region='춘천',dong=None,age_band='70대',age=75,sex='남',household='1인',weekday_day_ok=True,
         title='스마트폰 없이 방문·전화로 연결할 어르신',observed=['노년 남성 집단에서 편의점·패스트푸드 소비 비중이 높은 경향'],evidence='카드 연구의 성·연령별 경향 · 개별 식사·고립 상태 관측이 아님',default_function='돌봄'),
]


def build_persona_catalog(data,diagnose,reason_names,root:Path):
    source=root/SOURCE
    if not source.is_file():raise ValueError('페르소나 초안 문서를 확인해 주세요.')
    text=source.read_text()
    if not all(f'## P{i}.' in text for i in range(1,6)):raise ValueError('페르소나 초안의 다섯 사례를 확인해 주세요.')
    personas=[]
    for draft in DRAFTS:
        conditions=dict(region=draft['region'],age=draft['age'],sex=draft['sex'],household=draft['household'],
            weekday_day_ok=draft['weekday_day_ok'],income='일반',disabled=False,
            access='디지털 취약(방문·전화만)' if draft['id']=='P5' else '일반(모든 채널 가능)',function=draft['default_function'])
        fields=summarize_support(data,diagnose,reason_names,conditions)
        personas.append(dict(id=draft['id'],region=draft['region'],dong=draft['dong'],age_band=draft['age_band'],sex=draft['sex'],title=draft['title'],
            observed=draft['observed'],evidence=draft['evidence'],conditions=conditions,
            assumptions=[f"{'1인' if draft['household']=='1인' else '다인'}가구",'일반 소득','평일 낮 참여 가능' if draft['weekday_day_ok'] else '평일 낮 참여 어려움',conditions['access']],
            assumption_note=f"문서의 {draft['age_band']}를 엔진에 입력하기 위해 {draft['age']}세를 가정함. 정확한 나이는 조건 수정에서 바꿀 수 있음. 이 다섯 사례는 확정 전 초안이며 실제 주민이 아님.",
            fields=fields,blocked_fields=sum(f['portfolio'] in [e.PORT_CONFLICT,e.PORT_NONE] for f in fields),
            unknown_fields=sum(f['portfolio']==e.PORT_UNKNOWN for f in fields),default_function=draft['default_function']))
    return dict(status='draft',source_document=SOURCE,personas=personas,
                notice='지도는 초안에 적힌 동 또는 지역을 표시함. 실제 거주 주소·집단 규모·개인의 고립 위험을 나타내지 않음.')


def summarize_support(data,diagnose,reason_names,conditions):
    fields=[]
    for function in e.FUNCTIONS:
        result=diagnose(data,{**conditions,'function':function})
        causes=list(dict.fromkeys(reason_names.get(c['code'],c['note'] or c['code']) for p in result['programs'] if p['path']=='충돌' for c in p['checks'] if c['state']=='CONFLICT'))
        fields.append(dict(function=function,portfolio=result['portfolio'],program_count=len(result['programs']),
            open_count=sum(p['path'] in ['이용 가능','조건부(심사)','조건부(부가정보 미확인)'] for p in result['programs']),
            agency_count=sum(p['path']=='기관 발굴로만 연결' for p in result['programs']),
            conflict_count=sum(p['path']=='충돌' for p in result['programs']),unknown_count=sum(p['path']=='확인 필요' for p in result['programs']),
            causes=causes[:3]))
    return fields
