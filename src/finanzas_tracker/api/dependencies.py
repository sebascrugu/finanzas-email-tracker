"""Dependencias compartidas para FastAPI."""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.profile import Profile


def get_db() -> Generator[Session, None, None]:
    """Dependency para obtener sesión de base de datos."""
    with get_session() as session:
        yield session


# Type alias para inyección de dependencias
DBSession = Annotated[Session, Depends(get_db)]


def get_active_profile(db: DBSession) -> Profile:
    """
    Obtiene el perfil activo actual.

    Returns:
        Profile activo

    Raises:
        HTTPException: Si no hay perfil activo configurado
    """
    stmt = select(Profile).where(
        Profile.es_activo == True,
        Profile.activo == True,
    )
    profile = db.execute(stmt).scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "No hay perfil activo configurado",
                "code": "PROFILE_NOT_FOUND",
                "hint": "Crea un perfil primero usando POST /api/v1/profiles",
            },
        )

    return profile


# Type alias para perfil activo
ActiveProfile = Annotated[Profile, Depends(get_active_profile)]
