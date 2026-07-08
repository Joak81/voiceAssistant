FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY webhooks ./webhooks

# O Railway injeta a porta em $PORT; localmente usa 8000.
# exec: o uvicorn substitui o sh e recebe o SIGTERM do Railway diretamente.
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn webhooks.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
