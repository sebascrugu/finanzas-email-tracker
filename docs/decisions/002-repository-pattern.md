# ADR-002: Repository Pattern para acceso a datos

## Estado
**Aceptado** - Enero 2025

## Contexto

Necesitamos una estrategia para acceso a datos que:
1. Permita testing fácil con mocks
2. Centralice queries y lógica de soft-delete
3. Sea consistente en toda la aplicación
4. Siga principios SOLID

Las opciones consideradas:

| Patrón | Pros | Contras |
|--------|------|---------|
| Active Record | Simple, menos código | Difícil de testear, acoplado a ORM |
| Repository Pattern | Testable, separación clara | Más código, indirección |
| Query Objects | Muy flexible | Complejo, over-engineering |
| Raw SQLAlchemy | Flexible | Inconsistente, duplicación |

## Decisión

Implementamos **Repository Pattern** con un **BaseRepository genérico**.

### Implementación

```python
# src/finanzas_tracker/db/repositories/base.py
from typing import Generic, TypeVar
from sqlalchemy import select
from sqlalchemy.orm import Session

T = TypeVar("T")

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
        """Lista con paginación, excluyendo soft-deleted."""
        stmt = (
            select(self.model)
            .where(self.model.deleted_at.is_(None))
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars())

    def create(self, obj: T) -> T:
        """Crea y retorna con ID asignado."""
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, obj: T) -> T:
        """Actualiza y retorna."""
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def soft_delete(self, id: int) -> bool:
        """Marca deleted_at, NUNCA DELETE real."""
        obj = self.get(id)
        if obj:
            obj.deleted_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
```

### Repositorios Específicos

```python
# src/finanzas_tracker/db/repositories/transaction.py
class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Transaction)

    def get_by_date_range(
        self, 
        start: date, 
        end: date
    ) -> list[Transaction]:
        """Query específica del dominio."""
        stmt = (
            select(self.model)
            .where(
                self.model.deleted_at.is_(None),
                self.model.date >= start,
                self.model.date <= end
            )
            .order_by(self.model.date.desc())
        )
        return list(self.db.execute(stmt).scalars())
```

### Uso en Services

```python
class TransactionService:
    def __init__(self, db: Session) -> None:
        self.repository = TransactionRepository(db)
    
    def get_monthly_summary(self, month: int, year: int):
        start = date(year, month, 1)
        end = date(year, month + 1, 1) - timedelta(days=1)
        transactions = self.repository.get_by_date_range(start, end)
        # ... lógica de negocio
```

## Consecuencias

### Positivas
- **Testabilidad**: Fácil mockear repositorios en unit tests
- **Consistencia**: Soft-delete automático en todos los modelos
- **DRY**: BaseRepository elimina duplicación de CRUD
- **Separación de concerns**: Services no conocen detalles de SQLAlchemy
- **Extensibilidad**: Fácil agregar caching, logging, auditing

### Negativas
- **Más código**: Un archivo por repositorio
- **Indirección**: Un nivel más de abstracción
- **Learning curve**: Desarrolladores nuevos deben entender el patrón

### Trade-offs Aceptados
- El código extra vale la pena por la testabilidad
- La indirección es manejable con buena documentación
- Es un patrón estándar, fácil de entender para seniors

## Alternativas Descartadas

### Active Record (SQLAlchemy directo)
```python
# ❌ No usar
transaction = Transaction.query.get(id)
```
- Difícil de testear sin DB real
- No hay lugar centralizado para soft-delete

### Query Objects
```python
# ❌ Over-engineering para este proyecto
class GetTransactionsByDateQuery:
    def execute(self, start, end):
        ...
```
- Demasiada complejidad para queries simples

## Referencias

- [Martin Fowler - Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [SQLAlchemy 2.0 Best Practices](https://docs.sqlalchemy.org/en/20/)
