# Makefile para facilitar comandos comunes del proyecto

.PHONY: help install dev-install test coverage lint format type-check clean run-dashboard run-fetch init-db migrate seed income balance db-migrate db-upgrade db-downgrade db-current db-history migrate-tokens

# Colores para output
BLUE := \033[0;34m
NC := \033[0m # No Color

help: ## Muestra esta ayuda
	@echo "$(BLUE)Comandos disponibles:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Instala dependencias de producción
	poetry install --without dev

dev-install: ## Instala todas las dependencias (incluyendo dev)
	poetry install

test: ## Ejecuta todos los tests
	poetry run pytest

coverage: ## Ejecuta tests con reporte de cobertura
	poetry run pytest --cov=finanzas_tracker --cov-report=html --cov-report=term-missing
	@echo "$(BLUE)Abre htmlcov/index.html para ver el reporte completo$(NC)"

lint: ## Verifica el código con ruff
	poetry run ruff check .

format: ## Formatea el código automáticamente
	poetry run ruff format .
	poetry run ruff check --fix .

type-check: ## Verifica tipos con mypy
	poetry run mypy src/

clean: ## Limpia archivos temporales y cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/
	@echo "$(BLUE)Limpieza completada$(NC)"

dashboard: ## Inicia el dashboard web de Streamlit (interfaz principal)
	poetry run streamlit run src/finanzas_tracker/dashboard/app.py

run-dashboard: ## Alias de 'dashboard'
	@make dashboard

run-fetch: ## Ejecuta el script de extracción de correos
	poetry run python scripts/fetch_emails.py

process: ## Procesa transacciones desde correos y las guarda en la base de datos
	poetry run python scripts/process_transactions.py

review: ## Revisa y categoriza transacciones pendientes interactivamente
	poetry run python scripts/review_transactions.py

setup-user: ## Configura un nuevo usuario (email, salario, tarjetas)
	poetry run python scripts/setup_user.py

migrate: ## Migra la base de datos al nuevo schema (⚠️  BORRA TODOS LOS DATOS)
	poetry run python scripts/migrate_db.py

seed: ## Pobla la base de datos con categorías iniciales
	@echo "$(BLUE)Poblando categorías...$(NC)"
	@poetry run python -c "from finanzas_tracker.utils.seed_categories import seed_categories; seed_categories()"
	@echo "$(BLUE)¡Categorías pobladas exitosamente!$(NC)"

logout: ## Cierra sesión y limpia el cache de tokens
	poetry run python scripts/logout.py

migrate-tokens: ## Migra tokens del archivo antiguo al keyring del sistema (solo una vez)
	@echo "$(BLUE)Migrando tokens al keyring del sistema...$(NC)"
	poetry run python scripts/migrate_token_cache.py

income: ## Gestiona tus ingresos (agregar, listar, balance)
	poetry run python scripts/manage_income.py

balance: ## Muestra el balance rápido del mes actual
	poetry run python scripts/quick_balance.py

train-anomaly: ## Entrena el detector de anomalías con datos históricos (ML)
	poetry run python scripts/train_anomaly_detector.py

detect-subscriptions: ## Detecta suscripciones recurrentes en transacciones
	poetry run python scripts/detect_subscriptions.py

init-db: ## Inicializa la base de datos
	@echo "$(BLUE)Inicializando base de datos...$(NC)"
	@mkdir -p data logs
	@poetry run alembic upgrade head

db-migrate: ## Crea una nueva migración de base de datos (uso: make db-migrate MSG="descripción")
	@if [ -z "$(MSG)" ]; then \
		echo "$(BLUE)Error: Debes especificar un mensaje. Ejemplo: make db-migrate MSG='add user table'$(NC)"; \
		exit 1; \
	fi
	poetry run alembic revision --autogenerate -m "$(MSG)"

db-upgrade: ## Aplica todas las migraciones pendientes
	@echo "$(BLUE)Aplicando migraciones...$(NC)"
	poetry run alembic upgrade head
	@echo "$(BLUE)Migraciones aplicadas$(NC)"

db-downgrade: ## Revierte la última migración
	@echo "$(BLUE)Revirtiendo última migración...$(NC)"
	poetry run alembic downgrade -1
	@echo "$(BLUE)Migración revertida$(NC)"

db-current: ## Muestra la versión actual de la base de datos
	poetry run alembic current

db-history: ## Muestra el historial de migraciones
	poetry run alembic history

setup: dev-install init-db ## Setup completo del proyecto
	@echo "$(BLUE)¡Setup completado!$(NC)"
	@echo "$(BLUE)Siguiente paso: Copia .env.example a .env y configura tus credenciales$(NC)"

# =============================================================================
# DOCKER / PostgreSQL
# =============================================================================
# Usar 'docker compose' (nuevo) como comando predeterminado
DC := docker compose

db-up: ## Levanta PostgreSQL con Docker (pgvector incluido)
	@echo "$(BLUE)🐘 Levantando PostgreSQL...$(NC)"
	$(DC) up -d db
	@sleep 3
	@echo "$(BLUE)✅ PostgreSQL corriendo en localhost:5432$(NC)"
	@echo "$(BLUE)💡 Tip: Agrega USE_POSTGRES=true a tu .env$(NC)"

db-down: ## Detiene los contenedores de Docker
	@echo "$(BLUE)🛑 Deteniendo contenedores...$(NC)"
	$(DC) down
	@echo "$(BLUE)✅ Contenedores detenidos$(NC)"

db-reset: ## Reinicia PostgreSQL (⚠️ BORRA TODOS LOS DATOS)
	@echo "$(BLUE)⚠️  Esto borrará todos los datos. Ctrl+C para cancelar...$(NC)"
	@sleep 3
	$(DC) down -v
	$(DC) up -d db
	@sleep 5
	poetry run alembic upgrade head
	@echo "$(BLUE)✅ Base de datos reiniciada$(NC)"

db-logs: ## Muestra logs de PostgreSQL
	$(DC) logs -f db

db-shell: ## Abre psql en el contenedor de PostgreSQL
	$(DC) exec db psql -U finanzas -d finanzas_tracker

db-admin: ## Levanta pgAdmin (interfaz web para PostgreSQL)
	@echo "$(BLUE)🌐 Levantando pgAdmin...$(NC)"
	$(DC) --profile tools up -d pgadmin
	@echo "$(BLUE)✅ pgAdmin en http://localhost:5050$(NC)"
	@echo "$(BLUE)   Email: admin@finanzas.local | Password: admin123$(NC)"

# =============================================================================
# API FastAPI
# =============================================================================
api: ## Levanta la API FastAPI en modo desarrollo
	@echo "$(BLUE)🚀 Iniciando FastAPI en http://localhost:8000...$(NC)"
	poetry run uvicorn finanzas_tracker.api.main:app --reload --host 0.0.0.0 --port 8000

# =============================================================================
# UTILIDADES
# =============================================================================
shell: ## Abre un shell de Python con el contexto del proyecto
	@echo "$(BLUE)🐍 Abriendo shell interactivo...$(NC)"
	poetry run python -i -c "from finanzas_tracker.core.database import get_session, Base, engine; from finanzas_tracker.models import *; print('✅ Modelos cargados. Usa get_session() para DB.')"

parse-pdfs: ## Parsea todos los PDFs de BAC en data/raw/bac_pdf/
	@echo "$(BLUE)📄 Parseando PDFs de BAC...$(NC)"
	poetry run python -c "from finanzas_tracker.parsers import BACPDFParser; p = BACPDFParser(); results = p.parse_directory('data/raw/bac_pdf'); print(f'✅ {sum(len(r.transactions) for r in results)} transacciones extraídas')"

all: format lint type-check test ## Ejecuta todas las verificaciones

.DEFAULT_GOAL := help


