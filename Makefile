.PHONY: install test lint typecheck check

install:
	pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check .

typecheck:
	mypy

check: lint typecheck test
