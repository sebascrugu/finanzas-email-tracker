# ADR-004: Decimal para campos monetarios

## Estado
**Aceptado** - Enero 2025

## Contexto

Las aplicaciones financieras requieren precisión exacta en cálculos monetarios. Los errores de redondeo son inaceptables.

Ejemplo del problema con Float:
```python
>>> 0.1 + 0.2
0.30000000000000004  # ❌ ERROR

>>> from decimal import Decimal
>>> Decimal("0.1") + Decimal("0.2")
Decimal('0.3')  # ✅ CORRECTO
```

## Decisión

**Usar `Decimal` en Python y `Numeric(12, 2)` en PostgreSQL** para todos los campos monetarios.

### Implementación

#### Modelo SQLAlchemy

```python
from decimal import Decimal
from sqlalchemy import Numeric
from sqlalchemy.orm import Mapped, mapped_column

class Transaction(Base):
    __tablename__ = "transactions"
    
    # ✅ Correcto: Numeric con precisión y escala
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),  # 12 dígitos total, 2 decimales
        nullable=False
    )
    
    # ❌ NUNCA usar Float para dinero
    # amount: Mapped[float] = mapped_column(Float)
```

#### Schema Pydantic

```python
from decimal import Decimal
from pydantic import BaseModel, Field

class TransactionCreate(BaseModel):
    amount: Decimal = Field(
        ...,
        ge=0,  # Mayor o igual a 0
        decimal_places=2,
        description="Monto en la moneda especificada"
    )
```

#### Serialización JSON

```python
from pydantic import ConfigDict

class TransactionResponse(BaseModel):
    amount: Decimal
    
    model_config = ConfigDict(
        from_attributes=True,
        # Serializa Decimal como string para evitar pérdida de precisión
        json_encoders={Decimal: str}
    )
```

#### Constantes y Cálculos

```python
from decimal import Decimal, ROUND_HALF_UP

# ✅ Constantes como strings
TAX_RATE = Decimal("0.13")  # IVA Costa Rica
ZERO = Decimal("0.00")

# ✅ Redondeo explícito
def calculate_total(subtotal: Decimal, tax_rate: Decimal) -> Decimal:
    tax = subtotal * tax_rate
    total = subtotal + tax
    # Redondear a 2 decimales
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

## Consecuencias

### Positivas
- **Precisión exacta**: Sin errores de punto flotante
- **Compliance**: Cumple estándares financieros
- **Consistencia DB↔Python**: Mismo tipo en ambos lados
- **Comparaciones seguras**: `Decimal("10.00") == Decimal("10.00")`

### Negativas
- **Sintaxis verbosa**: `Decimal("10.00")` vs `10.0`
- **Serialización**: Requiere manejo especial en JSON
- **Performance**: Marginalmente más lento que float (despreciable)

### Reglas Estrictas

1. **NUNCA** usar `Float` para dinero
2. **SIEMPRE** crear Decimal desde strings: `Decimal("10.00")`
3. **NUNCA** crear Decimal desde float: `Decimal(10.0)` ← MAL
4. **SIEMPRE** especificar precisión en Numeric: `Numeric(12, 2)`
5. **SIEMPRE** redondear explícitamente después de operaciones

## Formato de Display

```python
def format_crc(amount: Decimal) -> str:
    """Formatea como colones costarricenses."""
    return f"₡{amount:,.2f}"

# Ejemplo
format_crc(Decimal("15000.00"))  # "₡15,000.00"
```

## Rangos Soportados

Con `Numeric(12, 2)`:
- **Mínimo**: -9,999,999,999.99
- **Máximo**: 9,999,999,999.99 (~$20 billones)

Más que suficiente para finanzas personales.

## Referencias

- [Python Decimal Module](https://docs.python.org/3/library/decimal.html)
- [PostgreSQL Numeric Type](https://www.postgresql.org/docs/current/datatype-numeric.html)
- [IEEE 754 Floating Point Problems](https://floating-point-gui.de/)
