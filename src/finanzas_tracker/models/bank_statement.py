"""Modelo de estado de cuenta bancario."""

__all__ = ["BankStatement"]

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import BankName


class BankStatement(Base):
    """
    Modelo para almacenar estados de cuenta bancarios procesados.

    Cada registro representa un estado de cuenta PDF que fue procesado
    para reconciliación con transacciones de correos electrónicos.

    Use cases:
    - Validar que todas las transacciones del banco están en el sistema
    - Detectar correos no recibidos o perdidos
    - Identificar discrepancias entre correos y estado de cuenta oficial
    - Mantener historial de reconciliaciones
    """

    __tablename__ = "bank_statements"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único del estado de cuenta",
    )

    # Relación con perfil
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        comment="ID del perfil al que pertenece este estado de cuenta",
    )

    # Información del estado de cuenta
    banco: Mapped[BankName] = mapped_column(
        String(50),
        index=True,
        comment="Banco: bac o popular",
    )
    cuenta_iban: Mapped[str] = mapped_column(
        String(50),
        comment="IBAN de la cuenta (ej: CR72 0102 0000 9661 5395 99)",
    )
    fecha_corte: Mapped[date] = mapped_column(
        Date,
        index=True,
        comment="Fecha de corte del estado de cuenta",
    )
    periodo: Mapped[str] = mapped_column(
        String(20),
        comment="Período del estado (ej: '2025-10', 'Octubre 2025')",
    )

    # Metadata del PDF
    pdf_filename: Mapped[str] = mapped_column(
        String(255),
        comment="Nombre original del archivo PDF",
    )
    pdf_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Hash SHA-256 del PDF para detectar duplicados",
    )

    # Datos extraídos del PDF
    saldo_inicial: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Saldo inicial del período",
    )
    saldo_final: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Saldo final del período",
    )
    total_debitos: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Total de débitos en el período",
    )
    total_creditos: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Total de créditos en el período",
    )

    # Estadísticas de reconciliación
    total_transactions_pdf: Mapped[int] = mapped_column(
        default=0,
        comment="Total de transacciones encontradas en el PDF",
    )
    matched_count: Mapped[int] = mapped_column(
        default=0,
        comment="Transacciones que hicieron match con emails",
    )
    missing_in_emails_count: Mapped[int] = mapped_column(
        default=0,
        comment="Transacciones en PDF pero no en emails",
    )
    missing_in_statement_count: Mapped[int] = mapped_column(
        default=0,
        comment="Transacciones en emails pero no en PDF",
    )
    discrepancies_count: Mapped[int] = mapped_column(
        default=0,
        comment="Transacciones con discrepancias (monto diferente, etc.)",
    )

    # Reporte de reconciliación (JSON)
    reconciliation_report: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Reporte completo de reconciliación en JSON",
    )

    # Estado del procesamiento
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        index=True,
        comment="Estado: pending, processing, completed, failed",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Mensaje de error si falló el procesamiento",
    )

    # Notas del usuario
    notas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notas adicionales del usuario sobre la reconciliación",
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
        comment="Fecha de creación del registro",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Fecha de última actualización",
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fecha en que se completó el procesamiento",
    )

    # Relaciones
    profile: Mapped["Profile"] = relationship("Profile", back_populates="bank_statements")

    # Índices
    __table_args__ = (
        Index("ix_bank_statements_profile_fecha", "profile_id", "fecha_corte"),
        Index("ix_bank_statements_profile_banco", "profile_id", "banco"),
        Index("ix_bank_statements_status", "processing_status"),
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<BankStatement(id={self.id[:8]}, "
            f"banco={self.banco}, "
            f"fecha_corte={self.fecha_corte}, "
            f"matched={self.matched_count}/{self.total_transactions_pdf})>"
        )

    @property
    def match_percentage(self) -> float:
        """Retorna el porcentaje de transacciones que hicieron match."""
        if self.total_transactions_pdf == 0:
            return 0.0
        return (self.matched_count / self.total_transactions_pdf) * 100

    @property
    def is_fully_reconciled(self) -> bool:
        """Retorna True si todas las transacciones están reconciliadas."""
        return (
            self.missing_in_emails_count == 0
            and self.missing_in_statement_count == 0
            and self.discrepancies_count == 0
        )

    @property
    def reconciliation_status(self) -> str:
        """
        Retorna el estado de reconciliación.

        Returns:
            - 'perfect': 100% reconciliado sin discrepancias
            - 'good': >90% reconciliado con pocas discrepancias
            - 'needs_review': <90% reconciliado o con discrepancias
            - 'pending': No procesado aún
        """
        if self.processing_status != "completed":
            return "pending"

        if self.is_fully_reconciled:
            return "perfect"

        match_pct = self.match_percentage
        if match_pct >= 90 and self.discrepancies_count <= 2:
            return "good"

        return "needs_review"

    @property
    def esta_activo(self) -> bool:
        """Verifica si el statement no ha sido eliminado (soft delete)."""
        return self.deleted_at is None

    def soft_delete(self) -> None:
        """Marca el statement como eliminado (soft delete)."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restaura un statement eliminado."""
        self.deleted_at = None

    def mark_as_processing(self) -> None:
        """Marca el statement como en procesamiento."""
        self.processing_status = "processing"

    def mark_as_completed(self) -> None:
        """Marca el statement como completado."""
        self.processing_status = "completed"
        self.processed_at = datetime.now(UTC)

    def mark_as_failed(self, error: str) -> None:
        """Marca el statement como fallido."""
        self.processing_status = "failed"
        self.error_message = error
        self.processed_at = datetime.now(UTC)

    # Validators
    @validates("cuenta_iban")
    def validate_cuenta_iban(self, key: str, value: str) -> str:
        """Valida formato básico de IBAN."""
        if not value or not value.strip():
            raise ValueError("El IBAN no puede estar vacío")
        value = value.strip().upper()
        # Formato básico: CR seguido de dígitos y espacios
        if not value.startswith("CR"):
            raise ValueError(f"IBAN debe comenzar con 'CR': '{value}'")
        return value

    @validates("pdf_filename")
    def validate_pdf_filename(self, key: str, value: str) -> str:
        """Valida que el filename no esté vacío."""
        if not value or not value.strip():
            raise ValueError("El nombre del archivo PDF no puede estar vacío")
        return value.strip()

    @validates("processing_status")
    def validate_processing_status(self, key: str, value: str) -> str:
        """Valida que el status sea válido."""
        valid_statuses = ["pending", "processing", "completed", "failed"]
        if value not in valid_statuses:
            raise ValueError(f"Status inválido: '{value}'. Debe ser uno de: {valid_statuses}")
        return value
