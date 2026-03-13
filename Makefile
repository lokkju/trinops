.PHONY: record record-all test

record:
ifndef VERSION
	$(error VERSION is required. Usage: make record VERSION=449)
endif
	uv run python scripts/record_trino.py $(VERSION)

record-all:
	uv run python scripts/record_trino.py --all

test:
	uv run python -m pytest tests/ -x -q
