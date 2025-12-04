# ADR-003: Soft Delete obligatorio

## Estado
**Aceptado** - Enero 2025

## Contexto

En una aplicación financiera, los datos son extremadamente sensibles:
- Los usuarios pueden querer recuperar transacciones eliminadas por error
- Auditoría requiere historial completo
- Reportes fiscales necesitan datos históricos

Necesitamos decidir cómo manejar eliminaciones.

| Estrategia | Pros | Contras |
|------------|------|---------|
| Hard Delete | Simple, menos storage | Irrecuperable, sin auditoría |
| Soft Delete | Recuperable, auditable | Queries más complejas, más storage |
| Event Sourcing | Auditoría perfecta | Complejidad extrema, over-engineering |

## Decisión

**Soft Delete obligatorio** en todas las tablas mediante campo `deleted_at`.

### Implementación

#### Base Model

```python
# src/finanzas_tracker/models/base.py
from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=None
    )
```

#### Todos los modelos heredan

```python
class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    # ... campos
```

#### Repository automatiza soft-delete

```python
class BaseRepository(Generic[T]):
    def get(self, id: int) -> T | None:
        # Automáticamente excluye deleted
        stmt = select(self.model).where(
            self.model.id == id,
            self.model.deleted_at.is_(None)  # ← Filtro automático
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def soft_delete(self, id: int) -> bool:
        """NUNCA hacer DELETE real."""
        obj = self.get(id)
        if obj:
            obj.deleted_at = datetime.utcnow()
            self.db.commit()
            return True
        return False
```

#### API expone DELETE que hace soft-delete

```python
@router.delete("/{id}", status_code=204)
def delete_transaction(
    id: int,
    db: Session = Depends(get_db)
):
    """Elimina una transacción (soft delete)."""
    repo = TransactionRepository(db)
    if not repo.soft_delete(id):
        raise NotFoundError("Transacción no encontrada")
    return None
```

## Consecuencias

### Positivas
- **Recuperación**: Usuarios pueden pedir restaurar datos
- **Auditoría**: Historial completo para compliance
- **Seguridad**: Errores no son catastróficos
- **Reportes**: Datos fiscales siempre disponibles
- **Debug**: Fácil investigar problemas

### Negativas
- **Storage**: Datos crecen indefinidamente
- **Queries**: Siempre filtrar por `deleted_at IS NULL`
- **Performance**: Índices más grandes

### Mitigaciones
- **Storage**: Archiving a cold storage después de X años
- **Queries**: BaseRepository lo hace automático
- **Performance**: Índice parcial en PostgreSQL

```sql
-- Índice parcial para optimizar queries activas
CREATE INDEX idx_transactions_active 
ON transactions (id) 
WHERE deleted_at IS NULL;
```

## Reglas Estrictas

1. **NUNCA** usar `DELETE FROM` en código
2. **SIEMPRE** filtrar por `deleted_at IS NULL` en queries
3. **SIEMPRE** usar `soft_delete()` del repository
4. **EXCEPCIÓN**: Scripts de purge con aprobación expresa (GDPR)

## Recuperación de Datos

```python
# Solo para admin/soporte
def restore(self, id: int) -> bool:
    """Restaura un registro soft-deleted."""
    stmt = select(self.model).where(self.model.id == id)
    obj = self.db.execute(stmt).scalar_one_or_none()
    if obj and obj.deleted_at:
        obj.deleted_at = None
        self.db.commit()
        return True
    return False
```

## Referencias

- [Soft Delete Patterns](https://www.brentozar.com/archive/2020/02/soft-deletes-are-a-good-thing/)
- [GDPR Right to be Forgotten](https://gdpr.eu/right-to-be-forgotten/)
