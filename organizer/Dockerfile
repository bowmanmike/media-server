# Builder stage: use uv image with Python preinstalled
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Copy dependency metadata first for cache
COPY pyproject.toml ./

# Install deps into /app/.venv (no project code yet)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen --no-install-project || uv sync --no-dev

# Copy app code and install project
COPY organize_media.py ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Runtime image: slim Python only
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"

# Defaults (overridden by docker-compose)
ENV DOWNLOADS_DIR=/downloads/complete
ENV MOVIES_DIR=/media/movies
ENV TV_DIR=/media/tv
ENV SLEEP_SECONDS=300

CMD ["organize-media"]
