.PHONY: dev test test-fast lint typecheck build docker-build backup storage clean

dev:
	PYTHONPATH=src uvicorn atlas20.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000

test:
	python -m pytest tests/ -q
	npm --prefix apps/web test -- --run

test-fast:
	python -m pytest tests/ -x -q --ff

lint:
	ruff check src tests
	npm --prefix apps/web run lint

# typecheck mirrors CI's mypy strict-pilot scope (schemas, settings, _metrics).
# Expand the file list here AND in .github/workflows/ci.yml when the strict
# pilot grows.
typecheck:
	mypy --strict src/atlas20/api/schemas.py src/atlas20/api/settings.py src/atlas20/api/_metrics.py
	npm --prefix apps/web run typecheck

build:
	npm --prefix apps/web run build

docker-build:
	docker compose build

backup:
	python -m atlas20.api.backup

storage:
	python -m atlas20.api.storage

clean:
	rm -rf .pytest_cache .mypy_cache apps/web/node_modules apps/web/dist
