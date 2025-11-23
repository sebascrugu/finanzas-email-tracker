"""Modelo de Alerta para notificaciones inteligentes."""

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base
from uuid import uuid4


class AlertType(str, Enum):
    """Tipos de alertas disponibles."""

    ANOMALY_DETECTED = "anomaly_detected"  # Transacción anómala detectada
    SUBSCRIPTION_DUE = "subscription_due"  # Suscripción próxima a vencerse
    BUDGET_EXCEEDED = "budget_exceeded"  # Presupuesto excedido
    CATEGORY_SPIKE = "category_spike"  # Gasto inusual en categoría
    MULTIPLE_PURCHASES = "multiple_purchases"  # Múltiples compras en corto tiempo
    HIGH_SPENDING_DAY = "high_spending_day"  # Día de gasto alto
    UNUSUAL_TIME = "unusual_time"  # Compra en horario inusual
    INTERNATIONAL_PURCHASE = "international_purchase"  # Compra internacional
    CREDIT_CARD_CLOSING = "credit_card_closing"  # Tarjeta de crédito próxima a cerrar
    MONTHLY_COMPARISON = "monthly_comparison"  # Comparación de gasto mensual
    SAVINGS_GOAL_PROGRESS = "savings_goal_progress"  # Progreso hacia meta de ahorro


class AlertSeverity(str, Enum):
    """Niveles de severidad de alertas."""

    INFO = "info"  # Informativa
    WARNING = "warning"  # Advertencia
    CRITICAL = "critical"  # Crítica (requiere atención inmediata)


class AlertStatus(str, Enum):
    """Estados de una alerta."""

    PENDING = "pending"  # Pendiente de revisar
    READ = "read"  # Leída pero no resuelta
    RESOLVED = "resolved"  # Resuelta/Atendida
    DISMISSED = "dismissed"  # Descartada


class Alert(Base):
    """
    Modelo de Alerta - Notificaciones Inteligentes.

    Representa alertas generadas automáticamente por el sistema
    para notificar al usuario sobre eventos importantes.
    """

    __tablename__ = "alerts"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único de la alerta",
    )

    # Relaciones
    profile_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        comment="ID del perfil al que pertenece la alerta",
    )
    transaction_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID de la transacción relacionada (si aplica)",
    )
    subscription_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID de la suscripción relacionada (si aplica)",
    )
    budget_id: Mapped[str | None] = mapped_column(
        String(26),
        ForeignKey("budgets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID del presupuesto relacionado (si aplica)",
    )

    # Tipo y severidad
    alert_type: Mapped[AlertType] = mapped_column(
        String(50),
        index=True,
        comment="Tipo de alerta",
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        String(20),
        index=True,
        default=AlertSeverity.INFO,
        comment="Nivel de severidad (info, warning, critical)",
    )
    status: Mapped[AlertStatus] = mapped_column(
        String(20),
        index=True,
        default=AlertStatus.PENDING,
        comment="Estado de la alerta (pending, read, resolved, dismissed)",
    )

    # Contenido
    title: Mapped[str] = mapped_column(
        String(200),
        comment="Título corto de la alerta",
    )
    message: Mapped[str] = mapped_column(
        Text,
        comment="Mensaje detallado de la alerta",
    )
    action_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL opcional para acción relacionada",
    )

    # Metadata
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fecha en que se leyó la alerta",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fecha en que se resolvió la alerta",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Fecha de creación de la alerta",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Fecha de última actualización",
    )

    # Relaciones ORM
    profile: Mapped["Profile"] = relationship("Profile", back_populates="alerts")
    transaction: Mapped["Transaction | None"] = relationship(
        "Transaction", back_populates="alerts"
    )
    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription", back_populates="alerts"
    )
    budget: Mapped["Budget | None"] = relationship("Budget", back_populates="alerts")

    def __repr__(self) -> str:
        """Representación en string del objeto."""
        return (
            f"<Alert(id={self.id}, type={self.alert_type}, "
            f"severity={self.severity}, status={self.status})>"
        )

    @property
    def is_pending(self) -> bool:
        """Retorna True si la alerta está pendiente."""
        return self.status == AlertStatus.PENDING

    @property
    def is_read(self) -> bool:
        """Retorna True si la alerta fue leída."""
        return self.status in (AlertStatus.READ, AlertStatus.RESOLVED, AlertStatus.DISMISSED)

    @property
    def is_critical(self) -> bool:
        """Retorna True si la alerta es crítica."""
        return self.severity == AlertSeverity.CRITICAL

    @property
    def emoji(self) -> str:
        """Retorna emoji apropiado según el tipo de alerta."""
        emoji_map = {
            AlertType.ANOMALY_DETECTED: "⚠️",
            AlertType.SUBSCRIPTION_DUE: "📅",
            AlertType.BUDGET_EXCEEDED: "💰",
            AlertType.CATEGORY_SPIKE: "📈",
            AlertType.MULTIPLE_PURCHASES: "🛒",
            AlertType.HIGH_SPENDING_DAY: "💸",
            AlertType.UNUSUAL_TIME: "🕐",
            AlertType.INTERNATIONAL_PURCHASE: "🌍",
        }
        return emoji_map.get(self.alert_type, "🔔")

    @property
    def severity_color(self) -> str:
        """Retorna color apropiado según la severidad."""
        color_map = {
            AlertSeverity.INFO: "blue",
            AlertSeverity.WARNING: "orange",
            AlertSeverity.CRITICAL: "red",
        }
        return color_map.get(self.severity, "gray")

    def mark_as_read(self) -> None:
        """Marca la alerta como leída."""
        if self.status == AlertStatus.PENDING:
            self.status = AlertStatus.READ
            self.read_at = datetime.now(UTC)

    def mark_as_resolved(self) -> None:
        """Marca la alerta como resuelta."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now(UTC)
        if not self.read_at:
            self.read_at = datetime.now(UTC)

    def dismiss(self) -> None:
        """Descarta la alerta."""
        self.status = AlertStatus.DISMISSED
        if not self.read_at:
            self.read_at = datetime.now(UTC)


class AlertConfig(Base):
    """
    Modelo de Configuración de Alertas.

    Permite a cada perfil configurar qué alertas quiere recibir.
    """

    __tablename__ = "alert_configs"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único de la configuración",
    )

    # Relación
    profile_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        comment="ID del perfil",
    )

    # Configuración de alertas
    enable_anomaly_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Habilitar alertas de anomalías detectadas",
    )
    enable_subscription_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Habilitar alertas de suscripciones próximas",
    )
    subscription_alert_days: Mapped[int] = mapped_column(
        default=3,
        comment="Días de anticipación para alertas de suscripciones",
    )
    enable_budget_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Habilitar alertas de presupuesto excedido",
    )
    budget_alert_threshold: Mapped[int] = mapped_column(
        default=90,
        comment="Porcentaje del presupuesto para alertar (ej: 90%)",
    )
    enable_category_spike_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Habilitar alertas de gastos inusuales por categoría",
    )
    enable_high_spending_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Habilitar alertas de días de gasto alto",
    )
    enable_international_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Habilitar alertas de compras internacionales",
    )
    enable_credit_card_closing_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Habilitar alertas de cierre de ciclo de tarjetas de crédito",
    )
    credit_card_alert_days: Mapped[int] = mapped_column(
        default=3,
        comment="Días de anticipación para alertas de cierre de tarjeta",
    )
    enable_savings_goal_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Habilitar alertas de progreso de metas de ahorro",
    )
    savings_goal_alert_frequency: Mapped[int] = mapped_column(
        default=7,
        comment="Frecuencia en días para alertas de progreso de metas",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Fecha de creación de la configuración",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Fecha de última actualización",
    )

    # Relaciones ORM
    profile: Mapped["Profile"] = relationship(
        "Profile", back_populates="alert_config", uselist=False
    )

    def __repr__(self) -> str:
        """Representación en string del objeto."""
        return f"<AlertConfig(profile_id={self.profile_id})>"
