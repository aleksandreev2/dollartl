SHELL := /bin/bash

.PHONY: install lint typecheck test check migrate revision compose-up compose-down backup restore config-check

install:
	python -m pip install -e '.[dev]'

lint:
	ruff check .

typecheck:
	mypy

test:
	pytest -q --cov=dollartl --cov-report=term-missing

check: lint typecheck test

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(m)"

compose-up:
	docker compose up --build

compose-down:
	docker compose down

backup:
	./scripts/db_export.sh

restore:
	./scripts/db_import.sh "$(BACKUP)"

config-check:
	python scripts/config_check.py
