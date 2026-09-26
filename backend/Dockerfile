# syntax=docker/dockerfile:1

# CandleStack backend. The dependencies are installed with uv into a venv on the same Python
# image the app runs on. The runtime image gets that venv and the app's source as separate
# layers, so a new commit ships only the small source layer and the dependency layer is pulled
# again only when uv.lock changes. Build context: backend/.
#   docker build -t candlestack-backend --build-arg APP_COMMIT=$(git rev-parse HEAD) backend

FROM ghcr.io/astral-sh/uv:0.11 AS uv

# The dependencies alone: this stage is reused until pyproject.toml or uv.lock change.
FROM python:3.13-slim AS deps
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-dev --no-install-project

# Local development only (compose.dev.yaml): dev dependencies, the project installed editable
# so the mounted src/ is what runs, granian with --reload.
FROM deps AS dev
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked
COPY granian-logging.json ./
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", \
     "--no-access-log", "--log-config", "granian-logging.json", "--reload", \
     "--reload-paths", "src", "candlestack.main:app"]

# The app runs from /app/src on PYTHONPATH, next to the dependencies' venv.
FROM python:3.13-slim
WORKDIR /app
COPY --from=deps /app/.venv /app/.venv
COPY granian-logging.json ./
COPY src ./src
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# Runs unprivileged and needs no writable path: fine with a read-only root filesystem.
USER 65534:65534
EXPOSE 8000
ARG APP_COMMIT=unknown
ENV APP_COMMIT=$APP_COMMIT
CMD ["granian", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000", \
     "--no-access-log", "--log-config", "granian-logging.json", "candlestack.main:app"]
