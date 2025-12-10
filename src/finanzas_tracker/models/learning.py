"""Modelos para el sistema de aprendizaje de categorización.

Estas tablas permiten:
1. Preferencias por usuario (SINPE 8123-4567 → "Mamá")
2. Contactos SINPE aprendidos
3. Sugerencias crowdsourced de categorías
"""

__all__ = [
    "UserMerchantPreference",
    "UserContact",
    "GlobalMerchantSuggestion",
]

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


if TYPE_CHECKING:
    from finanzas_tracker.models.category import Subcategory
    from finanzas_tracker.models.profile import Profile


class UserMerchantPreference(Base):
    """
    Preferencias de categorización personalizadas por usuario.
    
    Ejemplo:
    - Usuario A marca "SINPE 8123-4567" como "Mamá" → Personal/Familia
    - Usuario B marca "SINPE 8123-4567" como "Doña Rosa Galletas" → Comida
    
    Cada usuario tiene su propia "libreta de preferencias".
    """

    __tablename__ = "user_merchant_preferences"

    # Identificadores
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Multi-tenancy (futuro)
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Perfil del usuario
    profile_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Patrón del comercio
    merchant_pattern: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Patrón del comercio (ej: 'UBER%', 'SINPE MARIA%')",
    )

    # Categoría asignada
    subcategory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("subcategories.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Metadatos de uso
    times_used: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Veces que se ha usado esta preferencia",
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.95"),
        comment="Confianza de 0.00 a 1.00",
    )
    source: Mapped[str] = mapped_column(
        String(50),
        default="user_correction",
        comment="Origen: user_correction, auto_detected",
    )
    user_label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Etiqueta personalizada del usuario (ej: 'Mamá')",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    subcategory: Mapped["Subcategory"] = relationship("Subcategory")
    profile: Mapped["Profile"] = relationship("Profile")

    # Índices
    __table_args__ = (
        Index("ix_user_merchant_preferences_lookup", "profile_id", "merchant_pattern"),
    )

    def __repr__(self) -> str:
        return f"<UserMerchantPreference(pattern='{self.merchant_pattern}', label='{self.user_label}')>"


class UserContact(Base):
    """
    Contactos SINPE aprendidos del usuario.
    
    Cuando el usuario hace una transferencia SINPE a un número:
    - Se guarda el número y nombre oficial
    - El usuario puede ponerle un alias ("Mamá", "Casero", etc.)
    - Se asigna una categoría por defecto
    
    Esto permite categorización automática en futuras transferencias.
    """

    __tablename__ = "user_contacts"

    # Identificadores
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Multi-tenancy
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Perfil del usuario
    profile_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Información del contacto
    phone_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Número SINPE (ej: 8888-1234)",
    )
    sinpe_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Nombre como aparece en SINPE (ej: ROSA MARIA CRUZ)",
    )
    alias: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Nombre que el usuario le pone (ej: 'Mamá')",
    )

    # Categorización
    default_subcategory_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("subcategories.id", ondelete="SET NULL"),
        nullable=True,
    )
    relationship_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Tipo: family, friend, business, service",
    )

    # Estadísticas
    total_transactions: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    total_amount_crc: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("0"),
    )
    last_transaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    default_subcategory: Mapped["Subcategory"] = relationship("Subcategory")
    profile: Mapped["Profile"] = relationship("Profile")

    # Índices
    __table_args__ = (
        Index("ix_user_contacts_phone_lookup", "profile_id", "phone_number", unique=True),
        Index("ix_user_contacts_sinpe_name", "profile_id", "sinpe_name"),
    )

    def __repr__(self) -> str:
        return f"<UserContact(phone='{self.phone_number}', alias='{self.alias}')>"

    @property
    def display_name(self) -> str:
        """Nombre para mostrar (alias o nombre SINPE)."""
        return self.alias or self.sinpe_name or self.phone_number or "Desconocido"


class GlobalMerchantSuggestion(Base):
    """
    Sugerencias de categorización crowdsourced.
    
    Cuando múltiples usuarios categorizan el mismo comercio igual:
    - Se crea una sugerencia global
    - Si 5+ usuarios coinciden, se auto-aprueba
    - Esto mejora la categorización para TODOS los usuarios
    
    Ejemplo:
    - 10 usuarios categorizan "UBER" como "Transporte"
    - Se auto-aprueba como categoría global
    - Nuevos usuarios ven "UBER" auto-categorizado
    """

    __tablename__ = "global_merchant_suggestions"

    # Identificadores
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Comercio
    merchant_pattern: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Patrón del comercio (ej: 'UBER%')",
    )

    # Categoría sugerida
    suggested_subcategory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("subcategories.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Crowdsourcing
    user_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Número de usuarios que sugirieron esto",
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        nullable=True,
        comment="Score calculado de confianza",
    )

    # Estado de aprobación
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        comment="Estado: pending, approved, rejected",
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="Admin que aprobó",
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    suggested_subcategory: Mapped["Subcategory"] = relationship("Subcategory")

    # Índices
    __table_args__ = (
        Index(
            "ix_global_merchant_pattern_subcategory",
            "merchant_pattern",
            "suggested_subcategory_id",
            unique=True,
        ),
        Index("ix_global_merchant_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<GlobalMerchantSuggestion(pattern='{self.merchant_pattern}', users={self.user_count}, status='{self.status}')>"

    @property
    def is_approved(self) -> bool:
        """Verifica si está aprobada."""
        return self.status == "approved"

    @property
    def should_auto_approve(self) -> bool:
        """Verifica si debería auto-aprobarse (5+ usuarios con alta confianza)."""
        return (
            self.user_count >= 5
            and self.confidence_score is not None
            and self.confidence_score >= Decimal("0.90")
        )
