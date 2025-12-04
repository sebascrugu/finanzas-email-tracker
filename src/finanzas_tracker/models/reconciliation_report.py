"""Modelo de Reporte de Reconciliación mensual."""

__all__ = ["ReconciliationReport"]

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import BankName


class ReconciliationStatus(str, Enum):
    """Estado del proceso de reconciliación."""

    PENDING = "pendiente"  # Iniciado pero no completado
    IN_PROGRESS = "en_proceso"  # Usuario revisando discrepancias
    COMPLETED = "completada"  # Todas las transacciones verificadas
    FAILED = "fallida"  # Error en el proceso


class ReconciliationReport(Base):
    """
    Reporte de reconciliación mensual.

    Compara las transacciones importadas con el estado de cuenta PDF
    del banco para detectar discrepancias, transacciones faltantes
    y duplicados.

    Ejemplo de uso:
        - Usuario recibe estado de cuenta mensual de BAC (PDF)
        - Sistema compara transacciones importadas vs PDF
        - Genera reporte con matches, discrepancias, orphans
    """

    __tablename__ = "reconciliation_reports"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único del reporte",
    )

    # Relación con Profile
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="ID del perfil dueño de este reporte",
    )

    # Multi-tenancy (futuro)
    tenant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
    )

    # Información del período
    banco: Mapped[BankName] = mapped_column(
        String(20),
        nullable=False,
        comment="Banco del estado de cuenta",
    )
    periodo_inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Fecha de inicio del período (ej: 01-Nov-2024)",
    )
    periodo_fin: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Fecha de fin del período (ej: 30-Nov-2024)",
    )

    # Tipo de cuenta (tarjeta de crédito vs cuenta corriente)
    es_tarjeta_credito: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="True si es estado de tarjeta de crédito, False si es cuenta corriente",
    )
    card_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="ID de la tarjeta de crédito (si aplica)",
    )
    account_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="ID de la cuenta bancaria (si aplica)",
    )

    # Totales del estado de cuenta (PDF)
    total_estado_cuenta: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        comment="Total de transacciones según el PDF del banco",
    )
    total_importado: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        comment="Total de transacciones importadas al sistema",
    )
    diferencia: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Diferencia entre estado de cuenta e importado",
    )

    # Contadores de transacciones
    transacciones_estado_cuenta: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Número de transacciones en el PDF",
    )
    transacciones_importadas: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Número de transacciones importadas",
    )
    transacciones_matched: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Transacciones que coinciden exactamente",
    )
    transacciones_discrepantes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Transacciones con diferencias de monto",
    )
    transacciones_faltantes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Transacciones en PDF pero no importadas",
    )
    transacciones_huerfanas: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Transacciones importadas pero no en PDF",
    )

    # Estado del proceso
    estado: Mapped[str] = mapped_column(
        String(20),
        default=ReconciliationStatus.PENDING.value,
        index=True,
        comment="Estado: pendiente, en_proceso, completada, fallida",
    )

    # Detalles adicionales
    notas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notas del usuario sobre la reconciliación",
    )
    detalles_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON con detalles de matches, discrepancias, etc.",
    )

    # Archivo PDF fuente
    pdf_email_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="ID del email del cual se extrajo el PDF",
    )
    pdf_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Nombre del archivo PDF procesado",
    )

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Fecha de eliminación (soft delete)",
    )

    # Metadatos
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
        comment="Cuándo se creó el reporte",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Última actualización",
    )
    completado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Cuándo se completó la reconciliación",
    )

    # Relaciones
    profile: Mapped["Profile"] = relationship("Profile", back_populates="reconciliation_reports")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="reconciliation_report",
        foreign_keys="Transaction.reconciliacion_id",
    )

    # Constraints e índices
    __table_args__ = (
        CheckConstraint(
            "periodo_inicio < periodo_fin",
            name="check_reconciliation_periodo_valid",
        ),
        Index("ix_reconciliation_profile_periodo", "profile_id", "periodo_inicio", "periodo_fin"),
        Index("ix_reconciliation_profile_banco", "profile_id", "banco"),
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<ReconciliationReport(id={self.id[:8]}, "
            f"banco={self.banco.value}, "
            f"periodo={self.periodo_inicio.date()} - {self.periodo_fin.date()}, "
            f"estado={self.estado})>"
        )

    @property
    def tiene_discrepancias(self) -> bool:
        """Retorna True si hay diferencias que revisar."""
        return (
            self.transacciones_discrepantes > 0
            or self.transacciones_faltantes > 0
            or self.transacciones_huerfanas > 0
        )

    @property
    def porcentaje_match(self) -> float:
        """Porcentaje de transacciones que matchearon exactamente."""
        if self.transacciones_estado_cuenta == 0:
            return 100.0
        return (self.transacciones_matched / self.transacciones_estado_cuenta) * 100

    @property
    def esta_completa(self) -> bool:
        """Verifica si la reconciliación está completa."""
        return self.estado == ReconciliationStatus.COMPLETED.value

    def marcar_completa(self) -> None:
        """Marca la reconciliación como completada."""
        self.estado = ReconciliationStatus.COMPLETED.value
        self.completado_at = datetime.now(UTC)

    def soft_delete(self) -> None:
        """Marca el reporte como eliminado (soft delete)."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restaura un reporte eliminado."""
        self.deleted_at = None
