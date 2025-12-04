# Finanzas Tracker CR - Instrucciones para GitHub Copilot

## Proyecto
Sistema de finanzas personales para Costa Rica con AI. Soporta BAC Credomatic y Banco Popular.

**Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, PostgreSQL 16 + pgvector, Streamlit, Claude AI

**Estado:** En desarrollo activo, ~60% completo

## Arquitectura

```
src/
├── api/           # FastAPI REST API
├── core/          # Config, settings, constants
├── models/        # SQLAlchemy models
├── schemas/       # Pydantic schemas
├── services/      # Business logic
├── parsers/       # Bank statement parsers (SINPE, BAC, etc.)
├── mcp/           # MCP Server para Claude Desktop
└── utils/         # Helpers
```

## Convenciones de Código

### Python General
- Type hints OBLIGATORIOS en todo (funciones, variables, returns)
- Usar `str | None` en lugar de `Optional[str]`
- Docstrings en formato Google
- snake_case para variables y funciones
- PascalCase para clases
- UPPER_SNAKE_CASE para constantes
- Máximo 100 caracteres por línea
- Imports ordenados: stdlib → third-party → local

### SQLAlchemy 2.0
- Usar estilo 2.0: `select()` en lugar de `query()`
- Modelos heredan de Base declarativa
- SIEMPRE soft delete con `deleted_at`, NUNCA DELETE real
- SIEMPRE incluir `tenant_id: UUID | None` en todas las tablas (para multi-tenancy futuro)
- Usar `Numeric(12, 2)` para montos, NUNCA Float
- Incluir `created_at` y `updated_at` en todas las tablas

### FastAPI
- Versionar endpoints: `/api/v1/...`
- Schemas separados: `{Model}Create`, `{Model}Update`, `{Model}Response`
- Dependency injection para DB session con `Depends(get_db)`
- HTTPException con detail estructurado: `{"error": "msg", "code": "ERROR_CODE"}`
- Documentar endpoints con docstrings (aparecen en OpenAPI)

### Pydantic
- Usar `model_config = ConfigDict(from_attributes=True)` para responses
- Validación con `Field()` incluyendo description
- Schemas de Update tienen todos los campos opcionales

### Tests (pytest)
- Fixtures en `conftest.py`
- Mocks para APIs externas (Claude, email)
- Unit tests en `tests/unit/`
- Integration tests en `tests/integration/`
- Target: 80% coverage en `src/services/`
- Nombres descriptivos: `test_create_transaction_without_category`

### Logging
- Usar `logging` module, NUNCA `print()`
- Niveles apropiados: DEBUG para desarrollo, INFO para operaciones, ERROR para fallos
- No loggear datos sensibles (montos, descripciones, PII)

## Contexto de Dominio (Costa Rica)

- **CRC** = Colones costarricenses (moneda local)
- **SINPE Móvil** = Sistema de pagos instantáneos de Costa Rica (76% adopción)
- **BAC Credomatic** = Banco más grande de Centroamérica
- **Banco Popular** = Banco estatal de Costa Rica
- **50/30/20** = Metodología de presupuesto (necesidades/gustos/ahorros)

### Formatos de Moneda
```python
# Siempre usar Decimal para montos
from decimal import Decimal
amount = Decimal("15000.00")  # ₡15,000

# Formato display
f"₡{amount:,.2f}"  # "₡15,000.00"
```

## Patrones Requeridos

### Modelo SQLAlchemy
```python
from sqlalchemy import Column, Integer, String, DateTime, Numeric
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(String(500), nullable=False)
    
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Endpoint FastAPI
```python
@router.get("/{id}", response_model=TransactionResponse)
def get_transaction(
    id: int,
    db: Session = Depends(get_db),
) -> TransactionResponse:
    """Obtiene una transacción por ID."""
    service = TransactionService(db)
    transaction = service.get(id)
    if not transaction:
        raise HTTPException(
            status_code=404,
            detail={"error": "Transaction not found", "code": "TXN_NOT_FOUND"}
        )
    return transaction
```

### Service Pattern
```python
class TransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db
    
    def get(self, id: int) -> Transaction | None:
        stmt = select(Transaction).where(
            Transaction.id == id,
            Transaction.deleted_at.is_(None)
        )
        return self.db.execute(stmt).scalar_one_or_none()
```

## NO Hacer (Crítico)

- ❌ NO usar `print()` - usar `logging`
- ❌ NO hardcodear secrets - usar variables de entorno
- ❌ NO escribir SQL raw - usar SQLAlchemy ORM
- ❌ NO usar `Float` para dinero - usar `Numeric(12, 2)`
- ❌ NO hacer DELETE real - usar soft delete
- ❌ NO ignorar type hints
- ❌ NO olvidar `tenant_id` en tablas nuevas
- ❌ NO usar `Optional[X]` - usar `X | None`

## Respuestas Preferidas

- Código completo y funcional, no snippets parciales
- Incluir imports necesarios
- Incluir type hints
- Explicar brevemente decisiones no obvias
- Si hay múltiples formas, elegir la que sigue estas convenciones
