# Supply Chain Integration Hub

This is a local, hands-on study project for building a production-style Python
supply-chain integration platform. Phases 0 through 7 implement the product
design, operational REST API, partner adapters, durable asynchronous imports,
analytical workbench, scheduled historical pipeline, and production-quality
hardening, plus a first-party visual learning and operations console.

## Current stack

- Python 3.12.12, FastAPI, and Pydantic
- PostgreSQL 17, SQLAlchemy 2, and Alembic
- Redis 8 and Celery 5.6
- SeaweedFS 4.34 with its S3-compatible API
- NumPy 2.5, Pandas 3.0, and Polars 1.43
- Apache Spark 4.2, Parquet, and Apache Airflow 3.3
- Prometheus 3.12 and Grafana 13.1
- React 19, TypeScript 5.9, Vite 6, and Lucide
- uv, Ruff, strict mypy, pytest, and coverage
- Docker and Docker Compose

## Start the application

Docker Desktop or another Docker-compatible runtime must be running.

```bash
docker compose up --build --detach
curl --fail http://127.0.0.1:8000/health/ready
```

Readiness requires PostgreSQL, Redis, and object storage. Partner ingestion
routes also require this local development header:

```text
X-Partner-Token: local-partner-token-change-me
```

Set `PARTNER_API_TOKEN` to replace it. Production configuration refuses to
start with that placeholder.

Useful endpoints:

- Learning Operations UI — no login: <http://127.0.0.1:8000/hub>
- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
- Prometheus metrics: <http://127.0.0.1:8000/metrics>

Stop the application with `docker compose down`. Named data volumes are
preserved.

## Implemented API

| Area | Operations |
|---|---|
| Health | Liveness plus PostgreSQL, Redis, and object-storage readiness |
| Suppliers, products, warehouses | Create, list, and read canonical reference data |
| Inventory | Set and query inventory positions |
| Purchase orders and shipments | Create orders, shipments, and lifecycle events |
| Integration mappings | Upsert versioned partner product and location mappings |
| Supplier A and B | Queue authenticated JSON or CSV inventory imports |
| Imports | Read jobs, errors, attempts, and replay failed work |
| Carrier C | Receive authenticated, duplicate-safe shipment webhooks |
| Analytics | Run deterministic Pandas/Polars reconciliation and NumPy risk scenarios |
| Analytical results | Query persisted mismatches or stockout risks by run |
| Learning console | Overview, live guided import, lineage, pipeline manifests, analytics, and operations evidence |

## Use the Learning Operations UI

Open <http://127.0.0.1:8000/hub>. This is the main place to learn and
demonstrate the whole system without logging in:

- **How it works** gives the whole project a short, visual beginning-to-end
  story.
- **Follow an update** shows seven real scenes: the supplier message, checks,
  untouched copy, work ticket, worker, translation table, and final inventory.
- **Past Supplier Updates** answers what arrived, how it was translated, what
  changed, and whether anything went wrong.
- **Daily Processing** explains the larger Airflow/Spark path and teaches why
  Parquet groups data by column before showing a technical run receipt.
- **Calculations** fairly compares Pandas and Polars with the same data and five
  exact runs, while teaching NumPy stockout risk as a separate question.
- **System Health** explains what each status proves instead of relying on
  unexplained colors.
- **Learn the Pieces** is a searchable plain-English guide to every major
  technology and how it fits.

The browser talks only to FastAPI. It never receives PostgreSQL, Redis,
SeaweedFS, Airflow, or Prometheus credentials. The only mutation in the guided
flow creates clearly labeled synthetic learning records.

All business routes are under `/api/v1`. Inventory submissions and replay
require an `Idempotency-Key` and return `202 Accepted`. Immutable raw payloads
live in object storage; PostgreSQL stores their key, size, checksum, and
authoritative job state. Redis messages contain only the job UUID.

## Run the historical pipeline

```bash
make pipeline-up
make pipeline-seed
make pipeline-backfill
# after the three runs finish
make pipeline-pause
```

The Airflow UI is <http://127.0.0.1:8081>. The DAG checks each raw partition,
runs PySpark quality and risk transforms, writes warehouse-partitioned Parquet,
publishes an immutable success manifest, and verifies it. The DAG begins
paused; `pipeline-backfill` unpauses it so the scheduler can execute the queued
runs, and `pipeline-pause` prevents later dates from expecting synthetic data.
Airflow standalone mode is for local learning, not a claimed production
deployment.

## Run observability

```bash
make observability-up
```

- Prometheus: <http://127.0.0.1:9090>
- Grafana: <http://127.0.0.1:3000>
- Grafana local login: `admin` / `local-grafana-only`

Set `GRAFANA_ADMIN_PASSWORD` to replace the local password. The provisioned
`Supply Chain API Overview` dashboard shows request rate, p95 latency, and
in-progress requests.

## Development and verification

```bash
uv python install 3.12.12
uv sync --managed-python
make verify
make ui-check
make ui-build
make test-integration
make e2e
```

The integration suite uses a disposable PostgreSQL filesystem. The explicit
end-to-end proof requires the live core stack and crosses the API, partner
authentication, SeaweedFS, Redis, Celery worker, PostgreSQL, and final inventory
query.

Run the controlled Phase 4 benchmark with `make benchmark`. It proves equal
Pandas and Polars output before recording runtime and native DataFrame memory
evidence in `artifacts/phase4_benchmark.json`.

## Architecture at a glance

```text
Supplier JSON / CSV
    |
FastAPI -> raw payload in SeaweedFS + pointer/job in PostgreSQL
    |
job UUID in Redis
    |
Celery worker -> partner adapter -> canonical records and errors
    |
PostgreSQL snapshots, inventory, attempts, and terminal job state
    |
append-only operation events -> FastAPI learning APIs -> React /hub console

Celery beat -> queued-job redispatch + expired-lease recovery

historical CSV partitions in SeaweedFS
    |
Airflow DAG -> quality gate -> PySpark transform
    |
warehouse-partitioned Parquet + immutable success manifest

Pandas / Polars / NumPy -> PostgreSQL analytical runs and results

FastAPI /metrics -> Prometheus -> provisioned Grafana dashboard
```

Celery's result backend is disabled because PostgreSQL is authoritative. Phase
4 API analytics remain deliberately bounded; the Spark path owns historical
partition processing. Every Compose service has an explicit local CPU and
memory ceiling.

## Cost boundary

The project runs locally without cloud accounts, credit cards, paid trials, or
metered APIs. A paid service will never be introduced without an explicit
decision.
