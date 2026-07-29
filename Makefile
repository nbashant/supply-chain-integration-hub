.PHONY: api-check benchmark compose-down compose-up e2e format lint observability-up pipeline-backfill pipeline-pause pipeline-seed pipeline-up test test-integration typecheck ui-build ui-check ui-dev verify

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy

test:
	uv run pytest -m "not integration and not e2e"

test-integration:
	docker compose --profile test up \
		--build \
		--abort-on-container-exit \
		--exit-code-from tests \
		tests; \
	test_status=$$?; \
	docker compose --profile test rm --stop --force test-db tests; \
	exit $$test_status

benchmark:
	uv run python -m supply_chain_hub.analytics.benchmark \
		--rows 100000 \
		--seed 20260729 \
		--repeats 5 \
		--output artifacts/phase4_benchmark.json

verify: lint typecheck test

ui-check:
	cd ui && npm run check

ui-build:
	cd ui && npm run build

ui-dev:
	cd ui && npm run dev

compose-up:
	docker compose up --build --detach

compose-down:
	docker compose down

pipeline-up:
	docker compose --profile pipeline up --build --detach airflow

pipeline-seed:
	docker compose --profile pipeline exec airflow python \
		/opt/airflow/pipelines/seed_historical_inventory.py \
		--start-date 2026-07-25 --end-date 2026-07-27 --rows-per-day 1000

pipeline-backfill:
	docker compose --profile pipeline exec airflow airflow dags unpause \
		--yes inventory_risk_daily
	docker compose --profile pipeline exec airflow airflow backfill create \
		--dag-id inventory_risk_daily \
		--from-date 2026-07-25 --to-date 2026-07-27 \
		--reprocess-behavior completed --max-active-runs 1

pipeline-pause:
	docker compose --profile pipeline exec airflow airflow dags pause \
		--yes inventory_risk_daily

observability-up:
	docker compose --profile observability up --build --detach prometheus grafana

e2e:
	uv run pytest -m e2e tests/e2e

api-check:
	curl --fail --silent http://127.0.0.1:8000/health/ready
