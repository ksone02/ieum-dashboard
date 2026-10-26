# 이음 — 사회적 고립 지원을 잇는 에이전트 (빅콘테스트 2026)

공개 화면: https://ieum-pink-psi.vercel.app
모델(M3) 저장소: https://github.com/KangKyuC/bigcontest2026

지자체 담당자용 화면임. 동 × 성별 × 나이대 집계 신호로 가상 페르소나를 만들고, 강남 37개·춘천 17개 지원사업의 신청 조건과 한 명씩 대조해 단계(1~4)·할 일·정책 추천을 보여 줌.
- 페르소나는 모두 가상 인물임. 숫자는 실제 주민 수나 고립된 사람 수가 아님
- 단계는 정해 둔 규칙의 출력임(학습된 개인 고립 확률이 아님). 같은 입력이면 늘 같은 결과가 나옴

## 에이전트가 하는 일

| 단계 | 하는 일 | 코드 |
| --- | --- | --- |
| 신호 탐지 | 동 × 성별 × 나이대 집단 중 연락·외출(M3 서울 동년배 백분위)·주말 사람 흐름(SK, 평일 유입 보정)이 하위 20%인 곳을 페르소나로 고름. 연락 상위 20%는 뺌 | `run_dong_personas.py` |
| 조건 대조 | 사업 조건(나이·가구·소득·대상·신청 방법·운영 시간·지역·모집 기간)과 페르소나 조건을 하나씩 대조 → 갈 수 있음 / 조건부 / 막힘 / 확인 필요 | `policy_gap_engine.py` |
| 원인 분석 | 분야(7개)마다 공백 종류를 나눔: 갈 곳 없음 · 방식 다름 · 공고 정보 부족 · 모집 끝남 | `dashboard_agent.py` |
| 추천 | 같은 분야 안에서 맞는 방식 → 지역 안 시설 → 시간 → 신청 경로 순으로 사업 순위. 할 일에 실제 사업 이름과 대안을 넣음 | `run_persona_recommend.py`, `dashboard_agent.py` |
| 단계 판정 | 신호 강함(개인 신호 하위 5%, 또는 하위 20% 둘 이상, 연락 상위 20% 아님) × 공백 유무 → 1 긴급 · 2 높음 · 3 주의 · 4 관찰. 동 전체 값(주말 사람 흐름)만으로는 강함이 되지 않음 | `dashboard_agent.py` |
| 정책 추천 | 조건 하나 바꾸기(저녁·주말 회차, 1인가구·소득 요건, 나이 상한, 신청 방법)·새 사업·공고 보완. 몇 명에게 길이 열리는지 셈 | `dashboard_policy.py` |
| 우선 대상 | 높은 단계 인원이 많은 동 → 공백 분야가 많은 동 순으로 "먼저 볼 곳" | `dashboard_agent.py` |

결과는 `export_dashboard_static.py`가 `dashboard/public/data/`의 JSON 3개로 씀. 화면은 서버 없이 이 파일만 읽음.

## 폴더

| 경로 | 내용 |
| --- | --- |
| `*.py` (최상위) | 에이전트 파이프라인. 공개 사이트를 만든 코드 그대로임 |
| `tests/` | 단계 규칙·조건 엔진 테스트 (로컬 입력 필요) |
| `dashboard/` | 화면 (React · Leaflet). [dashboard/README.md](dashboard/README.md) |
| `dashboard/public/data/` | 화면이 읽는 결과 3개(`agent.json`, `personas.json`, `policy.json`) |
| `deploy_dashboard.sh` | 결과 생성 → 빌드 → Vercel 배포 → 공개 사이트 자료가 로컬과 같은지 확인 |

## 실행

화면만 볼 때 (결과 JSON이 들어 있어서 파이썬 없이 열림):

```sh
npm --prefix dashboard ci
npm --prefix dashboard run dev      # http://127.0.0.1:5173
```

결과를 다시 만들 때 (Python 3.12, `requirements.txt`):

```sh
python run_dong_personas.py
python export_dashboard_static.py
python -m pytest tests
```

**이 저장소만으로는 결과를 다시 만들 수 없음.** 파이프라인은 다음 입력을 `data/` 아래에서 읽고, 공개하지 않음.
- `data/policy/personas/m3_group_profiles.csv` (M3 220셀 결합 입력), `sk_weekend_by_dong.csv` (SK 집계) — 대회 제공 자료에서 만든 입력이라 재배포하지 않음
- `data/policy/` 사업 조건표·출처·운영 장소, `data/reference/` 행정동 경계, `data/external/` 동 인구

## 알려진 한계

- 화면의 "연락·외출 예측" 표기: 실제 값은 M3 관측 백분위(`contact_seoul_peer_percentile` 등)임. 발표자료와 맞추려고 발표 뒤 "연락·외출 집계"로 고칠 예정
- 춘천은 서울 통신 자료가 없어 신호가 주말 사람 흐름 하나뿐 → 모두 3단계. 교동(한림대)·효자2동(강원대)은 대학가 영향일 수 있음
- 동별 페르소나는 모두 혼자 산다고 가정함. 가족과 산다고 바꾸면 닫히는 분야는 주거·안전뿐임(강남 36·춘천 6 조합)
- "60세 미만은 평일 낮에 못 감" 가정: 강남 결론은 가정과 무관, 춘천 "저녁·주말 회차 → 29명"은 일하는 사람 기준
- 단계 판정을 외부 기준과 비교한 검증은 아직 없음

## 데이터·라이선스

- 대회 제공 SK·카드 원자료와 그 결합 입력은 넣지 않음. 결과 JSON은 동·집단 단위 결과로, 공개 사이트에서 제공하는 것과 같음
- 화면의 외부 소스와 글꼴은 [dashboard/THIRD_PARTY_NOTICES.md](dashboard/THIRD_PARTY_NOTICES.md). Satoshi 글꼴 파일은 재배포 범위가 불분명해 넣지 않음(없으면 숫자도 Pretendard로 보임)
