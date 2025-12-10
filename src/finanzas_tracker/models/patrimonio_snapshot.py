"""Modelo de Snapshot de Patrimonio."""

__all__ = ["PatrimonioSnapshot"]

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


if TYPE_CHECKING:
    from finanzas_tracker.models.profile import Profile


class SnapshotType(str, Enum):
    """Tipo de snapshot de patrimonio."""

    MANUAL = "manual"  # Usuario capturó snapshot manualmente
    AUTOMATIC = "automatico"  # Sistema capturó por schedule (fin de mes)
    ONBOARDING = "onboarding"  # Primera captura durante onboarding
    RECONCILIATION = "reconciliacion"  # Capturado durante reconciliación mensual


class PatrimonioSnapshot(Base):
    """
    Snapshot del patrimonio en un momento específico.

    Captura el estado financiero del usuario en un punto en el tiempo,
    permitiendo calcular tendencias y comparar períodos.

    Notas sobre patrimonio:
    - Patrimonio = Activos - Deuda de tarjetas de crédito
    - Activos = Cuentas corrientes + Ahorros + Inversiones
    - Deuda TC = Saldo pendiente de tarjetas de crédito

    Importante:
    - Las transacciones de tarjeta de crédito NO afectan patrimonio
      (el gasto ya ocurrió, la TC es solo el vehículo de pago)
    - Solo el PAGO de la tarjeta afecta las cuentas corrientes
    - Las transferencias entre cuentas propias no cambian patrimonio neto
    """

    __tablename__ = "patrimonio_snapshots"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único del snapshot",
    )

    # Relación con Profile
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="ID del perfil dueño de este snapshot",
    )

    # Multi-tenancy (futuro)
    tenant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
    )

    # Fecha del snapshot
    fecha_snapshot: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Fecha y hora del snapshot",
    )
    tipo: Mapped[str] = mapped_column(
        String(20),
        default=SnapshotType.AUTOMATIC.value,
        comment="Tipo: manual, automatico, onboarding, reconciliacion",
    )

    # ====================================
    # Desglose de Activos
    # ====================================

    # Cuentas bancarias (CRC)
    saldo_cuentas_crc: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total en cuentas bancarias (colones)",
    )

    # Cuentas bancarias (USD)
    saldo_cuentas_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total en cuentas bancarias (dólares)",
    )

    # Inversiones
    saldo_inversiones_crc: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total en inversiones (colones)",
    )
    saldo_inversiones_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total en inversiones (dólares)",
    )

    # ====================================
    # Desglose de Deudas
    # ====================================

    # Deuda de tarjetas de crédito
    deuda_tarjetas_crc: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Deuda total en tarjetas de crédito (colones)",
    )
    deuda_tarjetas_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Deuda total en tarjetas de crédito (dólares)",
    )

    # Otros préstamos (futuro)
    deuda_prestamos_crc: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Deuda en préstamos (colones)",
    )
    deuda_prestamos_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Deuda en préstamos (dólares)",
    )

    # ====================================
    # Totales Calculados (en CRC)
    # ====================================

    # Tipo de cambio usado para conversión
    tipo_cambio_usd: Mapped[Decimal] = mapped_column(
        Numeric(8, 2),
        nullable=False,
        default=Decimal("510.00"),
        comment="Tipo de cambio USD/CRC usado para este snapshot",
    )

    # Total de activos (todo convertido a CRC)
    total_activos_crc: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total de activos en colones (cuentas + inversiones)",
    )

    # Total de deudas (todo convertido a CRC)
    total_deudas_crc: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total de deudas en colones (tarjetas + préstamos)",
    )

    # Patrimonio neto = Activos - Deudas
    patrimonio_neto_crc: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Patrimonio neto en colones (activos - deudas)",
    )

    # Cambio respecto al snapshot anterior
    cambio_vs_anterior: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
        comment="Cambio en patrimonio vs snapshot anterior (puede ser negativo)",
    )
    cambio_porcentual: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="Cambio porcentual vs snapshot anterior",
    )

    # ====================================
    # Metadatos
    # ====================================

    # Notas adicionales
    notas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notas opcionales del usuario",
    )

    # Detalles JSON (para desglose por cuenta/tarjeta)
    detalles_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON con desglose detallado por cuenta/tarjeta",
    )

    # Es el snapshot inicial (FECHA_BASE)
    es_fecha_base: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        comment="True si es el snapshot de FECHA_BASE (inicio de tracking)",
    )

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Fecha de eliminación (soft delete)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
        comment="Cuándo se creó el registro",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Última actualización",
    )

    # Relaciones
    profile: Mapped["Profile"] = relationship("Profile", back_populates="patrimonio_snapshots")

    # Índices
    __table_args__ = (
        Index("ix_patrimonio_profile_fecha", "profile_id", "fecha_snapshot"),
        Index("ix_patrimonio_fecha_base", "profile_id", "es_fecha_base"),
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<PatrimonioSnapshot(id={self.id[:8]}, "
            f"fecha={self.fecha_snapshot.date()}, "
            f"patrimonio=₡{self.patrimonio_neto_crc:,.2f})>"
        )

    @property
    def patrimonio_display(self) -> str:
        """Formato de display del patrimonio."""
        return f"₡{self.patrimonio_neto_crc:,.2f}"

    @property
    def cambio_display(self) -> str | None:
        """Formato de display del cambio vs anterior."""
        if self.cambio_vs_anterior is None:
            return None
        signo = "+" if self.cambio_vs_anterior >= 0 else ""
        return f"{signo}₡{self.cambio_vs_anterior:,.2f}"

    def calcular_totales(self) -> None:
        """
        Calcula los totales a partir del desglose.

        Debe llamarse después de actualizar los saldos individuales.
        """
        # Total activos
        activos_usd_en_crc = self.saldo_cuentas_usd * self.tipo_cambio_usd
        inversiones_usd_en_crc = self.saldo_inversiones_usd * self.tipo_cambio_usd
        self.total_activos_crc = (
            self.saldo_cuentas_crc
            + activos_usd_en_crc
            + self.saldo_inversiones_crc
            + inversiones_usd_en_crc
        )

        # Total deudas
        deuda_usd_en_crc = self.deuda_tarjetas_usd * self.tipo_cambio_usd
        prestamos_usd_en_crc = self.deuda_prestamos_usd * self.tipo_cambio_usd
        self.total_deudas_crc = (
            self.deuda_tarjetas_crc
            + deuda_usd_en_crc
            + self.deuda_prestamos_crc
            + prestamos_usd_en_crc
        )

        # Patrimonio neto
        self.patrimonio_neto_crc = self.total_activos_crc - self.total_deudas_crc

    def calcular_cambio(self, snapshot_anterior: "PatrimonioSnapshot | None") -> None:
        """
        Calcula el cambio respecto al snapshot anterior.

        Args:
            snapshot_anterior: Snapshot previo para comparar (None si es el primero)
        """
        if snapshot_anterior is None:
            self.cambio_vs_anterior = None
            self.cambio_porcentual = None
            return

        self.cambio_vs_anterior = self.patrimonio_neto_crc - snapshot_anterior.patrimonio_neto_crc

        if snapshot_anterior.patrimonio_neto_crc != 0:
            self.cambio_porcentual = (
                self.cambio_vs_anterior / snapshot_anterior.patrimonio_neto_crc
            ) * 100
        else:
            self.cambio_porcentual = None

    def soft_delete(self) -> None:
        """Marca el snapshot como eliminado (soft delete)."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restaura un snapshot eliminado."""
        self.deleted_at = None
