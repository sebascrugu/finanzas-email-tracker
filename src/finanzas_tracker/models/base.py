"""Base mixins para modelos SQLAlchemy - Multi-tenancy ready."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class TenantMixin:
    """
    Mixin para agregar tenant_id a modelos multi-tenant.

    Por ahora nullable=True para desarrollo single-tenant.
    Cuando se active multi-tenancy, cambiar a nullable=False
    y agregar filtro automático en queries.
    """

    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
    )

    @declared_attr
    def __table_args__(cls) -> tuple:
        """Agrega índice compuesto con tenant_id si la tabla tiene otros índices."""
        # Las subclases pueden extender esto
        return ()


class TimestampMixin:
    """
    Mixin para agregar timestamps created_at y updated_at.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
        comment="Fecha de creación del registro",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Fecha de última actualización",
    )


class SoftDeleteMixin:
    """
    Mixin para soft delete.

    NUNCA hacer DELETE real - siempre soft delete.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Fecha de eliminación (soft delete - nunca DELETE real)",
    )

    @property
    def is_deleted(self) -> bool:
        """Verifica si el registro está eliminado."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Marca el registro como eliminado."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restaura un registro eliminado."""
        self.deleted_at = None


class BaseModelMixin(TenantMixin, TimestampMixin, SoftDeleteMixin):
    """
    Mixin completo que incluye tenant_id, timestamps y soft delete.

    Usar este mixin para modelos nuevos:

    ```python
    class MyModel(BaseModelMixin, Base):
        __tablename__ = "my_table"
        id: Mapped[str] = mapped_column(String(36), primary_key=True)
        # ... otros campos
    ```
    """

    pass
