"""Modelo de Usuario para autenticación JWT."""

__all__ = ["User"]

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from finanzas_tracker.core.database import Base


class User(Base):
    """
    Modelo de Usuario para autenticación.

    Separado de Profile porque:
    - Un User puede tener múltiples Profiles
    - User maneja auth (email/password)
    - Profile maneja contexto financiero

    Ejemplo:
        Un usuario tiene:
        - Profile "Personal" (su cuenta)
        - Profile "Negocio" (su empresa)
        - Profile "Mamá" (ayuda a su mamá)
    """

    __tablename__ = "users"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Multi-tenancy (futuro)
    tenant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
    )

    # Credenciales
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Email para login (único)",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hash bcrypt del password",
    )

    # Información del usuario
    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Nombre del usuario",
    )

    # Estado
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment="Si el usuario está activo",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Si el email está verificado",
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
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Último login exitoso",
    )

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fecha de eliminación (soft delete)",
    )

    # Relaciones (opcional por ahora - Profile aún no tiene user_id)
    # profiles: Mapped[list["Profile"]] = relationship(
    #     "Profile",
    #     back_populates="user",
    #     lazy="selectin",
    # )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
