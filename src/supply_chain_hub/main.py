from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from supply_chain_hub.api.routes import (
    analytics,
    health,
    imports,
    integration_mappings,
    integrations,
    inventory,
    learning,
    products,
    purchase_orders,
    shipments,
    suppliers,
    warehouses,
)
from supply_chain_hub.domain.exceptions import (
    DomainValidationError,
    ResourceConflictError,
    ResourceNotFoundError,
    ResourceUnavailableError,
)
from supply_chain_hub.infrastructure.db.session import engine
from supply_chain_hub.infrastructure.observability import (
    configure_logging,
    install_observability,
)
from supply_chain_hub.settings.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.app_log_level)
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "A local study project for supply-chain domain modeling, "
            "integration, and reliability."
        ),
        lifespan=lifespan,
    )
    install_observability(application, settings)

    application.include_router(health.router)
    application.include_router(suppliers.router)
    application.include_router(products.router)
    application.include_router(warehouses.router)
    application.include_router(inventory.router)
    application.include_router(purchase_orders.router)
    application.include_router(shipments.router)
    application.include_router(integration_mappings.router)
    application.include_router(imports.router)
    application.include_router(integrations.router)
    application.include_router(analytics.router)
    application.include_router(learning.router)

    ui_directory = Path("ui/dist")
    ui_index = ui_directory / "index.html"
    ui_assets = ui_directory / "assets"
    if ui_assets.is_dir():
        application.mount(
            "/hub/assets",
            StaticFiles(directory=ui_assets),
            name="learning-console-assets",
        )

    @application.get("/hub", include_in_schema=False)
    @application.get("/hub/", include_in_schema=False)
    @application.get("/hub/{client_path:path}", include_in_schema=False)
    def learning_console(client_path: str = "") -> FileResponse:
        del client_path
        if not ui_index.is_file():
            raise HTTPException(
                status_code=503,
                detail=(
                    "The learning console has not been built. "
                    "Run 'cd ui && npm install && npm run build'."
                ),
            )
        return FileResponse(ui_index)

    @application.exception_handler(ResourceNotFoundError)
    async def not_found_handler(
        _: Request,
        error: ResourceNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "resource_not_found",
                    "message": str(error),
                }
            },
        )

    @application.exception_handler(ResourceConflictError)
    async def conflict_handler(
        _: Request,
        error: ResourceConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "resource_conflict",
                    "message": str(error),
                }
            },
        )

    @application.exception_handler(DomainValidationError)
    async def domain_validation_handler(
        _: Request,
        error: DomainValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "domain_validation_error",
                    "message": str(error),
                }
            },
        )

    @application.exception_handler(ResourceUnavailableError)
    async def unavailable_handler(
        _: Request,
        error: ResourceUnavailableError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "resource_unavailable",
                    "message": str(error),
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    async def request_validation_handler(
        _: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "request_validation_error",
                    "message": "The request did not match the API contract.",
                    "details": jsonable_encoder(error.errors()),
                }
            },
        )

    return application


app = create_app()
