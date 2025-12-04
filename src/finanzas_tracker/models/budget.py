"""Modelo de presupuesto por categoría."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


class Budget(Base):
    """
    Modelo para almacenar presupuestos mensuales por categoría.

    Cada registro representa un límite de gasto para una categoría específica
    en un mes específico. Ejemplo: "Comida fuera - Nov 2025: ₡100,000"
    """

    __tablename__ = "budgets"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único del presupuesto",
    )

    # Multi-tenancy (futuro)
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
    )

    # Relación con perfil
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        comment="ID del perfil al que pertenece este presupuesto",
    )

    # Categoría presupuestada
    category_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("subcategories.id", ondelete="CASCADE"),
        index=True,
        comment="ID de la subcategoría presupuestada",
    )

    # Mes del presupuesto
    mes: Mapped[date] = mapped_column(
        Date,
        index=True,
        comment="Primer día del mes para este presupuesto (ej: 2025-11-01)",
    )

    # Límite de gasto
    amount_crc: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Límite de gasto en colones para esta categoría este mes",
    )

    # Alias para compatibilidad
    monto_limite: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Alias de amount_crc para compatibilidad",
    )

    # Metadatos
    notas: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Notas sobre este presupuesto",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
        comment="Fecha de creación del presupuesto",
    )

    # Relaciones
    profile: Mapped["Profile"] = relationship("Profile", back_populates="budgets")
    category: Mapped["Subcategory"] = relationship("Subcategory")

    # Constraints e índices
    __table_args__ = (
        CheckConstraint("amount_crc > 0", name="check_budget_amount_positive"),
        CheckConstraint("monto_limite > 0", name="check_budget_monto_positive"),
        # Un solo presupuesto por categoría por mes por perfil
        Index("ix_budgets_unique_category_month", "profile_id", "category_id", "mes", unique=True),
        Index("ix_budgets_profile_mes", "profile_id", "mes"),
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<Budget(profile_id={self.profile_id[:8]}..., "
            f"category_id={self.category_id[:8]}..., "
            f"mes={self.mes.strftime('%Y-%m')}, "
            f"limit=₡{self.amount_crc:,.0f})>"
        )

    @property
    def mes_nombre(self) -> str:
        """Retorna el mes en formato legible."""
        meses = {
            1: "Enero",
            2: "Febrero",
            3: "Marzo",
            4: "Abril",
            5: "Mayo",
            6: "Junio",
            7: "Julio",
            8: "Agosto",
            9: "Septiembre",
            10: "Octubre",
            11: "Noviembre",
            12: "Diciembre",
        }
        return f"{meses[self.mes.month]} {self.mes.year}"
