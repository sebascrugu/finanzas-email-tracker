"""FastAPI Application - Finanzas Tracker CR.

API REST para gestión de finanzas personales en Costa Rica.
Soporta SINPE Móvil, BAC, Banco Popular y más.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finanzas_tracker.api.errors import setup_exception_handlers
from finanzas_tracker.api.middleware import setup_middlewares
from finanzas_tracker.api.routers import (
    ai,
    auth,
    budgets,
    cards,
    categories,
    expenses,
    notifications,
    onboarding,
    patrimony,
    profiles,
    reconciliation,
    statements,
    subscriptions,
    transactions,
)
from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.services.embedding_events import (
    register_embedding_events,
    start_embedding_worker,
    stop_embedding_worker,
)
from finanzas_tracker.services.sync_scheduler import (
    start_background_tasks,
    stop_background_tasks,
)


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager para startup/shutdown."""
    # Startup
    logger.info("🚀 Iniciando Finanzas Tracker API...")

    # Registrar eventos de auto-embeddings
    register_embedding_events()
    start_embedding_worker()
    logger.info("✅ Sistema de auto-embeddings activado")

    # Iniciar tareas de fondo (sync emails, card alerts, etc.)
    start_background_tasks()
    logger.info("✅ Tareas de fondo programadas")

    yield

    # Shutdown
    logger.info("🛑 Deteniendo Finanzas Tracker API...")
    stop_background_tasks()
    logger.info("✅ Tareas de fondo detenidas")
    stop_embedding_worker()
    logger.info("✅ API detenida correctamente")


app = FastAPI(
    title="Finanzas Tracker CR API",
    description="""
## 🇨🇷 API de Finanzas Personales para Costa Rica

Primera aplicación que soporta:
- **SINPE Móvil** - Sistema de pagos instantáneos
- **BAC Credomatic** - Parsing de correos y PDFs
- **Banco Popular** - Parsing de correos

### Características:
- 📊 Presupuesto 50/30/20 (necesidades/gustos/ahorros)
- 🤖 Categorización automática con AI (Claude)
- 🔍 **Búsqueda semántica con RAG** (pgvector)
- 💬 **Chat inteligente** con contexto de transacciones
- 📈 Análisis de gastos y tendencias
- 🏪 Normalización de comercios
- 💱 Conversión USD/CRC automática

### Autenticación
Por ahora la API es de uso local. Autenticación OAuth2 próximamente.
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configurar manejo global de errores
setup_exception_handlers(app)

# Configurar middlewares (Correlation ID, Request Logging)
setup_middlewares(app)

# CORS - permitir frontend local
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React/Next.js
        "http://localhost:8501",  # Streamlit
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(onboarding.router, prefix="/api/v1", tags=["Onboarding"])
app.include_router(transactions.router, prefix="/api/v1", tags=["Transactions"])
app.include_router(categories.router, prefix="/api/v1", tags=["Categories"])
app.include_router(budgets.router, prefix="/api/v1", tags=["Budgets"])
app.include_router(profiles.router, prefix="/api/v1", tags=["Profiles"])
app.include_router(patrimony.router, prefix="/api/v1", tags=["Patrimonio"])
app.include_router(cards.router, prefix="/api/v1", tags=["Tarjetas"])
app.include_router(notifications.router, prefix="/api/v1", tags=["Notificaciones"])
app.include_router(statements.router, prefix="/api/v1", tags=["Estados de Cuenta"])
app.include_router(reconciliation.router, prefix="/api/v1", tags=["Reconciliación"])
app.include_router(subscriptions.router, prefix="/api/v1", tags=["Suscripciones"])
app.include_router(expenses.router, prefix="/api/v1", tags=["Gastos Proyectados"])
app.include_router(ai.router, prefix="/api/v1", tags=["AI & RAG"])


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint con información del API."""
    return {
        "name": "Finanzas Tracker CR API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "database": "postgresql",
        "environment": settings.environment,
    }
