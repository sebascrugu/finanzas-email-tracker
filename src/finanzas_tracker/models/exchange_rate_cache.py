"""Modelo de caché para tipos de cambio USD a CRC."""

from datetime import UTC, datetime
from datetime import date as date_type

from sqlalchemy import CheckConstraint, Date, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from finanzas_tracker.core.database import Base


class ExchangeRateCache(Base):
    """
    Modelo para cachear tipos de cambio USD a CRC.

    Almacena tipos de cambio históricos en la base de datos para evitar
    llamadas repetidas a APIs externas. Los tipos de cambio por fecha
    no cambian, por lo que pueden cachearse indefinidamente.

    Attributes:
        date: Fecha del tipo de cambio (clave primaria)
        rate: Tipo de cambio USD a CRC (cuántos colones por dólar)
        source: Fuente del tipo de cambio (hacienda_cr, exchangerate_api, default)
        created_at: Timestamp de cuando se guardó el rate
        updated_at: Timestamp de última actualización
    """

    __tablename__ = "exchange_rate_cache"

    # Fecha del tipo de cambio (clave primaria)
    date: Mapped[date_type] = mapped_column(
        Date,
        primary_key=True,
        comment="Fecha del tipo de cambio (YYYY-MM-DD)",
    )

    # Tipo de cambio
    rate: Mapped[float] = mapped_column(
        Numeric(10, 4),
        nullable=False,
        comment="Tipo de cambio USD a CRC (ej: 530.50)",
    )

    # Fuente del tipo de cambio
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Fuente: hacienda_cr, exchangerate_api, default",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        comment="Fecha de creación del registro",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Fecha de última actualización",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("rate > 0", name="check_rate_positive"),
        CheckConstraint(
            "source IN ('hacienda_cr', 'exchangerate_api', 'default')",
            name="check_valid_source",
        ),
    )

    def __repr__(self) -> str:
        """Representación legible del cache entry."""
        return f"<ExchangeRateCache(date={self.date}, rate={self.rate}, source={self.source})>"

    @classmethod
    def get_by_date(cls, session: Session, target_date: date_type) -> "ExchangeRateCache | None":
        """
        Obtiene el tipo de cambio cacheado para una fecha específica.

        Args:
            session: Sesión de SQLAlchemy
            target_date: Fecha del tipo de cambio

        Returns:
            ExchangeRateCache | None: Entry del cache o None si no existe
        """
        result: ExchangeRateCache | None = session.query(cls).filter(cls.date == target_date).first()
        return result

    @classmethod
    def save_rate(
        cls,
        session: Session,
        target_date: date_type,
        rate: float,
        source: str,
    ) -> "ExchangeRateCache":
        """
        Guarda un tipo de cambio en el cache.

        Args:
            session: Sesión de SQLAlchemy
            target_date: Fecha del tipo de cambio
            rate: Tipo de cambio USD a CRC
            source: Fuente del tipo de cambio

        Returns:
            ExchangeRateCache: Entry guardado en el cache
        """
        # Verificar si ya existe
        existing = cls.get_by_date(session, target_date)
        if existing:
            # Actualizar si cambió la fuente o el rate
            existing.rate = rate
            existing.source = source
            existing.updated_at = datetime.now(UTC)
            return existing

        # Crear nuevo entry
        cache_entry = cls(
            date=target_date,
            rate=rate,
            source=source,
        )
        session.add(cache_entry)
        return cache_entry
