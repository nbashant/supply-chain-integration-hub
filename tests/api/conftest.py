from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from supply_chain_hub.api.routes import health
from supply_chain_hub.application import integration_services
from supply_chain_hub.infrastructure.db import models  # noqa: F401
from supply_chain_hub.infrastructure.db.base import Base
from supply_chain_hub.infrastructure.db.session import get_db_session
from supply_chain_hub.infrastructure.object_storage import StoredObject
from supply_chain_hub.main import create_app


class MemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str,
        sha256: str,
    ) -> StoredObject:
        del content_type
        self.objects[key] = content
        return StoredObject(key=key, size_bytes=len(content), etag=sha256)

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def list_keys(self, prefix: str) -> list[str]:
        return sorted(key for key in self.objects if key.startswith(prefix))

    def is_available(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def object_store(
    monkeypatch: pytest.MonkeyPatch,
) -> MemoryObjectStore:
    store = MemoryObjectStore()
    monkeypatch.setattr(integration_services, "get_object_store", lambda: store)
    return store


@pytest.fixture
def api_session() -> Generator[Session, None, None]:
    test_engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    testing_session = sessionmaker(
        bind=test_engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )

    with testing_session() as session:
        yield session

    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def client(
    api_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        yield api_session

    application = create_app()
    application.dependency_overrides[get_db_session] = override_session
    monkeypatch.setattr(health, "redis_is_available", lambda: True)
    monkeypatch.setattr(health, "object_store_is_available", lambda: True)

    with TestClient(
        application,
        headers={"X-Partner-Token": "local-partner-token-change-me"},
    ) as test_client:
        yield test_client
