.PHONY: install install-prod lint test format

setup:
	poetry config virtualenvs.create true
	poetry install
	poetry run pre-commit install --install-hooks

install:
	poetry install
	poetry run pre-commit install

install-prod:
	poetry install --without dev

lint:
	poetry run flake8 .
	poetry run mypy .

format:
	poetry run black .

test:
	poetry run pytest