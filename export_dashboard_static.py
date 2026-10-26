"""대시보드 결과를 정적 JSON으로 뽑음. 파이썬 서버 없이(Vercel 등) 화면이 돌아가게 하기 위함.

결과는 데이터가 바뀌지 않는 한 늘 같으므로 미리 계산해 둠.
데이터나 엔진을 바꾸면 이 스크립트를 다시 돌리고 화면을 다시 빌드함.

    .analysis-venv/bin/python -I export_dashboard_static.py && npm --prefix dashboard run build
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import dashboard_server as s  # noqa: E402
from dashboard_agent import build_agent, summary  # noqa: E402
from dashboard_policy import build_policy  # noqa: E402

OUT = ROOT / 'dashboard/public/data'


def dump(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')
    return path.stat().st_size // 1024


if __name__ == '__main__':
    data = s.load_data()
    agent = build_agent(data, s.REASONS)
    policy = build_policy(agent, data['sources'])
    OUT.mkdir(parents=True, exist_ok=True)
    sizes = {'agent.json': dump('agent.json', summary(agent)),
             'personas.json': dump('personas.json', {p['id']: p for p in agent['personas']}),
             'policy.json': dump('policy.json', policy)}
    assert len(json.loads((OUT / 'personas.json').read_text())) == len(agent['personas'])
    print({k: f'{v}KB' for k, v in sizes.items()})
