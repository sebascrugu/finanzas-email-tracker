# Guía de Implementación para AI Assistants
## Sistema de Prompts y Agentes para Cursor/Copilot

**Versión:** 1.0  
**Para:** Uso con Cursor, GitHub Copilot, Claude Code, o cualquier AI coding assistant  
**Modelo recomendado:** Claude Opus 4.5 o equivalente

---

## Cómo Usar Esta Guía

### Estructura de Archivos Recomendada

Crear estos archivos en tu proyecto para dar contexto a los AI assistants:

```
tu-proyecto/
├── .cursorrules              # Reglas globales para Cursor
├── docs/
│   ├── ARCHITECTURE.md       # Arquitectura del proyecto
│   ├── CONVENTIONS.md        # Convenciones de código
│   └── prompts/              # Prompts por fase
│       ├── phase-0-prep.md
│       ├── phase-1-foundation.md
│       ├── phase-2-api.md
│       ├── phase-3-rag.md
│       ├── phase-4-mcp.md
│       ├── phase-5-parsers.md
│       └── phase-6-deploy.md
└── ...
```

### Flujo de Trabajo Recomendado

1. **Antes de cada sesión**: Copiar el contexto relevante (arquitectura, convenciones, fase actual)
2. **Un objetivo por sesión**: No mezclar tareas de diferentes fases
3. **Validar output**: Correr tests/lint después de cada cambio significativo
4. **Commits frecuentes**: Commitear antes de pedir cambios grandes
5. **Iterar**: Si el output no es correcto, dar feedback específico

---

## Archivos de Contexto Base

### Archivo: .cursorrules (o equivalente)

```
# Finanzas Tracker - Reglas para AI Assistants

## Proyecto
Sistema de finanzas personales para Costa Rica con AI.
Stack: Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL + pgvector, Streamlit.

## Convenciones de Código

### Python
- Type hints SIEMPRE (usar `str | None` no `Optional[str]`)
- Docstrings en Google style
- Nombres de variables/funciones en snake_case
- Nombres de clases en PascalCase
- Máximo 100 caracteres por línea
- Imports ordenados: stdlib, third-party, local

### SQLAlchemy
- Usar SQLAlchemy 2.0 style (select() no query())
- Modelos heredan de Base declarativa
- Soft delete con deleted_at, nunca DELETE real
- tenant_id en todas las tablas (UUID, nullable por ahora)

### FastAPI
- Versionar endpoints: /api/v1/...
- Schemas separados: Create, Update, Response
- Dependency injection para DB session
- HTTPException con detail estructurado

### Tests
- pytest con fixtures
- Mocks para APIs externas (Claude, email)
- Tests unitarios en tests/unit/
- Tests de integración en tests/integration/
- Target: 80% coverage en services/

## Estructura de Carpetas
```
src/
├── api/           # FastAPI endpoints
├── core/          # Config, constants
├── models/        # SQLAlchemy models
├── schemas/       # Pydantic schemas
├── services/      # Business logic
├── parsers/       # Bank/SINPE parsers
├── mcp/           # MCP server
└── utils/         # Helpers
```

## NO Hacer
- No usar print(), usar logging
- No hardcodear secrets
- No queries SQL raw (siempre ORM)
- No ignorar type errors
- No commitear código sin tests para lógica de negocio

## Contexto de Dominio
- CRC = Colones costarricenses
- SINPE = Sistema de pagos instantáneos de Costa Rica
- BAC = BAC Credomatic (banco más grande de CR)
- 50/30/20 = Metodología de presupuesto (necesidades/gustos/ahorros)
```

---

### Archivo: docs/ARCHITECTURE.md

```markdown
# Arquitectura de Finanzas Tracker

## Vista General

```
┌─────────────────────────────────────────────────────────────────┐
│                     ARQUITECTURA                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ENTRADA DE DATOS          PROCESAMIENTO         ALMACENAMIENTO │
│  ┌─────────────┐          ┌─────────────┐       ┌────────────┐ │
│  │ SMS SINPE   │────┐     │  Parsers    │       │ PostgreSQL │ │
│  │ Emails BAC  │────┼────▶│  Services   │──────▶│ + pgvector │ │
│  │ PDFs        │────┤     │  AI Claude  │       │            │ │
│  │ Manual      │────┘     └──────┬──────┘       └────────────┘ │
│                                  │                              │
│                                  ▼                              │
│  INTERFACES                 ┌─────────────┐                    │
│  ┌─────────────┐           │  FastAPI    │                    │
│  │ Streamlit   │◀──────────│  REST API   │                    │
│  │ MCP Server  │◀──────────│             │                    │
│  │ CLI Scripts │◀──────────│             │                    │
│  └─────────────┘           └─────────────┘                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Componentes Principales

### 1. Capa de Datos (PostgreSQL + pgvector)
- **transactions**: Transacciones financieras con embeddings
- **categories**: Categorías y subcategorías (50/30/20)
- **budgets**: Presupuestos mensuales por categoría
- **incomes**: Ingresos (salario, freelance, etc.)
- **profiles**: Usuarios/perfiles (multi-tenant ready)

### 2. Capa de Servicios
- **TransactionService**: CRUD de transacciones
- **CategorizationService**: Lógica 3-tier (keywords → histórico → Claude)
- **BudgetService**: Cálculos de presupuesto 50/30/20
- **AnalyticsService**: Estadísticas y tendencias
- **RAGService**: Búsqueda semántica y generación de respuestas
- **EmbeddingService**: Generación de embeddings

### 3. Capa de Parsers
- **SINPESMSParser**: SMS de SINPE Móvil
- **BACEmailParser**: Emails de BAC Credomatic
- **BACPDFParser**: Estados de cuenta PDF

### 4. Capa de API
- **FastAPI**: REST API versión v1
- **MCP Server**: Model Context Protocol para Claude Desktop

### 5. Capa de Presentación
- **Streamlit**: Dashboard web (13 páginas)

## Flujo de Datos

### Crear Transacción desde SMS SINPE
```
SMS → SINPESMSParser.parse() → ParsedTransaction
    → CategorizationService.categorize()
    → TransactionService.create()
    → EmbeddingService.embed()
    → PostgreSQL
```

### Query RAG
```
Pregunta → EmbeddingService.embed_query()
        → pgvector similarity search
        → Top 20 transacciones
        → RAGService.build_context()
        → Claude API
        → Respuesta
```

## Decisiones de Arquitectura

| Decisión | Alternativa | Por qué esta opción |
|----------|-------------|---------------------|
| pgvector | ChromaDB | Una sola DB, ACID, más simple |
| FastAPI | Flask | Async, type hints, OpenAPI |
| Streamlit | React | Más rápido para MVP data-heavy |
| SQLAlchemy 2.0 | Raw SQL | ORM seguro, migraciones |
| tenant_id now | Agregar después | Evita migración masiva futura |
```

---

### Archivo: docs/CONVENTIONS.md

```markdown
# Convenciones de Código

## Estructura de un Archivo Python

```python
"""
Docstring del módulo explicando qué hace.
"""
# Imports stdlib
from datetime import datetime
from decimal import Decimal

# Imports third-party
from sqlalchemy import Column, String
from pydantic import BaseModel

# Imports locales
from src.core.config import settings
from src.models.base import Base


# Constantes
DEFAULT_LIMIT = 100


# Clases/Funciones
class MyService:
    """Docstring de la clase."""
    
    def my_method(self, param: str) -> dict:
        """
        Docstring del método.
        
        Args:
            param: Descripción del parámetro.
            
        Returns:
            Descripción del retorno.
            
        Raises:
            ValueError: Cuando param es inválido.
        """
        pass
```

## Naming Conventions

```python
# Variables y funciones: snake_case
transaction_count = 10
def calculate_total() -> Decimal:
    pass

# Clases: PascalCase
class TransactionService:
    pass

# Constantes: UPPER_SNAKE_CASE
MAX_TRANSACTIONS = 1000

# Privados: _prefijo
def _internal_helper():
    pass

# Archivos: snake_case.py
# transaction_service.py, not TransactionService.py
```

## Modelos SQLAlchemy

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.models.base import Base


class Transaction(Base):
    """Transacción financiera."""
    
    __tablename__ = "transactions"
    
    # PK
    id = Column(Integer, primary_key=True)
    
    # Multi-tenancy (siempre incluir)
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Campos de negocio
    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(String(500), nullable=False)
    date = Column(DateTime, nullable=False)
    
    # FKs
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    
    # Relationships
    category = relationship("Category", back_populates="transactions")
    
    # Soft delete
    deleted_at = Column(DateTime, nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def soft_delete(self) -> None:
        """Marca como eliminado sin borrar."""
        self.deleted_at = datetime.utcnow()
```

## Schemas Pydantic

```python
from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal
from datetime import datetime


# Schema de creación (input)
class TransactionCreate(BaseModel):
    amount: Decimal = Field(..., description="Monto de la transacción")
    description: str = Field(..., max_length=500)
    date: datetime
    category_id: int | None = None


# Schema de actualización (input, todo opcional)
class TransactionUpdate(BaseModel):
    amount: Decimal | None = None
    description: str | None = Field(None, max_length=500)
    category_id: int | None = None


# Schema de respuesta (output)
class TransactionResponse(BaseModel):
    id: int
    amount: Decimal
    description: str
    date: datetime
    category: "CategoryResponse | None"
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
```

## Endpoints FastAPI

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.schemas.transaction import TransactionCreate, TransactionResponse
from src.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/", response_model=list[TransactionResponse])
def list_transactions(
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(100, ge=1, le=500, description="Máximo de registros"),
    db: Session = Depends(get_db),
):
    """
    Lista transacciones con paginación.
    
    - **skip**: Número de registros a saltar (para paginación)
    - **limit**: Máximo de registros a retornar
    """
    service = TransactionService(db)
    return service.list(skip=skip, limit=limit)


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    data: TransactionCreate,
    db: Session = Depends(get_db),
):
    """Crea una nueva transacción."""
    service = TransactionService(db)
    return service.create(data)


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
):
    """Obtiene una transacción por ID."""
    service = TransactionService(db)
    transaction = service.get(transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Transaction not found", "code": "TXN_NOT_FOUND"}
        )
    return transaction
```

## Tests

```python
import pytest
from decimal import Decimal
from datetime import datetime

from src.services.transaction_service import TransactionService
from src.schemas.transaction import TransactionCreate


class TestTransactionService:
    """Tests para TransactionService."""
    
    def test_create_transaction(self, db_session, sample_category):
        """Debe crear transacción correctamente."""
        # Arrange
        service = TransactionService(db_session)
        data = TransactionCreate(
            amount=Decimal("10000"),
            description="Test transaction",
            date=datetime.now(),
            category_id=sample_category.id,
        )
        
        # Act
        result = service.create(data)
        
        # Assert
        assert result.id is not None
        assert result.amount == Decimal("10000")
        assert result.category_id == sample_category.id
    
    def test_create_transaction_without_category(self, db_session):
        """Debe crear transacción sin categoría."""
        service = TransactionService(db_session)
        data = TransactionCreate(
            amount=Decimal("-5000"),
            description="Uncategorized",
            date=datetime.now(),
        )
        
        result = service.create(data)
        
        assert result.category_id is None


# Fixtures en conftest.py
@pytest.fixture
def db_session():
    """Session de DB para tests."""
    # Setup
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    # Teardown
    session.rollback()
    session.close()


@pytest.fixture
def sample_category(db_session):
    """Categoría de ejemplo."""
    category = Category(name="Test Category", type="needs")
    db_session.add(category)
    db_session.commit()
    return category
```
```

---

## Sistema de Agentes/Roles

Para proyectos complejos, usar diferentes "agentes" especializados ayuda a mantener el contexto y la calidad.

### Agente: Arquitecto

**Cuándo usar**: Decisiones de diseño, estructura, nuevos componentes.

**Prompt de activación:**
```
Actúa como Arquitecto de Software senior.

Tu rol:
- Diseñar estructura de componentes
- Definir interfaces entre módulos
- Tomar decisiones de arquitectura
- Considerar escalabilidad y mantenibilidad

Contexto del proyecto: [pegar ARCHITECTURE.md]

NO generes código de implementación, solo:
- Diagramas de arquitectura
- Interfaces/contratos
- Decisiones documentadas con trade-offs
```

### Agente: Implementador

**Cuándo usar**: Escribir código de funcionalidades.

**Prompt de activación:**
```
Actúa como Desarrollador Python senior.

Tu rol:
- Implementar funcionalidades según especificación
- Seguir convenciones del proyecto estrictamente
- Escribir código limpio y testeable
- Incluir type hints y docstrings

Convenciones: [pegar CONVENTIONS.md]
Tarea actual: [describir tarea]

Genera código completo y funcional.
```

### Agente: Tester

**Cuándo usar**: Escribir tests, mejorar coverage.

**Prompt de activación:**
```
Actúa como QA Engineer senior.

Tu rol:
- Escribir tests exhaustivos
- Identificar casos edge
- Mejorar coverage
- Validar que el código cumple la especificación

Código a testear: [pegar código]
Especificación: [describir qué debe hacer]

Genera tests con:
- Casos normales
- Casos edge
- Casos de error
- Mocks para dependencias externas
```

### Agente: Reviewer

**Cuándo usar**: Code review, identificar problemas.

**Prompt de activación:**
```
Actúa como Code Reviewer senior.

Tu rol:
- Revisar código críticamente
- Identificar bugs potenciales
- Sugerir mejoras
- Verificar cumplimiento de convenciones

Código a revisar: [pegar código]
Convenciones: [pegar CONVENTIONS.md]

Genera lista de:
1. 🔴 Problemas críticos (bugs, seguridad)
2. 🟡 Mejoras recomendadas
3. 🟢 Sugerencias menores
4. ✅ Cosas bien hechas
```

### Agente: Debugger

**Cuándo usar**: Resolver errores, entender comportamiento inesperado.

**Prompt de activación:**
```
Actúa como Debugger experto.

Tu rol:
- Analizar errores
- Identificar causa raíz
- Proponer solución
- Explicar por qué ocurrió

Error: [pegar error completo]
Código relevante: [pegar código]
Contexto: [describir qué estaba haciendo]

Analiza paso a paso:
1. Qué dice el error
2. Dónde ocurre
3. Por qué ocurre
4. Cómo solucionarlo
```

---

## Prompts por Fase

### Archivo: docs/prompts/phase-0-prep.md

```markdown
# Fase 0: Preparación y Limpieza
## Prompts para AI Assistants

### Contexto de la Fase
```
Fase 0 del proyecto Finanzas Tracker.
Objetivo: Auditar código existente, limpiar, establecer estructura.
Duración estimada: 2 semanas

El proyecto está al 50-60% completo. Antes de agregar features nuevas,
necesitamos entender qué hay y limpiarlo.
```

---

### Tarea 0.1: Inventario de Código

**Prompt:**
```
Necesito hacer un inventario del código existente en este proyecto.

Por favor analiza la estructura de carpetas y archivos y genera:
1. Lista de todos los archivos Python con descripción de qué hace cada uno
2. Dependencias entre archivos (quién importa a quién)
3. Estado de cada archivo: funcional / parcial / roto / no usado
4. Deuda técnica identificada

Formato de output:
| Archivo | Propósito | Estado | Dependencias | Notas |
|---------|-----------|--------|--------------|-------|

[Aquí pegar estructura de archivos o dejar que el AI la explore]
```

---

### Tarea 0.2: Diagrama de Arquitectura Actual

**Prompt:**
```
Basándote en el inventario de código, genera un diagrama de arquitectura
mostrando cómo fluyen los datos actualmente.

Incluir:
1. Fuentes de datos (emails, PDFs, etc.)
2. Procesamiento (parsers, services)
3. Almacenamiento (DB)
4. Interfaces (Streamlit, CLI)

Formato: Diagrama ASCII o descripción que pueda convertirse a diagrama.

También identificar:
- Componentes bien definidos
- Componentes con responsabilidades mezcladas
- Código duplicado
```

---

### Tarea 0.3: Identificar Código Muerto

**Prompt:**
```
Analiza el código del proyecto e identifica:

1. Archivos que no se importan desde ningún lado
2. Funciones/clases definidas pero nunca usadas
3. Variables asignadas pero nunca leídas
4. Imports no utilizados
5. Código comentado que debería eliminarse

Para cada hallazgo, indicar:
- Ubicación (archivo:línea)
- Qué es
- Recomendación (eliminar / revisar / mantener)

Ser conservador: si hay duda, marcar como "revisar" no "eliminar".
```

---

### Tarea 0.4: Reorganizar Estructura de Carpetas

**Prompt:**
```
El proyecto necesita reorganizarse a esta estructura:

```
src/
├── api/           # FastAPI endpoints
├── core/          # Config, constants
├── models/        # SQLAlchemy models
├── schemas/       # Pydantic schemas
├── services/      # Business logic
├── parsers/       # Bank/SINPE parsers
├── mcp/           # MCP server
└── utils/         # Helpers
tests/
├── unit/
├── integration/
└── fixtures/
```

Estructura actual: [pegar o describir]

Genera:
1. Plan de movimiento de archivos (de dónde a dónde)
2. Cambios necesarios en imports
3. Orden de ejecución (para no romper nada)
4. Script bash para hacer los movimientos

IMPORTANTE: No mover archivos que van a ser eliminados.
```

---

### Tarea 0.5: Configurar Pre-commit Hooks

**Prompt:**
```
Necesito configurar pre-commit hooks para el proyecto.

Tools a incluir:
1. ruff (linting + formatting)
2. mypy (type checking)
3. pytest (solo tests rápidos)

Genera:
1. .pre-commit-config.yaml
2. pyproject.toml con configuración de ruff y mypy
3. Instrucciones de instalación

Configuración de ruff:
- Line length: 100
- Python 3.11+
- Ignore: E501 en tests

Configuración de mypy:
- Strict mode
- Ignore missing imports para third-party sin stubs
```

---

### Tarea 0.6: README Inicial

**Prompt:**
```
Genera un README.md profesional inicial para el proyecto.

Información del proyecto:
- Nombre: Finanzas Tracker CR
- Descripción: Sistema de finanzas personales para Costa Rica con AI
- Stack: Python 3.11, FastAPI, SQLAlchemy, PostgreSQL, Streamlit
- Estado: En desarrollo activo

Secciones requeridas:
1. Título con badge de estado "Work in Progress"
2. Descripción en 2-3 oraciones
3. Features principales (lista)
4. Tech Stack
5. Quick Start (placeholder por ahora)
6. Estructura del proyecto
7. Roadmap (basado en las 6 fases)
8. License (MIT)

Tono: Profesional pero accesible.
```

---

### Verificación de Fase 0

**Prompt:**
```
Verifica que la Fase 0 está completa:

1. [ ] Inventario de código existe y está actualizado
2. [ ] Código muerto identificado y eliminado
3. [ ] Estructura de carpetas reorganizada
4. [ ] Pre-commit hooks funcionando (ruff, mypy pasan)
5. [ ] README.md existe con estructura básica
6. [ ] .env.example con todas las variables
7. [ ] .gitignore actualizado
8. [ ] Todos los archivos tienen docstrings de módulo

Ejecuta verificaciones y reporta qué falta.
```
```

---

### Archivo: docs/prompts/phase-1-foundation.md

```markdown
# Fase 1: Fundamentos de Producción
## Prompts para AI Assistants

### Contexto de la Fase
```
Fase 1 del proyecto Finanzas Tracker.
Objetivo: PostgreSQL + pgvector, Docker, Tests, tenant_id

Pre-requisitos:
- Fase 0 completa
- Docker instalado
- PostgreSQL client instalado

Stack actual: SQLite, sin Docker, 55% coverage
Stack objetivo: PostgreSQL + pgvector, Docker Compose, 80% coverage (services)
```

---

### Tarea 1.1: Docker Compose con PostgreSQL + pgvector

**Prompt:**
```
Necesito docker-compose.yml para desarrollo con PostgreSQL y pgvector.

Servicios requeridos:
1. db: PostgreSQL 16 con pgvector
2. redis: Para cache/rate limiting futuro (opcional pero recomendado)

Requisitos:
- Volúmenes persistentes
- Health checks
- Variables de entorno desde .env
- Puerto de PostgreSQL expuesto para desarrollo

También generar:
1. .env.example con todas las variables necesarias
2. Script de inicialización que habilita pgvector extension
3. Instrucciones en README para levantar

El contenedor de PostgreSQL debe usar imagen pgvector/pgvector:pg16
```

---

### Tarea 1.2: Actualizar Models para PostgreSQL

**Prompt:**
```
Necesito actualizar los modelos SQLAlchemy para PostgreSQL.

Cambios requeridos:
1. Agregar tenant_id (UUID, nullable, indexed) a TODAS las tablas
2. Agregar columna embedding (Vector(384)) a transactions
3. Usar tipos específicos de PostgreSQL donde aplique
4. Verificar que Numeric se use para montos (no Float)

Modelo actual de Transaction: [pegar modelo actual]
Otros modelos: [pegar o listar]

Genera:
1. Modelos actualizados
2. Migración Alembic para los cambios
3. Script SQL para habilitar pgvector y crear índice HNSW

Índice para embeddings:
```sql
CREATE INDEX ON transactions 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```
```

---

### Tarea 1.3: Configurar pytest con Fixtures

**Prompt:**
```
Necesito configurar pytest profesionalmente.

Estructura de tests:
```
tests/
├── conftest.py          # Fixtures globales
├── unit/
│   ├── conftest.py      # Fixtures de unit tests
│   ├── test_services/
│   └── test_parsers/
├── integration/
│   ├── conftest.py      # Fixtures de integration
│   └── test_api/
└── fixtures/
    └── data/            # JSON con datos de prueba
```

Fixtures necesarias:
1. db_session: Session de SQLAlchemy (SQLite in-memory para speed)
2. client: TestClient de FastAPI
3. sample_transactions: Lista de transacciones de prueba
4. sample_categories: Categorías 50/30/20
5. mock_claude: Mock de Anthropic API

Genera:
1. tests/conftest.py con fixtures globales
2. tests/fixtures/data/transactions.json con 50+ transacciones realistas
3. tests/fixtures/data/categories.json con categorías 50/30/20
4. pyproject.toml con configuración de pytest y coverage
```

---

### Tarea 1.4: Tests para Services Críticos

**Prompt:**
```
Necesito tests exhaustivos para los services de negocio.

Services a testear (en orden de prioridad):
1. TransactionService - CRUD de transacciones
2. CategorizationService - Lógica 3-tier
3. BudgetService - Cálculos 50/30/20
4. AnalyticsService - Estadísticas

Para cada service, testear:
- Casos normales (happy path)
- Casos edge (listas vacías, valores límite)
- Casos de error (datos inválidos, not found)
- Soft delete funciona correctamente

Código de TransactionService: [pegar]
Código de CategorizationService: [pegar]

Target: 80% coverage en estos services
```

---

### Tarea 1.5: GitHub Actions CI

**Prompt:**
```
Necesito GitHub Actions para CI.

Workflow ci.yml que se ejecute en:
- Push a main
- Pull requests a main

Jobs:
1. lint:
   - ruff check
   - ruff format --check
   
2. type-check:
   - mypy src/
   
3. test:
   - pytest con coverage
   - Subir coverage a Codecov (o similar)
   - Fallar si coverage < 60%

4. build:
   - docker build (verificar que Dockerfile funciona)

Matriz de Python: solo 3.11 por ahora

También generar badge para README.
```

---

### Tarea 1.6: Dockerfile Optimizado

**Prompt:**
```
Necesito Dockerfile multi-stage optimizado para producción.

Requisitos:
1. Base image: python:3.11-slim
2. Multi-stage: builder + runtime
3. Instalar solo dependencias de producción en runtime
4. No root user
5. Health check
6. Optimizar cache de layers

Dependencias del sistema necesarias:
- libpq-dev (para psycopg)

El Dockerfile debe funcionar tanto para la API como para Streamlit
(o crear dos Dockerfiles si es más limpio).
```

---

### Tarea 1.7: Makefile con Comandos Comunes

**Prompt:**
```
Necesito un Makefile con comandos de desarrollo.

Comandos requeridos:
- make dev: Levantar docker-compose en modo desarrollo
- make test: Correr pytest
- make test-cov: Correr pytest con coverage report
- make lint: Correr ruff
- make format: Formatear código con ruff
- make type-check: Correr mypy
- make migrate: Correr alembic upgrade head
- make migration MSG="descripcion": Crear nueva migración
- make shell: Abrir shell de Python con contexto del proyecto
- make clean: Limpiar archivos temporales

Incluir .PHONY para todos los comandos.
```

---

### Verificación de Fase 1

**Prompt:**
```
Verifica que la Fase 1 está completa:

1. [ ] docker-compose up levanta PostgreSQL con pgvector
2. [ ] Conexión a PostgreSQL funciona desde la app
3. [ ] pgvector extension está habilitada
4. [ ] tenant_id existe en todas las tablas
5. [ ] Migraciones Alembic funcionan
6. [ ] pytest corre sin errores
7. [ ] Coverage de services >= 80%
8. [ ] Coverage general >= 60%
9. [ ] GitHub Actions CI pasa
10. [ ] Dockerfile build funciona
11. [ ] Makefile comandos funcionan

Ejecuta verificaciones y reporta resultados.
```
```

---

### Archivo: docs/prompts/phase-2-api.md

```markdown
# Fase 2: API REST Profesional
## Prompts para AI Assistants

### Contexto de la Fase
```
Fase 2 del proyecto Finanzas Tracker.
Objetivo: API REST completa con FastAPI

Pre-requisitos:
- Fase 1 completa
- PostgreSQL corriendo
- Services existentes funcionando

El dashboard Streamlit actualmente hace queries directos a la DB.
Después de esta fase, todo debe pasar por la API.
```

---

### Tarea 2.1: Estructura Base de FastAPI

**Prompt:**
```
Necesito crear la estructura base de la API FastAPI.

Estructura:
```
src/api/
├── __init__.py
├── main.py              # App FastAPI, middleware, CORS
├── deps.py              # Dependencies (get_db, etc.)
└── v1/
    ├── __init__.py
    ├── router.py        # Router que agrupa todos los endpoints
    └── endpoints/
        ├── __init__.py
        ├── transactions.py
        ├── categories.py
        ├── budgets.py
        ├── analytics.py
        ├── incomes.py
        └── health.py
```

Genera:
1. src/api/main.py con:
   - CORS configurado (orígenes configurables)
   - Middleware de logging
   - Exception handlers
   - Lifespan para startup/shutdown
   
2. src/api/deps.py con:
   - get_db() dependency
   - Placeholder para get_current_user (futuro)
   
3. src/api/v1/router.py que incluye todos los routers
4. src/api/v1/endpoints/health.py con /health y /ready
```

---

### Tarea 2.2: Schemas Pydantic

**Prompt:**
```
Necesito schemas Pydantic para request/response de la API.

Modelos SQLAlchemy existentes: [pegar modelos]

Para cada modelo, crear:
1. {Model}Create - Para POST (solo campos requeridos en creación)
2. {Model}Update - Para PUT/PATCH (todos opcionales)
3. {Model}Response - Para respuestas (incluye id, timestamps)
4. {Model}List - Para listas con paginación

Schemas adicionales:
- PaginatedResponse[T] - Respuesta paginada genérica
- ErrorResponse - Estructura de errores consistente

Ubicación: src/schemas/

Ejemplo de estructura para Transaction:
```python
class TransactionCreate(BaseModel):
    amount: Decimal
    description: str
    date: datetime
    category_id: int | None = None

class TransactionResponse(BaseModel):
    id: int
    amount: Decimal
    description: str
    date: datetime
    category: CategoryResponse | None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
```
```

---

### Tarea 2.3: Endpoints de Transacciones

**Prompt:**
```
Necesito implementar endpoints CRUD para transacciones.

TransactionService existente: [pegar código]
Schemas: [pegar schemas]

Endpoints requeridos:

GET /api/v1/transactions
- Filtros: date_from, date_to, category_id, min_amount, max_amount, search
- Paginación: skip, limit
- Ordenamiento: sort_by, sort_order

POST /api/v1/transactions
- Crear transacción
- Retornar 201 con transacción creada

GET /api/v1/transactions/{id}
- Retornar transacción o 404

PUT /api/v1/transactions/{id}
- Actualizar transacción
- Retornar transacción actualizada o 404

DELETE /api/v1/transactions/{id}
- Soft delete
- Retornar 204

POST /api/v1/transactions/natural-language
- Crear desde texto natural (ej: "hoy gasté 10 mil en almuerzo")
- Usar Claude para parsear
- Retornar transacción creada

Generar src/api/v1/endpoints/transactions.py completo con:
- Documentación OpenAPI (descriptions, examples)
- Validación de inputs
- Manejo de errores consistente
```

---

### Tarea 2.4: Endpoints de Analytics

**Prompt:**
```
Necesito endpoints de analytics y reportes.

AnalyticsService existente: [pegar o describir]

Endpoints requeridos:

GET /api/v1/analytics/spending-by-category
- Parámetros: period (week/month/year)
- Retorna: {category: amount}

GET /api/v1/analytics/monthly-trends
- Parámetros: months (default 6)
- Retorna: [{month, income, expenses, balance}]

GET /api/v1/analytics/budget-status
- Parámetros: month (YYYY-MM, default actual)
- Retorna: Estado 50/30/20 con progreso

GET /api/v1/analytics/anomalies
- Parámetros: sensitivity (0.01-0.5)
- Retorna: Transacciones anómalas con score

GET /api/v1/analytics/subscriptions
- Sin parámetros
- Retorna: Gastos recurrentes detectados

GET /api/v1/analytics/end-of-month-prediction
- Sin parámetros
- Retorna: Predicción de balance a fin de mes

Generar src/api/v1/endpoints/analytics.py
```

---

### Tarea 2.5: Migrar Streamlit a Consumir API

**Prompt:**
```
Necesito migrar el dashboard Streamlit para que use la API en lugar de
queries directos a la base de datos.

Código actual de Streamlit: [pegar páginas relevantes]
URL de la API: http://localhost:8000/api/v1

Cambios necesarios:
1. Crear cliente HTTP (httpx o requests)
2. Reemplazar db.query() por llamadas a API
3. Manejar errores de API gracefully
4. Cachear respuestas donde tenga sentido (@st.cache_data)

Ejemplo de migración:

ANTES:
```python
transactions = db.query(Transaction).filter(...).all()
```

DESPUÉS:
```python
response = api_client.get("/transactions", params={...})
transactions = response.json()
```

Generar:
1. src/streamlit_app/api_client.py - Cliente HTTP configurado
2. Páginas migradas (o diff de cambios)
```

---

### Tarea 2.6: Tests de Integración de API

**Prompt:**
```
Necesito tests de integración para la API.

Endpoints implementados: [listar]

Para cada endpoint, testear:
1. Happy path retorna código y datos correctos
2. Validación rechaza datos inválidos (422)
3. Not found retorna 404
4. Filtros funcionan correctamente
5. Paginación funciona

Usar TestClient de FastAPI.

Generar:
1. tests/integration/test_api/test_transactions.py
2. tests/integration/test_api/test_analytics.py
3. tests/integration/conftest.py con fixtures específicas

Ejemplo de test:
```python
def test_list_transactions(client, sample_transactions):
    response = client.get("/api/v1/transactions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(sample_transactions)
```
```

---

### Verificación de Fase 2

**Prompt:**
```
Verifica que la Fase 2 está completa:

1. [ ] FastAPI app arranca sin errores
2. [ ] /docs muestra documentación OpenAPI
3. [ ] Todos los endpoints de transactions funcionan
4. [ ] Todos los endpoints de analytics funcionan
5. [ ] Endpoints de categories funcionan
6. [ ] Endpoints de budgets funcionan
7. [ ] Endpoints de incomes funcionan
8. [ ] Streamlit usa la API (no queries directos)
9. [ ] Tests de integración pasan
10. [ ] Response times < 200ms para endpoints simples

Ejecuta verificaciones y reporta resultados.
```
```

---

## Uso Práctico: Ejemplo de Sesión

### Sesión de Trabajo Típica

```
1. INICIO DE SESIÓN
   - Abrir Cursor/Copilot
   - Cargar contexto: .cursorrules, ARCHITECTURE.md, fase actual
   
2. DEFINIR OBJETIVO
   "Hoy voy a completar Tarea 2.3: Endpoints de Transacciones"
   
3. EJECUTAR PROMPT
   - Copiar prompt de phase-2-api.md → Tarea 2.3
   - Pegar código de contexto necesario
   - Enviar a AI
   
4. VALIDAR OUTPUT
   - Revisar código generado
   - Correr lint: make lint
   - Correr tests: make test
   
5. ITERAR SI NECESARIO
   "El endpoint GET /transactions no está filtrando por categoría 
   correctamente. El filtro category_id se ignora. Aquí está el 
   código actual: [pegar]. Por favor corrige."
   
6. COMMIT
   git add .
   git commit -m "feat(api): add transactions CRUD endpoints"
   
7. SIGUIENTE TAREA
   Repetir desde paso 2 con Tarea 2.4
```

### Tips para Mejores Resultados

1. **Contexto específico > contexto general**: Pegar solo el código relevante, no todo el proyecto.

2. **Un cambio a la vez**: No pedir "implementa toda la API", sino "implementa GET /transactions".

3. **Feedback específico**: No "no funciona", sino "retorna 500 con este error: [error]".

4. **Validar incrementalmente**: Correr tests después de cada cambio, no al final.

5. **Usar el agente correcto**: Arquitecto para diseño, Implementador para código, Tester para tests.

6. **Documentar decisiones**: Cuando el AI tome una decisión de diseño, documentarla en ARCHITECTURE.md.
