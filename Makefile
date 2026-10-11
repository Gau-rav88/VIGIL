.PHONY: env keys up down nuke logs migrate schemas lint test test-int smoke scenario load-test chaos verify market social datasets gate

env:
	@cp -n .env.example .env 2>/dev/null || true
	@uv run python scripts/check_env.py

keys:
	@./scripts/gen_dev_keys.sh

up: env keys
	@docker compose up -d --build
	@./scripts/wait_for_stack.sh

market:
	@./scripts/run_market.sh

social:
	@./scripts/run_social.sh

down:
	@docker compose down

nuke:
	@docker compose down -v

logs:
	@docker compose logs -f --tail=200 $(S)

migrate:
	@docker compose run --rm migrate

schemas:
	@uv run python scripts/export_schemas.py

lint:
	@uv run ruff check . && uv run mypy --strict libs services

test: keys
	@uv run pytest tests/unit tests/contract -q --cov=services/agents/quant_telemetry/src/quant_telemetry/detectors --cov-fail-under=80

test-int: keys
	@uv run pytest tests/integration -q

smoke:
	@./scripts/smoke_test.sh

scenario:
	@if [ -z "$(ID)" ]; then echo "Error: Scenario ID is required. Example: make scenario ID=baseline_01"; exit 1; fi
	@echo "Checking simulator subscribers status..."
	@status=$$(curl -fsS "http://localhost:8090/status" 2>/dev/null || echo '{"status":"offline"}'); \
	echo "Simulator status: $$status"; \
	resp=$$(curl -fsS -X POST "http://localhost:8090/scenarios/$(ID)/start?speed=$(or $(SPEED),10)&seed=$(or $(SEED),42)"); \
	echo "Scenario start response: $$resp"

load-test:
	@uv run python scripts/load_test.py --rate 5000 --duration 900

chaos:
	@./scripts/chaos_test.sh

verify: keys
	@uv run vigil-verify $(BUNDLE) --pubkey keys/dev_ed25519.pub

datasets:
	@./scripts/fetch_datasets.sh

gate:
	@./scripts/gates/phase_$(PHASE).sh
