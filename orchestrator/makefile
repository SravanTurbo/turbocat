.PHONY: setup install install-prod lint format test test-integration migrate migrate-down migration run

ENV ?= local

setup:
	poetry config virtualenvs.create true
	poetry install
	poetry run pre-commit install --install-hooks

install:
	poetry install

install-prod:
	poetry install --without dev

lint:
	poetry run flake8 .
	poetry run mypy .

format:
	poetry run black .

test:
	poetry run pytest tests/

test-integration:
	poetry run pytest tests/integration/ -s -v

run:
	APP_ENV=$(ENV) poetry run python -m uvicorn orchestrator.main:app --reload --port 8000

migrate:
	APP_ENV=$(ENV) poetry run alembic upgrade head

migrate-down:
	APP_ENV=$(ENV) poetry run alembic downgrade -1

migration:
	APP_ENV=$(ENV) poetry run alembic revision --autogenerate -m "$(name)"
