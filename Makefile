.PHONY: help install install-py install-ui dev dev-backend dev-ui \
        test-unit test-int test-e2e test-all coverage \
        lint format build docker-build clean

UV := uv
PNPM := pnpm
UI_DIR := ui

help:
	@echo "Targets:"
	@echo "  install      Install all Python and Node dependencies"
	@echo "  dev          Run backend + UI dev servers in parallel"
	@echo "  test-unit    Run Python unit tests"
	@echo "  test-int     Run Python integration tests"
	@echo "  test-e2e     Run Playwright + testcontainers E2E tests"
	@echo "  test-all     Run unit + integration + E2E"
	@echo "  coverage     Combined Python coverage report (gate 100%)"
	@echo "  lint         Ruff + TypeScript checks"
	@echo "  format       Ruff format"
	@echo "  build        Build UI static bundle"
	@echo "  docker-build Build orchestrator Docker image"
	@echo "  clean        Remove caches and build artefacts"

install: install-py install-ui
	$(UV) run playwright install chromium

install-py:
	$(UV) sync --group dev --group test-unit --group test-integration --group test-e2e

install-ui:
	cd $(UI_DIR) && $(PNPM) install --frozen-lockfile

dev:
	@echo "Starting backend on :8000 and UI on :5173 — Ctrl+C stops both"
	@trap 'kill 0' INT TERM EXIT; \
	$(UV) run uvicorn orchestrator.main:app --reload --port 8000 & \
	(cd $(UI_DIR) && $(PNPM) dev) & \
	wait

dev-backend:
	$(UV) run uvicorn orchestrator.main:app --reload --port 8000

dev-ui:
	cd $(UI_DIR) && $(PNPM) dev

test-unit:
	$(UV) run pytest tests/unit -m unit

test-int:
	$(UV) run pytest tests/integration -m integration

test-e2e:
	$(UV) run pytest tests/e2e -m e2e

# Coverage gate scope (per ARCHITECTURE.md §9): unit + integration cover
# the Python codebase to 100%; UI Vitest covers src/lib/hooks/stores to 100%;
# E2E targets 100% of UI flows (not Python line coverage — the daemon runs
# inside a container, out of coverage.py reach).
test-all:
	$(UV) run pytest tests/unit tests/integration -m "unit or integration" \
		--cov=orchestrator --cov-fail-under=100
	cd $(UI_DIR) && $(PNPM) coverage
	$(UV) run pytest tests/e2e -m e2e

coverage:
	$(UV) run pytest tests/unit tests/integration -m "unit or integration" \
		--cov=orchestrator --cov-report=term-missing --cov-fail-under=100

lint:
	$(UV) run ruff check .
	cd $(UI_DIR) && $(PNPM) exec tsc -b --noEmit

format:
	$(UV) run ruff format .

build:
	cd $(UI_DIR) && $(PNPM) build

docker-build:
	docker build -f Dockerfile.orchestrator -t j-arvis-orchestrator:latest .

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov coverage.xml
	rm -rf $(UI_DIR)/dist $(UI_DIR)/coverage $(UI_DIR)/.vite
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
