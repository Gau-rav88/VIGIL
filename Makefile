.PHONY: up down nuke logs migrate schemas lint test test-int smoke scenario load-test chaos verify market social

up:
	@./scripts/gen_dev_keys.sh
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

test:
	@uv run pytest tests/unit tests/contract -q --cov=services/agents/quant_telemetry/src/quant_telemetry/detectors --cov-fail-under=80

test-int:
	@uv run pytest tests/integration -q

smoke:
	@./scripts/smoke_test.sh

scenario:
	@curl -fsS -X POST "http://localhost:8090/scenarios/$(ID)/start?speed=$(or $(SPEED),10)&seed=$(or $(SEED),42)"

load-test:
	@uv run python scripts/load_test.py --rate 5000 --duration 900

chaos:
	@./scripts/chaos_test.sh

verify:
	@uv run vigil-verify $(BUNDLE) --pubkey keys/dev_ed25519.pub

datasets:
	@./scripts/fetch_datasets.sh

gate:
	@./scripts/gates/phase_$(PHASE).sh
