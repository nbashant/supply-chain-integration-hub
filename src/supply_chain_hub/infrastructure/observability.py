from __future__ import annotations

import contextvars
import json
import logging
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.trustedhost import TrustedHostMiddleware

from supply_chain_hub.settings.config import Settings

CORRELATION_ID_HEADER = "X-Correlation-ID"
_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id",
    default="-",
)

REQUESTS = Counter(
    "supply_chain_http_requests_total",
    "Completed HTTP requests.",
    ["method", "route", "status"],
)
REQUEST_DURATION = Histogram(
    "supply_chain_http_request_duration_seconds",
    "HTTP request duration.",
    ["method", "route"],
)
REQUESTS_IN_PROGRESS = Gauge(
    "supply_chain_http_requests_in_progress",
    "HTTP requests currently being handled.",
)


def current_correlation_id() -> str | None:
    """Return the request trace identifier when called inside an HTTP request."""
    value = _correlation_id.get()
    return None if value == "-" else value


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": _correlation_id.get(),
        }
        for field in ("method", "path", "status_code", "duration_ms"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").disabled = True


def _request_route(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return str(path) if path else request.url.path


def install_observability(application: FastAPI, settings: Settings) -> None:
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_host_list,
    )

    @application.middleware("http")
    async def observe_request(request: Request, call_next: Any) -> Response:
        supplied_id = request.headers.get(CORRELATION_ID_HEADER, "")
        correlation_id = (
            supplied_id
            if _SAFE_CORRELATION_ID.fullmatch(supplied_id)
            else str(uuid.uuid4())
        )
        token = _correlation_id.set(correlation_id)
        started = time.perf_counter()
        REQUESTS_IN_PROGRESS.inc()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration = time.perf_counter() - started
            route = _request_route(request)
            status_code = response.status_code if response is not None else 500
            REQUESTS.labels(request.method, route, str(status_code)).inc()
            REQUEST_DURATION.labels(request.method, route).observe(duration)
            REQUESTS_IN_PROGRESS.dec()
            if response is not None:
                response.headers[CORRELATION_ID_HEADER] = correlation_id
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["Referrer-Policy"] = "no-referrer"
                response.headers["Cache-Control"] = "no-store"
            logging.getLogger("supply_chain_hub.http").info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": route,
                    "status_code": status_code,
                    "duration_ms": round(duration * 1000, 3),
                },
            )
            _correlation_id.reset(token)

    @application.get(
        "/metrics",
        include_in_schema=False,
        response_class=Response,
    )
    def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
