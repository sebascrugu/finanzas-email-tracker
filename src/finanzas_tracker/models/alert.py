"""Modelo de Alerta para notificaciones inteligentes."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import AlertPriority, AlertStatus, AlertType


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
    card_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID de la tarjeta relacionada (si aplica)",
    )
    savings_goal_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("savings_goals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID de la meta de ahorro relacionada (si aplica)",
    )

    # Tipo y prioridad
    alert_type: Mapped[AlertType] = mapped_column(
        String(50),
        index=True,
        comment="Tipo de alerta",
    )
    priority: Mapped[AlertPriority] = mapped_column(
        String(20),
        index=True,
        default=AlertPriority.LOW,
        comment="Nivel de prioridad (critical, high, medium, low)",
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
    card: Mapped["Card | None"] = relationship("Card", back_populates="alerts")
    savings_goal: Mapped["SavingsGoal | None"] = relationship(
        "SavingsGoal", back_populates="alerts"
    )

    def __repr__(self) -> str:
        """Representación en string del objeto."""
        return (
            f"<Alert(id={self.id}, type={self.alert_type}, "
            f"priority={self.priority}, status={self.status})>"
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
        return self.priority == AlertPriority.CRITICAL

    @property
    def emoji(self) -> str:
        """Retorna emoji apropiado según el tipo de alerta."""
        emoji_map = {
            # Fase 1 - MVP Critical Alerts
            AlertType.STATEMENT_UPLOAD_REMINDER: "📄",
            AlertType.CREDIT_CARD_PAYMENT_DUE: "💳",
            AlertType.SPENDING_EXCEEDS_INCOME: "🚨",
            AlertType.BUDGET_80_PERCENT: "⚠️",
            AlertType.BUDGET_100_PERCENT: "🔴",
            AlertType.SUBSCRIPTION_RENEWAL: "📅",
            AlertType.DUPLICATE_TRANSACTION: "⚠️",
            AlertType.HIGH_INTEREST_PROJECTION: "💰",
            AlertType.CARD_EXPIRATION: "💳",
            AlertType.UNCATEGORIZED_TRANSACTIONS: "📊",
            # Fase 2 - Negative/Preventive Alerts
            AlertType.OVERDRAFT_PROJECTION: "⛔",
            AlertType.LOW_SAVINGS_WARNING: "📉",
            AlertType.UNKNOWN_MERCHANT_HIGH: "❓",
            AlertType.CREDIT_UTILIZATION_HIGH: "📊",
            AlertType.SPENDING_VELOCITY_HIGH: "⚡",
            AlertType.SEASONAL_SPENDING_WARNING: "🎄",
            AlertType.GOAL_BEHIND_SCHEDULE: "⏰",
            # Fase 2 - Positive Alerts (Gamification/Motivation)
            AlertType.SPENDING_REDUCTION: "🎯",
            AlertType.SAVINGS_MILESTONE: "🏆",
            AlertType.BUDGET_UNDER_TARGET: "✨",
            AlertType.DEBT_PAYMENT_PROGRESS: "💪",
            AlertType.STREAK_ACHIEVEMENT: "🔥",
            AlertType.CATEGORY_IMPROVEMENT: "📈",
            AlertType.ZERO_EATING_OUT: "🥗",
            AlertType.EMERGENCY_FUND_MILESTONE: "🛡️",
        }
        return emoji_map.get(self.alert_type, "🔔")

    @property
    def priority_color(self) -> str:
        """Retorna color apropiado según la prioridad."""
        color_map = {
            AlertPriority.CRITICAL: "red",
            AlertPriority.HIGH: "orange",
            AlertPriority.MEDIUM: "yellow",
            AlertPriority.LOW: "blue",
        }
        return color_map.get(self.priority, "gray")

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
    enable_spending_forecast_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Habilitar alertas de predicción de gasto mensual",
    )
    enable_budget_forecast_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Habilitar alertas si excederá presupuesto según predicción",
    )
    enable_category_trend_alerts: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Habilitar alertas de tendencias por categoría",
    )
    forecast_alert_frequency: Mapped[int] = mapped_column(
        default=7,
        comment="Frecuencia en días para alertas de predicciones (default: semanal)",
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
