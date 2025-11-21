"""Modelos para gestión de comercios (merchants) y sus variantes."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


class Merchant(Base):
    """
    Comercio normalizado - versión 'limpia' y unificada del nombre.

    Ejemplos:
    - "Subway" (agrupa "SUBWAY MOMENTUM", "SUBWAY AMERICA FREE ZO", etc.)
    - "Walmart" (agrupa "WALMART SUPERCENTER", "WALMART ESCAZU", etc.)
    - "Dunkin Donuts"
    """

    __tablename__ = "merchants"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Información del comercio
    nombre_normalizado: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, comment="Nombre limpio y unificado"
    )
    categoria_principal: Mapped[str] = mapped_column(
        String(50), index=True, comment="Categoría principal (ej: Restaurante, Supermercado)"
    )
    subcategoria: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Subcategoría (ej: Comida Rápida, Farmacia)"
    )
    tipo_negocio: Mapped[str] = mapped_column(
        String(30),
        comment="Tipo: food_service, retail, gas_station, healthcare, entertainment, etc.",
    )

    # Metadata descriptiva
    que_vende: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Descripción de productos/servicios"
    )
    logo_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="URL del logo del comercio"
    )
    color_brand: Mapped[str | None] = mapped_column(
        String(7), nullable=True, comment="Color de marca en hex (ej: #FF5733)"
    )

    # Metadatos
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Soft delete"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    variantes: Mapped[list["MerchantVariant"]] = relationship(
        "MerchantVariant", back_populates="merchant", cascade="all, delete-orphan"
    )
    transacciones: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="merchant"
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return f"<Merchant(id={self.id[:8]}..., nombre={self.nombre_normalizado}, categoria={self.categoria_principal})>"

    @classmethod
    def buscar_por_nombre_raw(cls, session, nombre_raw: str) -> "Merchant | None":
        """
        Busca un merchant por el nombre raw (como aparece en el correo).

        Args:
            session: Sesión de SQLAlchemy
            nombre_raw: Nombre como aparece en el correo (ej: "SUBWAY MOMENTUM")

        Returns:
            Merchant si encuentra match, None si no
        """
        variante = (
            session.query(MerchantVariant)
            .filter(MerchantVariant.nombre_raw.ilike(f"%{nombre_raw}%"))
            .first()
        )

        return variante.merchant if variante else None

    def calcular_total_gastado(self, session, profile_id: str) -> Decimal:
        """Calcula el total gastado en este merchant por un perfil."""
        from finanzas_tracker.models.transaction import Transaction

        transacciones = (
            session.query(Transaction)
            .filter(
                Transaction.merchant_id == self.id,
                Transaction.profile_id == profile_id,
                Transaction.deleted_at.is_(None),
            )
            .all()
        )

        total = sum(t.monto_crc for t in transacciones)
        return total.quantize(Decimal("0.01"))

    def calcular_numero_visitas(self, session, profile_id: str) -> int:
        """Calcula el número de transacciones en este merchant."""
        from finanzas_tracker.models.transaction import Transaction

        return (
            session.query(Transaction)
            .filter(
                Transaction.merchant_id == self.id,
                Transaction.profile_id == profile_id,
                Transaction.deleted_at.is_(None),
            )
            .count()
        )


class MerchantVariant(Base):
    """
    Variante del nombre de un comercio como aparece en correos bancarios.

    Ejemplos:
    - "SUBWAY MOMENTUM" (San José, Costa Rica)
    - "SUBWAY AMERICA FREE ZO" (Heredia, Costa Rica)
    - "WALMART SUPERCENTER" (Escazú, Costa Rica)
    """

    __tablename__ = "merchant_variants"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("merchants.id"), nullable=False, index=True
    )

    # Nombre como aparece en el correo
    nombre_raw: Mapped[str] = mapped_column(
        String(200), unique=True, index=True, comment="Nombre exacto del correo bancario"
    )

    # Ubicación
    ciudad: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Ciudad donde está el local"
    )
    pais: Mapped[str] = mapped_column(
        String(50), default="Costa Rica", comment="País"
    )
    ubicacion_descriptiva: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Descripción de ubicación (ej: Momentum Pinares, Mall San Pedro)",
    )

    # Metadata de matching
    confianza_match: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=1.0,
        comment="Confianza del match (0.0 - 1.0). 1.0 = manual/confirmado",
    )

    # Metadatos
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Soft delete"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="variantes")

    # Índices
    __table_args__ = (
        Index("ix_merchant_variants_merchant_ciudad", "merchant_id", "ciudad"),
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<MerchantVariant(id={self.id[:8]}..., nombre_raw={self.nombre_raw}, "
            f"ciudad={self.ciudad})>"
        )
