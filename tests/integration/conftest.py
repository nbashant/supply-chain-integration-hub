import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

EXPECTED_TABLES = [
    "analytics_runs",
    "import_attempts",
    "import_errors",
    "import_jobs",
    "inventory_positions",
    "inventory_reconciliations",
    "inventory_snapshots",
    "operation_events",
    "products",
    "purchase_order_lines",
    "purchase_orders",
    "shipment_events",
    "shipments",
    "stockout_risks",
    "suppliers",
    "supplier_product_mappings",
    "supplier_warehouse_mappings",
    "warehouses",
]


@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine, None, None]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests.")

    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    engine = create_engine(database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def postgres_session(postgres_engine: Engine) -> Generator[Session, None, None]:
    session_factory = sessionmaker(
        bind=postgres_engine,
        class_=Session,
        expire_on_commit=False,
    )
    with session_factory() as session:
        yield session
        session.rollback()

    table_names = ", ".join(EXPECTED_TABLES)
    with postgres_engine.begin() as connection:
        connection.execute(
            text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
        )
