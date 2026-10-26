# 화면 (dashboard)

React · Leaflet · Vite. 서버 없이 `public/data/`의 결과 3개만 읽음. 결과를 만드는 코드와 전체 설명은 [최상위 README](../README.md).

| 파일 | 내용 |
| --- | --- |
| `src/agent/AgentApp.tsx` | 브리핑(결론 한 줄 · 에이전트가 한 일 · 단계 인원) · 동별/대표 사례/정책 추천 목록 |
| `src/agent/AgentMap.tsx` | 지도: 동 단계 색 · 동 배지 · 페르소나 핀 · 추천 대상 동 |
| `src/agent/PersonaPanel.tsx` | 인물 분석 창: 단계 · 판단 기록 · 분야별 후보와 걸린 조건 · 원문 링크 |
| `src/agent/PolicyPanel.tsx` | 정책 추천 상세: 해당 인원 · 동별 분포 · 다른 지역 사례 |
| `src/agent/agent.css` | 화면 스타일 |

```sh
npm ci
npm run dev     # http://127.0.0.1:5173
npm run build   # dist/
```
