#!/bin/sh
# 결과를 다시 만들고 화면을 빌드해서 Vercel 프로젝트 "ieum"(https://ieum-pink-psi.vercel.app)에 올림.
# Vercel 로그인은 각자 함(`npx vercel login`). 프로젝트 id는 비밀값이 아님.
set -e
cd "$(dirname "$0")/.."
uv run python -m ieum.export
npm --prefix dashboard run build
deploy() {
  VERCEL_ORG_ID=team_XQDEx13vCX6gqxGTjFWF32PR VERCEL_PROJECT_ID=prj_84CLpaIP9yVfHE5v9lXb2EiXqBAw \
    npx vercel deploy dashboard/dist --prod --yes
}
# 올린 직후 1분 가까이 예전 판이 나올 수 있어서, 공개 사이트 자료가 방금 만든 것과 같아질 때까지 기다림
same() { curl -s "https://ieum-pink-psi.vercel.app/data/personas.json?t=$(date +%s)" | cmp -s - dashboard/dist/data/personas.json; }
wait_same() { for _ in 1 2 3 4 5 6 7 8 9; do same && return 0; sleep 10; done; return 1; }
deploy
wait_same || { echo '공개 사이트 자료가 달라서 다시 올림'; deploy; }
wait_same && echo '공개 사이트 자료 확인됨' || { echo '공개 사이트 자료가 여전히 다름. 직접 확인 필요' >&2; exit 1; }
