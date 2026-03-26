# Multi-stage production image
FROM python:3.12-slim AS builder

WORKDIR /build

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml .
COPY src/ src/

# Install dependencies into /build/.venv
RUN uv sync --no-dev --all-extras

FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /build/.venv /app/.venv

# Copy source code
COPY src/ src/
COPY langgraph.json .

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "agent_framework.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
