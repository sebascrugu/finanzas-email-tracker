# Makefile para facilitar comandos comunes del proyecto

.PHONY: help install dev-install test coverage lint format type-check clean run-dashboard run-fetch init-db migrate seed income balance

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

income: ## Gestiona tus ingresos (agregar, listar, balance)
	poetry run python scripts/manage_income.py

balance: ## Muestra el balance rápido del mes actual
	poetry run python scripts/quick_balance.py

init-db: ## Inicializa la base de datos
	@echo "$(BLUE)Inicializando base de datos...$(NC)"
	@mkdir -p data logs
	@poetry run alembic upgrade head || echo "$(BLUE)Alembic aún no configurado, continuando...$(NC)"

setup: dev-install init-db ## Setup completo del proyecto
	@echo "$(BLUE)¡Setup completado!$(NC)"
	@echo "$(BLUE)Siguiente paso: Copia .env.example a .env y configura tus credenciales$(NC)"

all: format lint type-check test ## Ejecuta todas las verificaciones

.DEFAULT_GOAL := help


