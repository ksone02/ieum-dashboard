"""기존 정책 분석을 읽기 전용으로 연결하는 로컬 대시보드."""
from __future__ import annotations

import json
import re
import sys
import argparse
import traceback
import mimetypes
from copy import deepcopy
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pandas as pd
from pyproj import Transformer

# -I 실행에서도 이 프로젝트의 검증된 엔진만 명시적으로 불러옴.
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import policy_gap_engine as e
from run_policy_gap_analysis import load_programs, scenarios
from dashboard_briefing import load_briefing_sources, policy_briefing, review_draft as build_review_draft
from dashboard_personas import build_persona_catalog, summarize_support
from dashboard_agent import build_agent, persona_detail, summary as agent_summary
from dashboard_policy import build_policy

POLICY = ROOT / 'data/policy'
REGIONS = ['강남', '춘천']
DEFAULT = dict(region='춘천', age=52, sex='여', household='1인', income='일반',
               access='일반(모든 채널 가능)', weekday_day_ok=False, disabled=False,
               function='관계 형성')
ITEMS = {'status': '운영상태', 'region': '지역', 'age': '나이', 'residence': '세부 거주지역',
         'household': '가구 형태', 'income': '소득', 'target': '사업 대상',
         'screening': '선정 심사', 'channel': '신청 방법', 'device': '필요 기기', 'time': '참여 시간'}
REASONS = {
    'CLOSED': '조사 자료에서 모집 종료 또는 계속 운영 미확인으로 처리한 사업임',
    'AGE_OUT_OF_RANGE': '사업에서 정한 나이 범위에 해당하지 않음',
    'HOUSEHOLD': '사업의 가구·성별 조건과 맞지 않음',
    'HOUSEHOLD_EXCEPTION': '가구 조건의 예외 적용 여부를 심사해야 함',
    'INCOME': '저소득 조건을 충족하지 않음', 'INCOME_SCREEN': '소득 기준 해당 여부를 심사해야 함',
    'TARGET': '사업의 장애인 대상 조건과 맞지 않음', 'TARGET_SCREEN': '필요·위험 등 사업 대상 여부를 심사해야 함',
    'TARGET_ATTR_UNKNOWN': '사업 대상에 해당하는지 추가 확인이 필요함',
    'CHANNEL': '이용할 수 있는 신청 방법이 없음', 'CHANNEL_UNVERIFIED': '신청 방법을 확인해야 함',
    'OUTREACH_ONLY': '직접 신청보다 기관이 찾아내서 연결하는 경로임',
    'DEVICE': '사업에서 요구하는 기기를 사용할 수 없음',
    'TIME': '평일 낮 운영과 참여 가능 시간이 맞지 않음',
    'TIME_UNVERIFIED': '평일 낮 외에 참여할 수 있는 회차인지 확인해야 함',
    'SCREENING': '기관의 선정 심사가 필요함', 'POLICY_FACT_MISSING': '공개 자료에서 조건을 확인하지 못함',
    'SERVICE_AREA_UNVERIFIED': '세부 제공 지역·단지·배달 가능 여부를 확인해야 함',
    'OTHER_REGION': '다른 지역의 사업임',
}
CHANGES = {'S1': '온라인·전화 신청 추가', 'S2': '저녁·주말 회차 추가', 'S3': '1인가구 요건 완화'}


def records(frame):
    """pandas 결측과 숫자를 표준 JSON 값으로 바꿈."""
    return json.loads(frame.to_json(orient='records', force_ascii=False))


def safe_url(value):
    try:
        parsed = urlsplit(str(value))
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except ValueError:
        return False


# 화면에 첫 링크를 거는데 열리지 않는 주소(2026-10-26 확인: 없는 게시물 2개, 서버 오류 나는 검색 페이지 1개)
DEAD_URLS = {'https://bokji.gangnam.go.kr/board/BBS_SUPPORT/1670/view.do?mid=ID03_02&pgno=1',
             'https://bokji.gangnam.go.kr/board/BBS_SUPPORT/1668/view.do?mid=ID03_02&type=',
             'https://1in.seoul.go.kr/front/search/searchList.do'}
# 맨 앞에 걸 링크: 남은 첫 링크가 파일 내려받기·기사라서 운영기관 사업 안내 페이지로 대신함(조사 메모 G04·G05에 있는 주소)
FIRST_URL = {'G04': 'https://www.gangnam1.org/main/sub.html?pageCode=10',
             'G05': 'https://www.gangnam1.org/main/sub.html?pageCode=11'}


def load_data() -> dict:
    def read(path):
        return pd.read_csv(POLICY / path, dtype={'adm_cd': str}).fillna('')

    programs = load_programs()
    conditions = read('policy_conditions.csv')
    candidates = read('research/candidate_decisions.csv')
    facts = read('research/program_facts_checked.csv')
    sources, operators = {}, {}
    for pid in programs.id:
        original = conditions[conditions.id == pid]
        values = original.source_url_1.tolist() + original.source_url_2.tolist()
        values += candidates.loc[candidates.cand_id == pid, 'source_url'].tolist()
        values += facts.loc[facts.id == pid, 'source_url'].tolist()
        sources[pid] = list(dict.fromkeys([FIRST_URL.get(pid, '')] + [u.strip() for v in values for u in re.split(r'[;|]', v)
                                          if safe_url(u.strip()) and u.strip() not in DEAD_URLS]))
        sources[pid] = [u for u in sources[pid] if u]
        operators[pid] = '; '.join(original.operator.drop_duplicates())
    maps = {}
    to_geo = Transformer.from_crs('EPSG:5179', 'EPSG:4326', always_xy=True)

    def coordinates(value):
        if isinstance(value[0], (int, float)):
            return list(to_geo.transform(value[0], value[1]))
        return [coordinates(child) for child in value]

    for region, code in [('강남', '11230'), ('춘천', '32010')]:
        geo = json.loads((ROOT / f'data/reference/boundary_{code}_2025.geojson').read_text())
        geographic = deepcopy(geo['features'])
        for feature in geographic:
            feature['geometry']['coordinates'] = coordinates(feature['geometry']['coordinates'])
        maps[region] = {'features': geo['features'], 'coordinate_system': 'EPSG:4326',
                        'geojson': {'type': 'FeatureCollection', 'features': geographic}}
    centers = read('extra/읍면동_중심점.csv')
    centers['longitude'], centers['latitude'] = to_geo.transform(centers.centroid_x, centers.centroid_y)
    return dict(programs=programs, sources=sources, operators=operators, facts=facts,
                indicators=read('weighted/indicators.csv'), cells=read('cells/policy_by_sex_age.csv'),
                distances=read('extra/공간접근성_읍면동별.csv'), sites=read('extra/서비스_장소.csv'),
                centers=centers, maps=maps, briefing_sources=load_briefing_sources(POLICY))


def metadata(data: dict) -> dict:
    return dict(regions=REGIONS, functions=e.FUNCTIONS, access=list(e.ACCESS),
                program_counts=data['programs'].groupby('region').size().to_dict(),
                defaults=DEFAULT, path_order=e.PATH_ORDER, items=ITEMS, reasons=REASONS, changes=CHANGES,
                m3={'available': False, 'message': '연락·외출 원본 미수령 · 추천 순서 규칙 미정. 고립 위험 판정에는 사용하지 않음'},
                signal_basis='policy_gap', persona_slots=[None]*5, priority_ready=False,
                basis='정책 조사·분석본 2026-10-19 / 성·연령 연결표 2026-10-25',
                notice='공고 기준으로 정리한 조사 범위의 결과이며 현재 모집·정원은 기관에 확인해야 함.')


def validate_choice(value, allowed, label):
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f'{label} 값을 확인해 주세요.')


def validate_payload(payload):
    if not isinstance(payload, dict) or set(payload) != set(DEFAULT):
        raise ValueError('주민 조건의 입력 항목을 확인해 주세요.')
    for key, allowed in dict(region=REGIONS, sex=['남', '여'], household=['1인', '다인'],
                             income=['저소득', '일반'], access=list(e.ACCESS), function=e.FUNCTIONS).items():
        validate_choice(payload[key], allowed, key)
    if type(payload['age']) is not int or not 19 <= payload['age'] <= 100:
        raise ValueError('나이는 19~100세의 정수로 입력해 주세요.')
    for key in ['weekday_day_ok', 'disabled']:
        if type(payload[key]) is not bool:
            raise ValueError('참여 시간과 장애 여부는 참 또는 거짓으로 입력해 주세요.')


def overview(data: dict, region: str, function: str) -> dict:
    validate_choice(region, REGIONS, '지역')
    validate_choice(function, e.FUNCTIONS, '사업 분류')
    programs = data['programs'].query('region == @region')
    indicators = data['indicators']
    wanted = ((indicators.indicator == 'E3') |
              ((indicators.indicator == 'E1') & (indicators.detail == '평균 안내 도메인 수')) |
              ((indicators.indicator == 'E2') & indicators.detail.str.contains('평균 누락 비율')))
    metrics = records(indicators[(indicators.region == region) & (indicators.variant == 'main') & wanted])
    for m in metrics:
        m['basis'] = ('충돌인 시나리오×사업 검토 중 같은 목적의 대안이 남는 추정 비율. 실제 담당자 오류율이 아님.'
                      if m['indicator'] == 'E3' else
                      '열린 사업이 있는 조건별 공식 목록 누락 비율을 추정 주민 수로 평균함.'
                      if m['indicator'] == 'E2' else '주민 조건별 안내 출처의 도메인 수를 추정 주민 수로 평균함.')
    sites = data['sites']
    sites = sites[(sites.region == region) & sites.operating.eq(True) &
                  sites.functions.map(lambda fs: function in fs.split(';'))]
    distances = data['distances']
    distances = distances[(distances.region == region) & (distances.function == function)]
    centers = data['centers'].query('region == @region')
    cells = data['cells']
    cells = cells[(cells.region == region) & (cells.function == function)]
    return dict(region=region, function=function, program_count=len(programs),
                providers=programs.groupby('provider').size().to_dict(),
                functions=[{'function': f, 'count': sum(e.has_function(g, f) for g in programs.to_dict('records'))}
                           for f in e.FUNCTIONS],
                metrics=metrics, map=data['maps'][region], sites=records(sites),
                centers=records(centers), distances=records(distances), cells=records(cells),
                cell_notice='강남 전체 성·연령별 추정 비율로 동마다 같은 값임. 동별 인구·지원 필요 인원으로 읽거나 합산하지 않음.',
                distance_notice='동 중심점부터 운영 중 대면 장소까지 직선거리임. 도로 대표점 등 근사 위치를 포함하며 실제 이동거리·시간이 아님.')


def diagnose(data: dict, payload: dict) -> dict:
    validate_payload(payload)
    persona = e.Persona(**{k: v for k, v in payload.items() if k != 'function'})
    selected = data['programs'][data['programs'].region == persona.region]
    programs = []
    for g in selected.to_dict('records'):
        if not e.has_function(g, payload['function']):
            continue
        checks = e.l1(persona, g)
        path, reason = e.l2(checks)
        detail = records(data['facts'][data['facts'].id == g['id']])
        programs.append(dict(id=g['id'], program=g['program'], provider=g['provider'],
                             operator=data['operators'][g['id']], path=path, reason=reason,
                             checks=[asdict(c) for c in checks], sources=data['sources'][g['id']], facts=detail,
                             coding_note=g['coding_note'] if isinstance(g['coding_note'], str) else '',
                             conditions=records(pd.DataFrame([g]))[0]))
    programs.sort(key=lambda g: (e.PATH_ORDER.index(g['path']), g['id']))
    paths = [g['path'] for g in programs]
    return dict(persona=asdict(persona), function=payload['function'],
                portfolio=e.l3(paths, len(programs)),
                counts={state: paths.count(state) for state in e.PATH_ORDER}, programs=programs)


def simulate(data: dict, payload: dict) -> dict:
    if not isinstance(payload, dict) or set(payload) != set(DEFAULT) | {'program_id', 'change'}:
        raise ValueError('비교할 주민 조건·사업·변경을 확인해 주세요.')
    person = {k: payload[k] for k in DEFAULT}
    validate_payload(person)
    validate_choice(payload['change'], CHANGES, '조건 변경')
    validate_choice(payload['program_id'], data['programs'].id.tolist(), '사업')
    row = data['programs'][data['programs'].id == payload['program_id']]
    g = row.iloc[0].to_dict()
    if g['region'] != person['region'] or not e.has_function(g, person['function']):
        raise ValueError('선택한 지역·분류에 속하는 사업을 골라 주세요.')
    changed = scenarios(row)[f"{payload['change']} {CHANGES[payload['change']]}"]
    fields = {}
    for col in ['ch_online', 'ch_phone', 'schedule', 'household_req']:
        before, after = row.iloc[0][col], changed.iloc[0][col]
        if before != after:
            fields[col] = dict(before=before, after=after)
    programs = data['programs'].copy(deep=True)
    programs.loc[row.index, changed.columns] = changed
    return dict(before=diagnose(data, person), after=diagnose({**data, 'programs': programs}, person),
                changed_fields=fields, changed_program_ids=[g['id']] if fields else [],
                program_id=g['id'], change=payload['change'])


def persona_catalog(data):
    if "persona_catalog" not in data:
        data["persona_catalog"] = build_persona_catalog(data, diagnose, REASONS, ROOT)
    return data["persona_catalog"]


def persona_check(data, payload):
    validate_payload(payload)
    return dict(fields=summarize_support(data, diagnose, REASONS, payload))


def review_draft(data, payload):
    return build_review_draft(data, payload, diagnose)


def make_server(host: str = '127.0.0.1', port: int = 8765) -> ThreadingHTTPServer:
    if host not in ('127.0.0.1', 'localhost'):
        raise ValueError('로컬 주소에서만 실행할 수 있습니다.')
    data = load_data()
    build = (ROOT / 'dashboard/dist').resolve()

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, body, content_type='application/json; charset=utf-8'):
            if isinstance(body, dict):
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass  # 다른 조건으로 재조회하면서 취소한 브라우저 요청임.

        def do_GET(self):
            parsed = urlsplit(self.path)
            try:
                if parsed.path == '/api/meta':
                    self.reply(200, metadata(data))
                elif parsed.path == '/api/policy':
                    if 'agent' not in data:
                        data['agent'] = build_agent(data, REASONS)
                    if 'policy' not in data:
                        data['policy'] = build_policy(data['agent'], data['sources'])
                    self.reply(200, data['policy'])
                elif parsed.path in ('/api/agent', '/api/agent/persona'):
                    if 'agent' not in data:
                        data['agent'] = build_agent(data, REASONS)
                    if parsed.path == '/api/agent':
                        self.reply(200, agent_summary(data['agent']))
                    else:
                        query = parse_qs(parsed.query)
                        if set(query) != {'id'} or len(query['id']) != 1:
                            raise ValueError('페르소나를 한 명 지정해 주세요.')
                        self.reply(200, persona_detail(data['agent'], query['id'][0]))
                elif parsed.path == '/api/personas':
                    if parsed.query:
                        raise ValueError('페르소나 목록은 추가 조건 없이 조회해 주세요.')
                    self.reply(200, persona_catalog(data))
                elif parsed.path == '/api/briefing':
                    query = parse_qs(parsed.query)
                    if set(query) != {'region'} or len(query['region']) != 1:
                        raise ValueError('지역을 한 개 지정해 주세요.')
                    self.reply(200, policy_briefing(data, query['region'][0]))
                elif parsed.path == '/api/overview':
                    query = parse_qs(parsed.query)
                    if set(query) != {'region', 'function'} or any(len(v) != 1 for v in query.values()):
                        raise ValueError('지역과 사업 분류를 한 개씩 지정해 주세요.')
                    self.reply(200, overview(data, query['region'][0], query['function'][0]))
                elif parsed.path in ('/', '/index.html') or parsed.path.startswith(('/assets/', '/fonts/', '/icons/', '/data/')):
                    path = (build / ('index.html' if parsed.path == '/' else parsed.path.lstrip('/'))).resolve()
                    if not path.is_relative_to(build) or not path.is_file() or path.suffix not in {'.html', '.js', '.css', '.woff2', '.png', '.svg', '.json'}:
                        self.reply(404, {'error': '요청한 자산을 찾지 못했습니다.'})
                        return
                    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
                    self.reply(200, path.read_bytes(), mime)
                else:
                    self.reply(404, {'error': '요청한 화면이나 자료를 찾지 못했습니다.'})
            except ValueError as exc:
                self.reply(400, {'error': str(exc)})
            except Exception:
                traceback.print_exc()
                self.reply(500, {'error': '자료를 읽지 못했습니다. 서버 실행 상태를 확인해 주세요.'})

        def do_POST(self):
            route = urlsplit(self.path).path
            if route not in ('/api/diagnose', '/api/simulate', '/api/draft', '/api/persona-check'):
                self.reply(404, {'error': '요청한 계산을 찾지 못했습니다.'})
                return
            origin = self.headers.get('Origin')
            if origin and origin != f"http://{self.headers.get('Host')}":
                self.reply(403, {'error': '같은 로컬 화면에서 요청해 주세요.'})
                return
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                self.reply(415, {'error': 'JSON 형식으로 요청해 주세요.'})
                return
            try:
                size = int(self.headers.get('Content-Length', '-1'))
                if size < 0:
                    raise ValueError('요청 크기를 확인해 주세요.')
                if size > 65536:
                    self.reply(413, {'error': '입력이 너무 큽니다.'})
                    return
                payload = json.loads(self.rfile.read(size))
                result = persona_check(data, payload) if route == '/api/persona-check' else review_draft(data, payload) if route == '/api/draft' else diagnose(data, payload) if route == '/api/diagnose' else simulate(data, payload)
                self.reply(200, result)
            except (ValueError, UnicodeError) as exc:
                self.reply(400, {'error': str(exc) if not isinstance(exc, json.JSONDecodeError) else '입력 JSON을 확인해 주세요.'})
            except Exception:
                traceback.print_exc()
                self.reply(500, {'error': '계산을 완료하지 못했습니다. 입력을 확인하고 다시 시도해 주세요.'})

        def log_message(self, format, *args):
            if args and str(args[1] if len(args) > 1 else '').startswith('5'):
                super().log_message(format, *args)

    return ThreadingHTTPServer((host, port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('포트는 1~65535 사이여야 합니다.')
    try:
        server = make_server(port=args.port)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'대시보드를 시작하지 못했습니다: {exc}\n')
    print(f'정책 검토 대시보드: http://127.0.0.1:{server.server_port}', flush=True)
    print('종료: Ctrl+C / 원자료는 읽기만 합니다.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
