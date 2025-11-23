"""Modelo de Progreso del Onboarding."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from finanzas_tracker.core.database import Base


class OnboardingProgress(Base):
    """
    Modelo de Progreso del Onboarding.

    Rastrea el progreso del wizard de onboarding para cada email/perfil,
    permitiendo que el usuario pueda pausar y continuar después.

    Estados de cada paso:
    - not_started: No ha comenzado
    - in_progress: En progreso
    - completed: Completado
    - skipped: Saltado por el usuario
    """

    __tablename__ = "onboarding_progress"

    # IDs
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único del progreso",
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        comment="Email del usuario (único por onboarding)",
    )

    # Progreso general
    current_step: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Paso actual del wizard (1-6)",
    )

    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        comment="Si completó todo el onboarding",
    )

    # Estado de cada paso
    step1_welcome: Mapped[str] = mapped_column(
        String(20),
        default="not_started",
        comment="Estado del paso 1: Bienvenida",
    )

    step2_profile: Mapped[str] = mapped_column(
        String(20),
        default="not_started",
        comment="Estado del paso 2: Crear Perfil",
    )

    step3_email: Mapped[str] = mapped_column(
        String(20),
        default="not_started",
        comment="Estado del paso 3: Conectar Email",
    )

    step4_cards: Mapped[str] = mapped_column(
        String(20),
        default="not_started",
        comment="Estado del paso 4: Detectar Tarjetas",
    )

    step5_income: Mapped[str] = mapped_column(
        String(20),
        default="not_started",
        comment="Estado del paso 5: Configurar Ingreso",
    )

    step6_import: Mapped[str] = mapped_column(
        String(20),
        default="not_started",
        comment="Estado del paso 6: Primera Importación",
    )

    # Datos temporales del wizard
    profile_id: Mapped[str | None] = mapped_column(
        String(36),
        comment="ID del perfil creado",
    )

    detected_cards_count: Mapped[int | None] = mapped_column(
        Integer,
        comment="Número de tarjetas detectadas",
    )

    imported_transactions_count: Mapped[int | None] = mapped_column(
        Integer,
        comment="Número de transacciones importadas",
    )

    # PDF Reconciliation (Step 3.5 - Nuevo)
    bank_statement_uploaded: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Si subió el estado de cuenta PDF durante onboarding",
    )

    bank_statement_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="ID del BankStatement procesado durante onboarding",
    )

    reconciliation_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Si completó la reconciliación inicial con PDF",
    )

    reconciliation_summary: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Resumen de la reconciliación inicial (matched, missing, etc.)",
    )

    transactions_added_from_pdf: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Número de transacciones agregadas automáticamente desde el PDF",
    )

    # Metadata
    wizard_version: Mapped[str] = mapped_column(
        String(10),
        default="1.0",
        comment="Versión del wizard para compatibilidad futura",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        comment="Notas adicionales o errores encontrados",
    )

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Cuándo empezó el onboarding",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Cuándo completó el onboarding",
    )

    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Última actividad en el wizard",
    )

    @property
    def progress_percentage(self) -> float:
        """Porcentaje de progreso del onboarding (0-100)."""
        steps = [
            self.step1_welcome,
            self.step2_profile,
            self.step3_email,
            self.step4_cards,
            self.step5_income,
            self.step6_import,
        ]

        completed = sum(1 for step in steps if step == "completed")
        total = len(steps)

        return (completed / total) * 100 if total > 0 else 0

    @property
    def can_skip_onboarding(self) -> bool:
        """True si puede saltar el onboarding (ya tiene perfil configurado)."""
        return self.profile_id is not None and self.is_completed

    def mark_step_completed(self, step: int) -> None:
        """Marca un paso como completado."""
        step_map = {
            1: "step1_welcome",
            2: "step2_profile",
            3: "step3_email",
            4: "step4_cards",
            5: "step5_income",
            6: "step6_import",
        }

        if step in step_map:
            setattr(self, step_map[step], "completed")
            self.last_activity_at = datetime.now(UTC)

        # Si completó el paso 6, marcar todo como completado
        if step == 6:
            self.is_completed = True
            self.completed_at = datetime.now(UTC)

    def __repr__(self) -> str:
        """Representación en string."""
        return (
            f"<OnboardingProgress(email={self.email}, step={self.current_step}, "
            f"progress={self.progress_percentage:.1f}%)>"
        )
