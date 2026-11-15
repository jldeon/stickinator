UV ?= uv

.PHONY: setup lock run test smoke lint build clean

setup:
	./scripts/bootstrap.sh

lock:
	$(UV) lock

run:
	$(UV) run stickinator

test:
	QT_QPA_PLATFORM=offscreen $(UV) run pytest

smoke:
	QT_QPA_PLATFORM=offscreen $(UV) run python scripts/smoke_gui.py

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy

build:
	./scripts/build_macos.sh

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
