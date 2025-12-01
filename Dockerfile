# =============================================================================
# Dockerfile - Finanzas Tracker CR API
# Multi-stage build para imagen ligera
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder - Instala dependencias
# ---------------------------------------------------------------------------
FROM python:3.11-slim as builder

WORKDIR /app

# Instalar Poetry
ENV POETRY_VERSION=1.8.2 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir poetry==$POETRY_VERSION
ENV PATH="$POETRY_HOME/bin:$PATH"

# Copiar archivos de dependencias
COPY pyproject.toml poetry.lock ./

# Instalar dependencias (sin dev)
RUN poetry install --only=main --no-root

# ---------------------------------------------------------------------------
# Stage 2: Runtime - Imagen final ligera
# ---------------------------------------------------------------------------
FROM python:3.11-slim as runtime

WORKDIR /app

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:$PATH"

# Instalar dependencias del sistema para psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copiar virtualenv desde builder
COPY --from=builder /app/.venv .venv

# Copiar código fuente
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

# Crear usuario no-root
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Puerto de la API
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Comando para iniciar
CMD ["uvicorn", "finanzas_tracker.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
