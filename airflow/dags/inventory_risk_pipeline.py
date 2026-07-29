from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

with DAG(
    dag_id="inventory_risk_daily",
    description="Validate raw inventory and publish curated risk Parquet data.",
    schedule="@daily",
    start_date=datetime(2026, 7, 25, tzinfo=UTC),
    catchup=False,
    is_paused_upon_creation=True,
    max_active_runs=1,
    default_args={
        "owner": "supply-chain-data-platform",
        "retries": 1,
        "retry_delay": timedelta(seconds=10),
    },
    tags=["supply-chain", "inventory", "pyspark"],
) as dag:
    check_source = BashOperator(
        task_id="check_raw_partition",
        bash_command=(
            "python /opt/airflow/pipelines/historical_inventory.py "
            "check-source --partition-date '{{ ds }}'"
        ),
    )
    transform = BashOperator(
        task_id="transform_with_pyspark",
        bash_command=(
            "python /opt/airflow/pipelines/historical_inventory.py "
            "run --partition-date '{{ ds }}' --run-id '{{ run_id }}'"
        ),
        execution_timeout=timedelta(minutes=15),
    )
    verify = BashOperator(
        task_id="verify_published_manifest",
        bash_command=(
            "python /opt/airflow/pipelines/historical_inventory.py "
            "verify --partition-date '{{ ds }}' --run-id '{{ run_id }}'"
        ),
    )

    check_source >> transform >> verify
