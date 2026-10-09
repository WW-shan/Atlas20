VENV ?= .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip
VENV_STAMP := $(VENV)/.installed

.PHONY: setup dev test test-fast lint typecheck build docker-build backup storage openapi load-test clean

$(PYTHON):
	python -m venv $(VENV)

$(VENV_STAMP): pyproject.toml $(PYTHON)
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install -e ".[dev]"
	touch $(VENV_STAMP)

setup: $(VENV_STAMP)

dev: $(VENV_STAMP)
	PYTHONPATH=src $(PYTHON) -m uvicorn atlas20.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000

test: $(VENV_STAMP)
	$(PYTHON) -m pytest tests/ -q
	npm --prefix apps/web test -- --run

test-fast: $(VENV_STAMP)
	$(PYTHON) -m pytest tests/ -x -q --ff

lint: $(VENV_STAMP)
	$(PYTHON) -m ruff check src tests
	npm --prefix apps/web run lint

# typecheck mirrors CI's strict API mypy scope.
typecheck: $(VENV_STAMP)
	$(PYTHON) -m mypy --strict src/atlas20/api
	npm --prefix apps/web run typecheck

build:
	npm --prefix apps/web run build

docker-build:
	docker compose build

backup: $(VENV_STAMP)
	$(PYTHON) -m atlas20.api.backup

storage: $(VENV_STAMP)
	$(PYTHON) -m atlas20.api.storage

openapi: $(VENV_STAMP)
	$(PYTHON) -m atlas20.api.openapi

load-test: $(VENV_STAMP)
	$(PYTHON) scripts/load_test_api.py --rps 100 --duration-seconds 60 --p95-ms 200

# Derivatives track daily routine (Ubuntu-friendly: plain make, no launchd).
# Requires the frozen spec; never used to select parameters.
derivatives-oos-data: $(VENV_STAMP)
	$(PYTHON) scripts/download_bitget_derivatives_data.py \
		--output-dir data/raw/bitget_derivatives/merged_oos_20261009 \
		--start 2026-09-21 --end $(shell $(PYTHON) -c "import datetime;print((datetime.datetime.now(datetime.UTC)+datetime.timedelta(days=1)).date())") \
		--types mark

derivatives-oos: $(VENV_STAMP)
	$(PYTHON) scripts/run_derivatives_oos.py

clean:
	rm -rf .pytest_cache .mypy_cache apps/web/node_modules apps/web/dist
