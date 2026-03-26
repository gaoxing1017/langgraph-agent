.PHONY: install dev studio lint format typecheck test test-unit test-integration docker-up docker-down migrate

install:
	uv sync --all-extras

dev:
	uv run uvicorn agent_framework.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000

studio:
	uv run langgraph dev

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

typecheck:
	uv run mypy src/

test:
	uv run pytest tests/ -v

test-unit:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

migrate:
	uv run alembic upgrade head

docker-up:
	docker-compose -f docker/docker-compose.yml up -d

docker-down:
	docker-compose -f docker/docker-compose.yml down

bootstrap:
	bash scripts/bootstrap.sh
