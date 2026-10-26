# dashboard

이음 화면이에요. 전체 설명은 [최상위 README](../README.md)에 있어요.

화면은 `public/data/`의 JSON 세 개(`agent.json`, `personas.json`, `policy.json`)만 읽어요. 이 파일은 `python -m ieum.export`가 만들어요.

| 파일                         | 하는 일            |
| ---------------------------- | ------------------ |
| `src/agent/AgentApp.tsx`     | 왼쪽 브리핑과 목록 |
| `src/agent/AgentMap.tsx`     | 지도               |
| `src/agent/PersonaPanel.tsx` | 인물 분석 창       |
| `src/agent/PolicyPanel.tsx`  | 정책 추천 상세     |
| `src/agent/types.ts`         | JSON 형식          |
