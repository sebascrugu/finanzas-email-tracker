"""Modelos para gestión de comercios (merchants) y sus variantes."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from finanzas_tracker.core.database import Base


if TYPE_CHECKING:
    from finanzas_tracker.models.transaction import Transaction


# Comercios conocidos que pueden tener múltiples categorías
# El usuario debe confirmar qué compró
COMERCIOS_AMBIGUOS: dict[str, list[str]] = {
    # Tiendas departamentales / Big Box
    "walmart": ["Supermercado", "Electrónica", "Ropa y Calzado", "Hogar", "Farmacia"],
    "pricesmart": ["Supermercado", "Electrónica", "Hogar", "Oficina"],
    "costco": ["Supermercado", "Electrónica", "Hogar", "Farmacia"],
    "amazon": ["Electrónica", "Libros", "Ropa y Calzado", "Hogar", "Suscripciones"],
    # Ferreterías / Mejoras del hogar
    "epa": ["Ferretería", "Hogar", "Jardín", "Electrónica"],
    "construplaza": ["Ferretería", "Hogar", "Jardín"],
    "home depot": ["Ferretería", "Hogar", "Jardín", "Electrónica"],
    # Tiendas por departamentos
    "el rey": ["Supermercado", "Hogar", "Ropa y Calzado"],
    "la curacao": ["Electrónica", "Hogar", "Electrodomésticos"],
    "gollo": ["Electrónica", "Hogar", "Electrodomésticos"],
    # Gasolineras (pueden tener tienda de conveniencia)
    "total": ["Gasolina", "Tienda de Conveniencia", "Comida"],
    "shell": ["Gasolina", "Tienda de Conveniencia", "Comida"],
    "uno": ["Gasolina", "Tienda de Conveniencia", "Comida"],
    # Farmacias que venden más
    "farmacia fischel": ["Farmacia", "Belleza", "Hogar"],
    "farmacia la bomba": ["Farmacia", "Belleza", "Supermercado"],
    # Tiendas de conveniencia
    "am pm": ["Tienda de Conveniencia", "Comida", "Bebidas"],
    "fresh market": ["Tienda de Conveniencia", "Comida", "Bebidas"],
}


def es_comercio_ambiguo(nombre_comercio: str) -> bool:
    """Verifica si un comercio necesita confirmación de categoría."""
    nombre_lower = nombre_comercio.lower().strip()
    return any(ambiguo in nombre_lower or nombre_lower in ambiguo for ambiguo in COMERCIOS_AMBIGUOS)


def obtener_categorias_posibles(nombre_comercio: str) -> list[str]:
    """Obtiene las posibles categorías para un comercio ambiguo."""
    nombre_lower = nombre_comercio.lower().strip()
    for ambiguo, categorias in COMERCIOS_AMBIGUOS.items():
        if ambiguo in nombre_lower or nombre_lower in ambiguo:
            return categorias
    return []


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
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Multi-tenancy (futuro)
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
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

    # Comercios ambiguos (Walmart, Amazon, etc.)
    es_ambiguo: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        comment="True si el comercio puede tener múltiples categorías (ej: Walmart)",
    )
    categorias_posibles: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Lista de categorías posibles para comercios ambiguos (JSON serializado)",
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
    def buscar_por_nombre_raw(cls, session: Session, nombre_raw: str) -> "Merchant | None":
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

    def calcular_total_gastado(self, session: Session, profile_id: str) -> Decimal:
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

        total = sum((t.monto_crc for t in transacciones), Decimal("0"))
        return total.quantize(Decimal("0.01"))

    def calcular_numero_visitas(self, session: Session, profile_id: str) -> int:
        """Calcula el número de transacciones en este merchant."""
        from finanzas_tracker.models.transaction import Transaction

        count: int = (
            session.query(Transaction)
            .filter(
                Transaction.merchant_id == self.id,
                Transaction.profile_id == profile_id,
                Transaction.deleted_at.is_(None),
            )
            .count()
        )
        return count


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
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Multi-tenancy (futuro)
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
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
    pais: Mapped[str] = mapped_column(String(50), default="Costa Rica", comment="País")
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
    __table_args__ = (Index("ix_merchant_variants_merchant_ciudad", "merchant_id", "ciudad"),)

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<MerchantVariant(id={self.id[:8]}..., nombre_raw={self.nombre_raw}, "
            f"ciudad={self.ciudad})>"
        )
