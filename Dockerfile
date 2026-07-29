FROM ghcr.io/astral-sh/uv:0.10.5 AS uv

FROM node:22-alpine AS learning-ui

WORKDIR /ui

COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui ./
RUN npm run build

FROM python:3.12.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --create-home app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests
COPY --from=learning-ui /ui/dist ./ui/dist

RUN uv sync --frozen \
    && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn supply_chain_hub.main:app --host 0.0.0.0 --port 8000"]
