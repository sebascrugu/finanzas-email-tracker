# Finanzas Tracker CR - Arquitectura

> Sistema de finanzas personales para Costa Rica con AI.  
> Primera app que soporta SINPE Móvil y bancos costarricenses.

## Tabla de Contenidos

- [Vista General](#vista-general)
- [Stack Tecnológico](#stack-tecnológico)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Capas de la Arquitectura](#capas-de-la-arquitectura)
- [Base de Datos](#base-de-datos)
- [API REST](#api-rest)
- [Patrones de Diseño](#patrones-de-diseño)
- [Infraestructura](#infraestructura)
- [Testing](#testing)
- [Flujo de Datos](#flujo-de-datos)

---

## Vista General

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTES                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Streamlit  │  │   Claude    │  │   Future    │              │
│  │  Dashboard  │  │   Desktop   │  │   Mobile    │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼─────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI REST API                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Middleware Layer                       │   │
│  │  • CorrelationIdMiddleware (X-Correlation-ID)            │   │
│  │  • RequestLoggingMiddleware (JSON structured logs)       │   │
│  │  • Error Handling (AppException hierarchy)               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Router Layer                           │   │
│  │  /api/v1/transactions  │  /api/v1/categories             │   │
│  │  /api/v1/incomes       │  /api/v1/budgets                │   │
│  │  /api/v1/profiles      │  /api/v1/cards                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SERVICE LAYER                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │Transaction  │  │ Categorizer │  │   Budget    │              │
│  │  Service    │  │  (Claude)   │  │   Service   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  REPOSITORY LAYER                         │   │
│  │  • BaseRepository<T> (Generic CRUD + soft delete)        │   │
│  │  • TransactionRepository                                  │   │
│  │  • CategoryRepository                                     │   │
│  │  • ProfileRepository                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL + pgvector                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │transactions │  │ categories  │  │  embeddings │              │
│  │   (soft     │  │  (seed +    │  │   (vector   │              │
│  │   delete)   │  │   custom)   │  │   search)   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Stack Tecnológico

### Core
| Componente | Tecnología | Versión | Propósito |
|------------|------------|---------|-----------|
| Runtime | Python | 3.11+ | Lenguaje principal |
| API Framework | FastAPI | 0.100+ | REST API async |
| ORM | SQLAlchemy | 2.0+ | Mapeo objeto-relacional |
| Validation | Pydantic | 2.0+ | Schemas y validación |
| Database | PostgreSQL | 16+ | Almacenamiento principal |
| Vector Store | pgvector | 0.5+ | Embeddings para RAG |
| AI | Claude (Anthropic) | API | Categorización inteligente |

### Infrastructure
| Componente | Tecnología | Propósito |
|------------|------------|-----------|
| Containerization | Docker | Ambientes consistentes |
| Orchestration | Docker Compose | Dev/Prod deployment |
| CI/CD | GitHub Actions | Automatización |
| Migrations | Alembic | Schema versioning |

### Development
| Componente | Tecnología | Propósito |
|------------|------------|-----------|
| Linting | Ruff | Fast Python linter |
| Type Checking | mypy | Static type analysis |
| Security Scan | Bandit | Vulnerability detection |
| Testing | pytest | Unit/Integration tests |
| Coverage | pytest-cov | Code coverage reports |

### MCP Server (Model Context Protocol)
| Componente | Tecnología | Versión | Propósito |
|------------|------------|---------|-----------|
| SDK | FastMCP | 1.22.0 | Protocol implementation |
| Transport | stdio | - | Claude Desktop integration |
| Features | Tools, Resources, Prompts | - | Full MCP spec support |

---

## MCP Server - Integración con Claude Desktop

El servidor MCP permite que Claude Desktop interactúe directamente con tus finanzas personales.

### Arquitectura MCP

```
┌────────────────────┐         ┌────────────────────────────────┐
│   Claude Desktop   │  stdio  │        MCP Server              │
│                    │◄───────►│   (finanzas-tracker)           │
│  "¿Cuánto gasté    │         │                                │
│   en comida?"      │         │  ┌──────────────────────────┐  │
│                    │         │  │ 🔧 12 Tools              │  │
└────────────────────┘         │  │ 📄 3 Resources           │  │
                               │  │ 📝 4 Prompts             │  │
                               │  └────────────┬─────────────┘  │
                               │               │                 │
                               │               ▼                 │
                               │  ┌──────────────────────────┐  │
                               │  │      PostgreSQL          │  │
                               │  │   (transactions, etc)    │  │
                               │  └──────────────────────────┘  │
                               └────────────────────────────────┘
```

### Herramientas Disponibles (12 total)

#### Configuración (REQUERIDO PRIMERO)
| Herramienta | Descripción |
|-------------|-------------|
| `set_profile` | ⚙️ Establece el perfil activo (OBLIGATORIO antes de otras tools) |
| `list_profiles` | 📋 Lista todos los perfiles disponibles |

#### Nivel 1 - Consultas Básicas
| Herramienta | Descripción |
|-------------|-------------|
| `get_transactions` | Consultar transacciones con filtros (días, comercio, categoría) |
| `get_spending_summary` | Resumen agrupado por categoría, comercio o banco |
| `get_top_merchants` | Top N comercios donde más gastas |

#### Nivel 2 - Análisis
| Herramienta | Descripción |
|-------------|-------------|
| `search_transactions` | Búsqueda semántica con embeddings |
| `get_monthly_comparison` | Comparación mes actual vs anterior |

#### Nivel 3 - Coaching (DIFERENCIADOR vs Actual Budget)
| Herramienta | Emoji | Descripción |
|-------------|-------|-------------|
| `budget_coaching` | 🎯 | Coaching financiero personalizado con score de salud |
| `savings_opportunities` | 💰 | Encuentra oportunidades concretas de ahorro |
| `cashflow_prediction` | 🔮 | Predice flujo de efectivo y días de riesgo |
| `spending_alert` | 🚨 | Detecta patrones problemáticos en tiempo real |
| `goal_advisor` | 🎯 | Asesor de metas de ahorro con plan de acción |

### MCP Resources (Contexto Automático)

Los Resources proveen contexto que Claude puede leer automáticamente:

| Resource URI | Descripción |
|--------------|-------------|
| `profile://current` | Información del perfil activo actual |
| `finance://summary` | Resumen financiero rápido del mes actual |
| `categories://list` | Lista de categorías disponibles |

### MCP Prompts (Plantillas Predefinidas)

Los Prompts son plantillas para casos de uso comunes:

| Prompt | Descripción | Parámetros |
|--------|-------------|------------|
| `weekly_review` | Revisión semanal de finanzas | ninguno |
| `monthly_checkup` | Chequeo mensual completo | ninguno |
| `savings_plan` | Plan de ahorro para meta específica | goal, amount, months |
| `quick_question` | Plantilla para preguntas rápidas | question |

### Configuración Claude Desktop

```json
{
  "mcpServers": {
    "finanzas-tracker": {
      "command": "poetry",
      "args": [
        "run",
        "python",
        "-m",
        "finanzas_tracker.mcp"
      ],
      "cwd": "/path/to/finanzas-email-tracker"
    }
  }
}
```

### Ejemplos de Uso

```
Usuario: "¿Cómo van mis finanzas este mes?"
→ Claude usa set_profile() + budget_coaching()
→ Retorna: Score de salud 78/100, 3 recomendaciones priorizadas

Usuario: "¿Dónde puedo ahorrar dinero?"
→ Claude usa savings_opportunities()
→ Retorna: ₡45,000 en oportunidades identificadas

Usuario: "Quiero ahorrar ₡300,000 en 6 meses para un viaje"
→ Claude usa goal_advisor(goal_amount=300000, goal_months=6, goal_name="viaje")
→ Retorna: Plan de acción con categorías a reducir
```

---

## Estructura del Proyecto

```
finanzas-email-tracker/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions: lint, typecheck, security, test, docker
│
├── alembic/
│   └── versions/               # Database migrations
│
├── src/finanzas_tracker/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app factory
│   │   ├── deps.py             # Dependency injection
│   │   ├── errors.py           # Exception handlers
│   │   ├── middleware.py       # Correlation ID, Request logging
│   │   └── routers/
│   │       ├── transactions.py
│   │       ├── categories.py
│   │       ├── incomes.py
│   │       ├── budgets.py
│   │       └── profiles.py
│   │
│   ├── core/
│   │   ├── config.py           # Settings (Pydantic)
│   │   ├── logging.py          # Loguru + JSON formatting
│   │   └── exceptions.py       # AppException hierarchy
│   │
│   ├── db/
│   │   ├── database.py         # Session management
│   │   └── repositories/
│   │       ├── base.py         # BaseRepository<T>
│   │       ├── transaction.py
│   │       ├── category.py
│   │       └── profile.py
│   │
│   ├── models/
│   │   ├── base.py             # Base model with timestamps
│   │   ├── transaction.py
│   │   ├── category.py
│   │   ├── income.py
│   │   ├── budget.py
│   │   ├── profile.py
│   │   └── card.py
│   │
│   ├── schemas/
│   │   ├── transaction.py      # Create, Update, Response
│   │   ├── category.py
│   │   ├── income.py
│   │   └── ...
│   │
│   ├── services/
│   │   ├── transaction_processor.py
│   │   ├── categorizer.py      # Claude integration
│   │   ├── email_fetcher.py
│   │   └── exchange_rate.py
│   │
│   └── parsers/
│       ├── bac_parser.py       # BAC Credomatic
│       ├── sinpe_parser.py     # SINPE Móvil
│       └── popular_parser.py   # Banco Popular
│
├── tests/
│   ├── conftest.py             # Fixtures (db, client, factories)
│   ├── unit/
│   ├── integration/
│   └── api/                    # FastAPI TestClient tests
│
├── docker-compose.yml          # Base compose
├── docker-compose.dev.yml      # Development overrides
├── docker-compose.prod.yml     # Production config
├── Dockerfile                  # Multi-stage production build
├── Dockerfile.dev              # Development with hot reload
│
├── pyproject.toml              # Dependencies + tool config
├── ruff.toml                   # Linting rules
└── alembic.ini                 # Migration config
```

---

## Capas de la Arquitectura

### 1. API Layer (`src/finanzas_tracker/api/`)

**Responsabilidades:**
- Recibir requests HTTP
- Validar input con Pydantic schemas
- Inyectar dependencias (DB session)
- Retornar responses estructuradas
- Manejo de errores consistente

**Middleware Stack:**
```python
# Orden de ejecución (de afuera hacia adentro)
app.add_middleware(CorrelationIdMiddleware)   # 1. Genera/propaga X-Correlation-ID
app.add_middleware(RequestLoggingMiddleware)  # 2. Log: method, path, status, duration
```

**Error Handling:**
```python
# Jerarquía de excepciones
AppException (base)
├── ValidationError      # 400 Bad Request
├── NotFoundError        # 404 Not Found
├── ConflictError        # 409 Conflict
├── AuthenticationError  # 401 Unauthorized
└── AuthorizationError   # 403 Forbidden

# Respuesta estructurada
{
    "error": "Categoría no encontrada",
    "code": "CATEGORY_NOT_FOUND",
    "details": {...}  # Solo en development
}
```

### 2. Service Layer (`src/finanzas_tracker/services/`)

**Responsabilidades:**
- Lógica de negocio
- Orquestación de repositories
- Integración con servicios externos (Claude, email)
- Validaciones de dominio

**Patrón:**
```python
class TransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TransactionRepository(db)
    
    def create_with_categorization(
        self, 
        data: TransactionCreate
    ) -> Transaction:
        # 1. Validar datos
        # 2. Categorizar con Claude si necesario
        # 3. Guardar via repository
        # 4. Retornar entidad
        ...
```

### 3. Repository Layer (`src/finanzas_tracker/db/repositories/`)

**Responsabilidades:**
- Acceso a datos
- Queries SQLAlchemy
- Soft delete automático
- Paginación

**BaseRepository genérico:**
```python
class BaseRepository(Generic[T]):
    def __init__(self, db: Session, model: type[T]) -> None:
        self.db = db
        self.model = model
    
    def get(self, id: int) -> T | None:
        """Obtiene por ID, excluyendo soft-deleted."""
        stmt = select(self.model).where(
            self.model.id == id,
            self.model.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        """Lista con paginación."""
        ...
    
    def create(self, obj: T) -> T:
        """Crea y retorna con ID."""
        ...
    
    def soft_delete(self, id: int) -> bool:
        """Marca deleted_at, nunca DELETE real."""
        ...
```

### 4. Model Layer (`src/finanzas_tracker/models/`)

**Responsabilidades:**
- Definición de tablas
- Relaciones SQLAlchemy
- Timestamps automáticos

**Convenciones:**
```python
class Transaction(Base):
    __tablename__ = "transactions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID | None]  # Multi-tenancy futuro
    
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # NUNCA Float
    description: Mapped[str] = mapped_column(String(500))
    
    # Soft delete - NUNCA DELETE real
    deleted_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(onupdate=datetime.utcnow)
```

---

## Base de Datos

### PostgreSQL + pgvector

**¿Por qué PostgreSQL?**
- ACID compliant
- pgvector para embeddings (RAG)
- Mejor soporte para Numeric/Decimal
- Producción ready

**Schema Principal:**

```
┌─────────────────────┐       ┌─────────────────────┐
│     categories      │       │      profiles       │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │       │ id (PK)             │
│ nombre              │       │ nombre              │
│ tipo (enum)         │       │ email               │
│ color               │       │ is_default          │
│ icono               │       │ deleted_at          │
│ tenant_id           │       │ created_at          │
│ deleted_at          │       │ updated_at          │
└─────────────────────┘       └─────────────────────┘
         │                              │
         │                              │
         ▼                              ▼
┌─────────────────────────────────────────────────────┐
│                    transactions                      │
├─────────────────────────────────────────────────────┤
│ id (PK)                                             │
│ amount (Numeric 12,2)                               │
│ currency (CRC/USD)                                  │
│ description                                         │
│ date                                                │
│ source_type (sinpe/bac/manual)                     │
│ category_id (FK) ────────────────────────────────┐ │
│ profile_id (FK) ─────────────────────────────────┘ │
│ tenant_id                                           │
│ deleted_at                                          │
│ created_at, updated_at                              │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│              transaction_embeddings                  │
├─────────────────────────────────────────────────────┤
│ id (PK)                                             │
│ transaction_id (FK)                                 │
│ embedding (vector 1536)  ← pgvector                 │
│ model_version                                       │
└─────────────────────────────────────────────────────┘
```

### Migrations (Alembic)

```bash
# Crear nueva migración
alembic revision --autogenerate -m "add_new_table"

# Aplicar migraciones
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## API REST

### Endpoints Principales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/v1/transactions` | Listar transacciones |
| `POST` | `/api/v1/transactions` | Crear transacción |
| `GET` | `/api/v1/transactions/{id}` | Obtener por ID |
| `PUT` | `/api/v1/transactions/{id}` | Actualizar |
| `DELETE` | `/api/v1/transactions/{id}` | Soft delete |
| `GET` | `/api/v1/categories` | Listar categorías |
| `POST` | `/api/v1/categories` | Crear categoría |
| `GET` | `/api/v1/budgets` | Listar presupuestos |
| `POST` | `/api/v1/budgets` | Crear presupuesto |
| `GET` | `/health` | Health check |

### Schemas (Pydantic)

```python
# Patrón: Create, Update, Response separados
class TransactionCreate(BaseModel):
    amount: Decimal = Field(..., description="Monto en la moneda especificada")
    currency: Currency = Currency.CRC
    description: str = Field(..., max_length=500)
    date: date
    category_id: int | None = None

class TransactionUpdate(BaseModel):
    amount: Decimal | None = None
    description: str | None = None
    category_id: int | None = None

class TransactionResponse(BaseModel):
    id: int
    amount: Decimal
    currency: Currency
    description: str
    date: date
    category: CategoryResponse | None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
```

---

## Patrones de Diseño

### 1. Repository Pattern
- Abstracción sobre acceso a datos
- BaseRepository genérico con CRUD
- Soft delete automático
- Facilita testing con mocks

### 2. Dependency Injection
```python
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
def list_transactions(db: Session = Depends(get_db)):
    ...
```

### 3. Factory Pattern
- `create_app()` para FastAPI application
- Permite diferentes configs (test, dev, prod)

### 4. Strategy Pattern (Parsers)
```python
class BaseParser(ABC):
    @abstractmethod
    def parse(self, content: str) -> list[Transaction]:
        ...

class BACParser(BaseParser):
    def parse(self, content: str) -> list[Transaction]:
        # Lógica específica BAC
        ...

class SINPEParser(BaseParser):
    def parse(self, content: str) -> list[Transaction]:
        # Lógica específica SINPE
        ...
```

---

## Infraestructura

### Docker

**Development:**
```yaml
# docker-compose.dev.yml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.dev
    volumes:
      - ./src:/app/src  # Hot reload
    environment:
      - DEBUG=true
    ports:
      - "8000:8000"
  
  db:
    image: pgvector/pgvector:pg16
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

**Production:**
```yaml
# docker-compose.prod.yml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    deploy:
      resources:
        limits:
          memory: 512M
    restart: unless-stopped
```

### GitHub Actions CI

```yaml
# .github/workflows/ci.yml
jobs:
  lint:        # Ruff check + format
  typecheck:   # mypy strict
  security:    # Bandit scan
  test:        # pytest with PostgreSQL service
  docker:      # Build + push to GHCR
```

### Logging

```python
# Production: JSON structured
{
    "timestamp": "2024-01-15T10:30:00Z",
    "level": "INFO",
    "service": "finanzas-tracker-api",
    "correlation_id": "abc123",
    "message": "POST /api/v1/transactions 201 45ms"
}

# Development: Colorized console
2024-01-15 10:30:00 | INFO | POST /api/v1/transactions 201 45ms
```

---

## Testing

### Estrategia de Tests

```
tests/
├── unit/                  # Lógica aislada, mocks
├── integration/           # Con DB real (PostgreSQL)
└── api/                   # FastAPI TestClient
```

### Fixtures (conftest.py)

```python
@pytest.fixture
def db_session():
    """Session con transacción que hace rollback."""
    ...

@pytest.fixture
def client(db_session):
    """TestClient con DB inyectada."""
    ...

@pytest.fixture
def sample_category(db_session):
    """Categoría de prueba."""
    ...
```

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Con coverage
pytest --cov=src/finanzas_tracker --cov-report=html

# Solo unit tests
pytest tests/unit/

# Solo API tests
pytest tests/api/
```

### Coverage Target
- **Global:** 80%+
- **Services:** 90%+
- **Parsers:** 95%+ (lógica crítica)

---

## Flujo de Datos

### Crear Transacción

```
1. Request → POST /api/v1/transactions
                    │
2. Middleware → Genera Correlation ID
                    │
3. Router → Valida con Pydantic schema
                    │
4. Service → Categoriza con Claude (si necesario)
                    │
5. Repository → INSERT con SQLAlchemy
                    │
6. Response → 201 Created + TransactionResponse
```

### Flujo de Email Processing

```
1. Email Fetcher → Lee IMAP inbox
                    │
2. Parser Selection → Detecta banco (BAC/SINPE/Popular)
                    │
3. Parser → Extrae transacciones del email
                    │
4. Categorizer → Claude categoriza cada transacción
                    │
5. Transaction Service → Guarda en DB
                    │
6. Embeddings → Genera vectores para RAG
```

---

## Decisiones de Arquitectura

| Decisión | Alternativa | Razón |
|----------|-------------|-------|
| PostgreSQL + pgvector | ChromaDB, Pinecone | Un solo DB, menos complejidad |
| Repository Pattern | Active Record | Mejor testabilidad |
| Soft Delete | Hard Delete | Recuperación, auditoría |
| Decimal para dinero | Float | Precisión financiera |
| Multi-stage Docker | Single Dockerfile | Imágenes más pequeñas |
| Pydantic v2 | Marshmallow | Mejor integración FastAPI |

---

## Próximos Pasos

- [ ] Autenticación (OAuth2 / JWT)
- [ ] Rate limiting
- [ ] Caching (Redis)
- [ ] Background jobs (Celery/ARQ)
- [ ] Métricas (Prometheus)
- [ ] Tracing distribuido (OpenTelemetry)

---

*Última actualización: Enero 2025*
