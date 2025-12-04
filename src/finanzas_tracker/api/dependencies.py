"""Dependencias compartidas para FastAPI."""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.user import User
from finanzas_tracker.services.auth_service import auth_service


# =============================================================================
# DATABASE
# =============================================================================


def get_db() -> Generator[Session, None, None]:
    """Dependency para obtener sesión de base de datos."""
    with get_session() as session:
        yield session


# Type alias para inyección de dependencias
DBSession = Annotated[Session, Depends(get_db)]


# =============================================================================
# AUTHENTICATION
# =============================================================================

# Esquema de autenticación Bearer
security = HTTPBearer(auto_error=False)


def get_current_user(
    db: DBSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    """
    Obtiene el usuario actual desde el token JWT.

    Args:
        db: Sesión de base de datos
        credentials: Credenciales del header Authorization

    Returns:
        Usuario autenticado

    Raises:
        HTTPException 401: Si no hay token o es inválido
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "No se proporcionó token de autenticación",
                "code": "MISSING_TOKEN",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decodificar token
    payload = auth_service.decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Token inválido o expirado",
                "code": "INVALID_TOKEN",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Obtener usuario
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Token malformado",
                "code": "MALFORMED_TOKEN",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Usuario no encontrado",
                "code": "USER_NOT_FOUND",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Usuario desactivado",
                "code": "USER_INACTIVE",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_user_optional(
    db: DBSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User | None:
    """
    Versión opcional de get_current_user.

    Útil para endpoints que funcionan con o sin auth.

    Returns:
        Usuario si hay token válido, None si no
    """
    if not credentials:
        return None

    try:
        return get_current_user(db, credentials)
    except HTTPException:
        return None


# Type aliases para auth
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]


# =============================================================================
# PROFILES
# =============================================================================


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
