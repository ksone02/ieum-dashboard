"""화면이 읽는 결과 3개(agent.json · personas.json · policy.json)를 dashboard/public/data에 씀.

python -m ieum.export
"""

import json

from ieum.agent import build_agent, summary
from ieum.paths import WEB_DATA
from ieum.policy import build_policy
from ieum.sources import REASONS, load_data


def dump(name, value):
    path = WEB_DATA / name
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')
    return path.stat().st_size // 1024


def main():
    data = load_data()
    agent = build_agent(data, REASONS)
    policy = build_policy(agent, data['sources'])
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    sizes = {
        'agent.json': dump('agent.json', summary(agent)),
        'personas.json': dump('personas.json', {p['id']: p for p in agent['personas']}),
        'policy.json': dump('policy.json', policy),
    }
    print({k: f'{v}KB' for k, v in sizes.items()})


if __name__ == '__main__':
    main()
