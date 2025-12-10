"""Modelo para preguntas pendientes al usuario durante onboarding/reconciliación."""

__all__ = ["PendingQuestion", "QuestionType", "QuestionPriority", "QuestionStatus"]

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base

if TYPE_CHECKING:
    from finanzas_tracker.models.profile import Profile
    from finanzas_tracker.models.transaction import Transaction


class QuestionType(str, Enum):
    """Tipos de preguntas que el sistema puede hacer al usuario."""

    # SINPE sin descripción clara
    SINPE_SIN_DESCRIPCION = "sinpe_sin_descripcion"

    # Comercio desconocido - no sabemos qué categoría
    COMERCIO_DESCONOCIDO = "comercio_desconocido"

    # Transacción que no matchea entre correo y estado de cuenta
    MONTO_NO_MATCHEA = "monto_no_matchea"

    # Transacción en estado de cuenta pero no en correos
    SOLO_EN_ESTADO_CUENTA = "solo_en_estado_cuenta"

    # Transacción en correos pero no en estado de cuenta
    SOLO_EN_CORREOS = "solo_en_correos"

    # Categoría ambigua - comercio puede ser varias cosas
    CATEGORIA_AMBIGUA = "categoria_ambigua"

    # Confirmación de categoría sugerida por IA
    CONFIRMAR_CATEGORIA = "confirmar_categoria"

    # Pregunta genérica
    OTRO = "otro"


class QuestionPriority(str, Enum):
    """Prioridad de la pregunta (basada en monto e importancia)."""

    ALTA = "alta"      # Montos grandes, discrepancias significativas
    MEDIA = "media"    # Montos medianos, categorización
    BAJA = "baja"      # Montos pequeños, opcional responder


class QuestionStatus(str, Enum):
    """Estado de la pregunta."""

    PENDIENTE = "pendiente"
    RESPONDIDA = "respondida"
    IGNORADA = "ignorada"      # Usuario decidió no responder
    AUTO_RESUELTA = "auto_resuelta"  # Sistema la resolvió automáticamente


class PendingQuestion(Base):
    """
    Pregunta pendiente para el usuario.

    Se generan durante:
    - Onboarding (SINPEs sin descripción, comercios desconocidos)
    - Reconciliación (transacciones que no matchean)
    - Categorización diaria (comercios nuevos)

    Ejemplos:
        - "¿Qué es este SINPE de ₡5,000 a 8888-1234?"
        - "No encontramos 'UBER EATS' en tus correos, ¿es correcto?"
        - "¿'WALMART' es Supermercado o Otro?"
    """

    __tablename__ = "pending_questions"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único de la pregunta",
    )

    # Multi-tenancy (futuro)
    tenant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
    )

    # Relación con Profile
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="ID del perfil dueño de esta pregunta",
    )

    # Relación opcional con Transaction
    transaction_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID de la transacción relacionada (si aplica)",
    )

    # Tipo y prioridad
    tipo: Mapped[QuestionType] = mapped_column(
        String(30),
        nullable=False,
        comment="Tipo de pregunta",
    )
    prioridad: Mapped[QuestionPriority] = mapped_column(
        String(10),
        nullable=False,
        default=QuestionPriority.MEDIA,
        comment="Prioridad de la pregunta",
    )
    status: Mapped[QuestionStatus] = mapped_column(
        String(20),
        nullable=False,
        default=QuestionStatus.PENDIENTE,
        index=True,
        comment="Estado de la pregunta",
    )

    # Contenido de la pregunta
    pregunta: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Texto de la pregunta para mostrar al usuario",
    )
    contexto: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Contexto adicional (JSON con datos relevantes)",
    )

    # Opciones predefinidas (JSON array)
    opciones: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Opciones de respuesta en formato JSON array",
    )

    # Monto relacionado (para ordenar por importancia)
    monto_relacionado: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2),
        nullable=True,
        comment="Monto de la transacción relacionada",
    )

    # Respuesta del usuario
    respuesta: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Respuesta del usuario",
    )
    respondida_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fecha/hora en que se respondió",
    )

    # Origen
    origen: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="onboarding",
        comment="De dónde vino: onboarding, reconciliacion, sync_diario",
    )

    # Orden de presentación
    orden: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Orden para mostrar (menor = primero)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Fecha de creación",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Última actualización",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Soft delete",
    )

    # Relaciones
    profile: Mapped["Profile"] = relationship(
        "Profile",
        back_populates="pending_questions",
    )
    transaction: Mapped["Transaction | None"] = relationship(
        "Transaction",
        back_populates="pending_questions",
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return f"<PendingQuestion(tipo={self.tipo.value}, status={self.status.value})>"

    @property
    def es_pendiente(self) -> bool:
        """Retorna True si la pregunta está pendiente."""
        return self.status == QuestionStatus.PENDIENTE

    def responder(self, respuesta: str) -> None:
        """Marca la pregunta como respondida."""
        self.respuesta = respuesta
        self.status = QuestionStatus.RESPONDIDA
        self.respondida_en = datetime.now(UTC)

    def ignorar(self) -> None:
        """Marca la pregunta como ignorada."""
        self.status = QuestionStatus.IGNORADA
        self.respondida_en = datetime.now(UTC)

    def auto_resolver(self, respuesta: str) -> None:
        """Marca la pregunta como auto-resuelta por el sistema."""
        self.respuesta = respuesta
        self.status = QuestionStatus.AUTO_RESUELTA
        self.respondida_en = datetime.now(UTC)

    @classmethod
    def crear_pregunta_sinpe(
        cls,
        profile_id: str,
        transaction_id: str,
        numero_telefono: str,
        monto: Decimal,
        fecha: datetime,
    ) -> "PendingQuestion":
        """Crea una pregunta para un SINPE sin descripción."""
        return cls(
            profile_id=profile_id,
            transaction_id=transaction_id,
            tipo=QuestionType.SINPE_SIN_DESCRIPCION,
            prioridad=QuestionPriority.ALTA if monto > 20000 else QuestionPriority.MEDIA,
            pregunta=f"¿Qué es este SINPE de ₡{monto:,.0f} a {numero_telefono}?",
            contexto=f'{{"telefono": "{numero_telefono}", "fecha": "{fecha.isoformat()}"}}',
            opciones='["Comida", "Transporte", "Servicios", "Personal", "Otro..."]',
            monto_relacionado=monto,
            origen="onboarding",
        )

    @classmethod
    def crear_pregunta_comercio_desconocido(
        cls,
        profile_id: str,
        transaction_id: str,
        comercio: str,
        monto: Decimal,
    ) -> "PendingQuestion":
        """Crea una pregunta para un comercio desconocido."""
        return cls(
            profile_id=profile_id,
            transaction_id=transaction_id,
            tipo=QuestionType.COMERCIO_DESCONOCIDO,
            prioridad=QuestionPriority.MEDIA,
            pregunta=f"¿Qué tipo de comercio es '{comercio}'?",
            contexto=f'{{"comercio": "{comercio}"}}',
            opciones='["Supermercado", "Restaurante", "Gasolinera", "Tienda", "Servicio", "Otro..."]',
            monto_relacionado=monto,
            origen="onboarding",
        )

    @classmethod
    def crear_pregunta_solo_estado_cuenta(
        cls,
        profile_id: str,
        comercio: str,
        monto: Decimal,
        fecha: datetime,
    ) -> "PendingQuestion":
        """Crea pregunta para txn en estado de cuenta pero no en correos."""
        return cls(
            profile_id=profile_id,
            tipo=QuestionType.SOLO_EN_ESTADO_CUENTA,
            prioridad=QuestionPriority.ALTA,
            pregunta=f"'{comercio}' por ₡{monto:,.0f} aparece en tu estado de cuenta pero no encontramos el correo. ¿Es correcta?",
            contexto=f'{{"comercio": "{comercio}", "fecha": "{fecha.isoformat()}"}}',
            opciones='["Sí, es correcta", "No la reconozco", "Necesito revisar"]',
            monto_relacionado=monto,
            origen="reconciliacion",
        )
