# ============================================
# Library API - Makefile
# ============================================

.PHONY: help up down logs restart db-logs redis-logs install dev test format lint clean

# Default target
help:
	@echo "Comandos disponíveis:"
	@echo "  make up        - Sobe containers (postgres + redis)"
	@echo "  make down      - Para e remove containers"
	@echo "  make logs      - Mostra logs de todos os containers"
	@echo "  make restart   - Reinicia containers"
	@echo "  make db-logs   - Mostra logs do PostgreSQL"
	@echo "  make redis-logs- Mostra logs do Redis"
	@echo "  make install   - Instala dependências do backend"
	@echo "  make dev       - Roda servidor de desenvolvimento"
	@echo "  make test      - Roda testes"
	@echo "  make format    - Formata código com black e isort"
	@echo "  make lint      - Verifica código com ruff"
	@echo "  make clean     - Remove arquivos temporários"

# ============================================
# Docker
# ============================================

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose restart

db-logs:
	docker compose logs -f postgres

redis-logs:
	docker compose logs -f redis

# ============================================
# Backend
# ============================================

install:
	cd backend && pip install -e ".[dev]"

dev:
	cd backend && uvicorn app.main:app --reload --port 8000

test:
	cd backend && pytest tests/ -v

format:
	cd backend && black app tests && isort app tests

lint:
	cd backend && ruff check app tests

# ============================================
# Cleanup
# ============================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
