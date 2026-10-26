# 자주 쓰는 명령. 처음에는 `make install`.
.PHONY: install lint format test data build dev deploy

install:
	uv sync
	npm --prefix dashboard ci

lint:
	uv run ruff check .
	uv run ruff format --check .
	npm --prefix dashboard run lint
	npm --prefix dashboard run typecheck

format:
	uv run ruff check --fix .
	uv run ruff format .
	npm --prefix dashboard run format

test:
	uv run pytest

data:  ## data/ 입력이 있어야 함
	uv run python -m ieum.personas
	uv run python -m ieum.export

build:
	npm --prefix dashboard run build

dev:
	npm --prefix dashboard run dev

deploy:
	scripts/deploy.sh
