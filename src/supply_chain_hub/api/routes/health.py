from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from supply_chain_hub.api.dependencies import DatabaseSession
from supply_chain_hub.infrastructure.object_storage import (
    object_store_is_available,
)
from supply_chain_hub.infrastructure.redis_client import redis_is_available

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready", response_model=None)
def ready(session: DatabaseSession) -> dict[str, str] | JSONResponse:
    database_available = True
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_available = False
    redis_available = redis_is_available()
    object_storage_available = object_store_is_available()
    if not database_available or not redis_available or not object_storage_available:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "dependencies": {
                    "database": ("available" if database_available else "unavailable"),
                    "redis": "available" if redis_available else "unavailable",
                    "object_storage": (
                        "available" if object_storage_available else "unavailable"
                    ),
                },
            },
        )
    return {
        "status": "ready",
        "database": "available",
        "redis": "available",
        "object_storage": "available",
    }
