#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing dependencies..."
uv sync --all-extras

echo "==> Copying .env.example to .env (if not exists)..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "    Created .env from .env.example. Please fill in your credentials."
fi

echo "==> Running database migrations..."
uv run alembic upgrade head

echo "==> Bootstrap complete!"
