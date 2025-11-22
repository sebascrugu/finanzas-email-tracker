"""Modelos de categorías y subcategorías."""

__all__ = ["Category", "Subcategory"]

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import CategoryType


class Category(Base):
    """
    Modelo para categorías principales de gastos.

    Tres categorías principales:
    - Necesidades: Gastos esenciales
    - Gustos: Gastos discrecionales
    - Ahorros: Ahorro e inversiones
    """

    __tablename__ = "categories"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único de la categoría",
    )

    # Información
    tipo: Mapped[CategoryType] = mapped_column(
        String(20),
        unique=True,
        index=True,
        comment="Tipo: necesidades, gustos, ahorros",
    )
    nombre: Mapped[str] = mapped_column(
        String(100),
        index=True,
        comment="Nombre descriptivo de la categoría",
    )
    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Descripción detallada de la categoría",
    )
    icono: Mapped[str] = mapped_column(
        String(10),
        default="",
        comment="Emoji o icono para la categoría",
    )

    # Metadatos
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Fecha de creación",
    )

    # Relaciones
    subcategories: Mapped[list["Subcategory"]] = relationship(
        "Subcategory",
        back_populates="category",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return f"<Category(tipo={self.tipo}, nombre={self.nombre})>"


class Subcategory(Base):
    """
    Modelo para subcategorías granulares.

    Ejemplos:
    - Necesidades/Transporte: Gasolina, seguro, lavados
    - Necesidades/Trabajo: Almuerzos oficina
    - Gustos/Comida: Salidas con amigos
    - Gustos/Entretenimiento: Cine, Netflix
    """

    __tablename__ = "subcategories"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único de la subcategoría",
    )
    category_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("categories.id", ondelete="CASCADE"),
        index=True,
        comment="ID de la categoría padre",
    )

    # Información
    nombre: Mapped[str] = mapped_column(
        String(100),
        comment="Nombre de la subcategoría (ej: Transporte, Comida)",
    )
    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Descripción y ejemplos (ej: 'Gasolina, seguro, lavados')",
    )
    icono: Mapped[str] = mapped_column(
        String(10),
        default="🔹",
        comment="Emoji o icono para la subcategoría",
    )

    # Palabras clave para categorización automática
    keywords: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Palabras clave separadas por coma para auto-categorización",
    )

    # Metadatos
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Fecha de creación",
    )

    # Relaciones
    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="subcategories",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="subcategory",
    )

    # Índices
    __table_args__ = (Index("ix_subcategories_category_nombre", "category_id", "nombre"),)

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return f"<Subcategory(nombre={self.nombre}, category={self.category_id})>"

    @property
    def nombre_completo(self) -> str:
        """Retorna el nombre completo (Categoría/Subcategoría)."""
        if self.category:
            return f"{self.category.nombre}/{self.nombre}"
        return self.nombre
