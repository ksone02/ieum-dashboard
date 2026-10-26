"""화면 결과에 필요한 입력을 읽음: 사업 조건표, 사업별 원문 링크, 운영 장소, 동 중심점, 행정동 경계."""

import json
import re
from copy import deepcopy
from urllib.parse import urlsplit

import pandas as pd
from pyproj import Transformer

from ieum.engine import load_programs
from ieum.paths import DATA, POLICY

REASONS = {
    'CLOSED': '조사 자료에서 모집 종료 또는 계속 운영 미확인으로 처리한 사업임',
    'AGE_OUT_OF_RANGE': '사업에서 정한 나이 범위에 해당하지 않음',
    'HOUSEHOLD': '사업의 가구·성별 조건과 맞지 않음',
    'HOUSEHOLD_EXCEPTION': '가구 조건의 예외 적용 여부를 심사해야 함',
    'INCOME': '저소득 조건을 충족하지 않음',
    'INCOME_SCREEN': '소득 기준 해당 여부를 심사해야 함',
    'TARGET': '사업의 장애인 대상 조건과 맞지 않음',
    'TARGET_SCREEN': '필요·위험 등 사업 대상 여부를 심사해야 함',
    'TARGET_ATTR_UNKNOWN': '사업 대상에 해당하는지 추가 확인이 필요함',
    'CHANNEL': '이용할 수 있는 신청 방법이 없음',
    'CHANNEL_UNVERIFIED': '신청 방법을 확인해야 함',
    'OUTREACH_ONLY': '직접 신청보다 기관이 찾아내서 연결하는 경로임',
    'DEVICE': '사업에서 요구하는 기기를 사용할 수 없음',
    'TIME': '평일 낮 운영과 참여 가능 시간이 맞지 않음',
    'TIME_UNVERIFIED': '평일 낮 외에 참여할 수 있는 회차인지 확인해야 함',
    'SCREENING': '기관의 선정 심사가 필요함',
    'POLICY_FACT_MISSING': '공개 자료에서 조건을 확인하지 못함',
    'SERVICE_AREA_UNVERIFIED': '세부 제공 지역·단지·배달 가능 여부를 확인해야 함',
    'OTHER_REGION': '다른 지역의 사업임',
}


def safe_url(value):
    try:
        parsed = urlsplit(str(value))
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except ValueError:
        return False


# 화면에 첫 링크를 거는데 열리지 않는 주소(2026-10-26 확인: 없는 게시물 2개, 서버 오류 나는 검색 페이지 1개)
DEAD_URLS = {
    'https://bokji.gangnam.go.kr/board/BBS_SUPPORT/1670/view.do?mid=ID03_02&pgno=1',
    'https://bokji.gangnam.go.kr/board/BBS_SUPPORT/1668/view.do?mid=ID03_02&type=',
    'https://1in.seoul.go.kr/front/search/searchList.do',
}
# 맨 앞에 걸 링크: 남은 첫 링크가 파일 내려받기·기사라서 운영기관 사업 안내 페이지로 대신함(조사 메모 G04·G05에 있는 주소)
FIRST_URL = {
    'G04': 'https://www.gangnam1.org/main/sub.html?pageCode=10',
    'G05': 'https://www.gangnam1.org/main/sub.html?pageCode=11',
}


def load_data() -> dict:
    def read(path):
        return pd.read_csv(POLICY / path, dtype={'adm_cd': str}).fillna('')

    programs = load_programs()
    conditions = read('policy_conditions.csv')
    candidates = read('research/candidate_decisions.csv')
    facts = read('research/program_facts_checked.csv')
    sources = {}
    for pid in programs.id:
        original = conditions[conditions.id == pid]
        values = original.source_url_1.tolist() + original.source_url_2.tolist()
        values += candidates.loc[candidates.cand_id == pid, 'source_url'].tolist()
        values += facts.loc[facts.id == pid, 'source_url'].tolist()
        urls = [u.strip() for v in values for u in re.split(r'[;|]', v)]
        urls = [FIRST_URL.get(pid, '')] + [u for u in urls if safe_url(u) and u not in DEAD_URLS]
        sources[pid] = [u for u in dict.fromkeys(urls) if u]

    to_geo = Transformer.from_crs('EPSG:5179', 'EPSG:4326', always_xy=True)

    def coordinates(value):
        if isinstance(value[0], int | float):
            return list(to_geo.transform(value[0], value[1]))
        return [coordinates(child) for child in value]

    maps = {}
    for region, code in [('강남', '11230'), ('춘천', '32010')]:
        geo = json.loads((DATA / f'reference/boundary_{code}_2025.geojson').read_text())
        features = deepcopy(geo['features'])
        for feature in features:
            feature['geometry']['coordinates'] = coordinates(feature['geometry']['coordinates'])
        maps[region] = {'geojson': {'type': 'FeatureCollection', 'features': features}}
    centers = read('extra/읍면동_중심점.csv')
    centers['longitude'], centers['latitude'] = to_geo.transform(centers.centroid_x, centers.centroid_y)
    return dict(programs=programs, sources=sources, sites=read('extra/서비스_장소.csv'), centers=centers, maps=maps)
