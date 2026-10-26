"""입력·출력 경로. 입력 폴더는 IEUM_DATA로 바꿀 수 있음(기본: 저장소의 data/)."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('IEUM_DATA', ROOT / 'data'))
POLICY = DATA / 'policy'
PERSONAS = POLICY / 'personas'
WEB_DATA = ROOT / 'dashboard' / 'public' / 'data'
