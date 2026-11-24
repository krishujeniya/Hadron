.PHONY: help dev dev-backend dev-frontend test test-backend test-frontend lint lint-backend lint-frontend build build-backend build-frontend docker-up docker-down clean

help:
	@echo "Hadron Monorepo Developer Commands:"
	@echo "  make dev           - Start both backend and frontend development servers"
	@echo "  make dev-backend   - Start FastAPI backend with hot reloading"
	@echo "  make dev-frontend  - Start Next.js frontend development server"
	@echo "  make test          - Run all backend and frontend tests"
	@echo "  make test-backend  - Run backend pytest suite"
	@echo "  make test-frontend - Run frontend test suites"
	@echo "  make lint          - Run ruff and TypeScript typechecks"
	@echo "  make build         - Build production container and Next.js static output"
	@echo "  make docker-up     - Launch full local stack via Docker Compose"
	@echo "  make docker-down   - Stop local Docker Compose services"
	@echo "  make clean         - Remove transient build caches and artifacts"

dev:
	@echo "Starting full development environment..."
	@make -j 2 dev-backend dev-frontend

dev-backend:
	cd backend && uvicorn main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	uv run --locked python -m pytest tests/ -v -m "not eval"

test-frontend:
	cd frontend && npm run build:pages

lint: lint-backend lint-frontend

lint-backend:
	uv run --locked ruff check backend/ tests/
	python3 -m py_compile backend/main.py

lint-frontend:
	cd frontend && npm run lint

build: build-backend build-frontend

build-backend:
	docker build -f deploy/docker/backend.Dockerfile -t hadron-backend:latest .

build-frontend:
	cd frontend && npm run build

docker-up:
	docker compose -f deploy/docker-compose.yml up -d

docker-down:
	docker compose -f deploy/docker-compose.yml down

clean:
	rm -rf .pytest_cache htmlcov .coverage .ruff_cache frontend/.next frontend/out frontend/node_modules/.cache
