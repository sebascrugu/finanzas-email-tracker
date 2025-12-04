"""Router de Perfiles - CRUD + switch activo."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from finanzas_tracker.api.dependencies import DBSession
from finanzas_tracker.api.schemas.profile import (
    ProfileCreate,
    ProfileListResponse,
    ProfileResponse,
    ProfileUpdate,
)
from finanzas_tracker.models.profile import Profile


router = APIRouter(prefix="/profiles")


@router.get("", response_model=ProfileListResponse)
def list_profiles(db: DBSession) -> ProfileListResponse:
    """
    Lista todos los perfiles disponibles.

    Perfiles permiten separar finanzas:
    - Personal: Tus finanzas personales
    - Negocio: Finanzas de empresa
    - Familia: Gestionar finanzas de familiares
    """
    stmt = select(Profile).where(Profile.activo == True).order_by(Profile.nombre)
    profiles = db.execute(stmt).scalars().all()

    return ProfileListResponse(
        items=[ProfileResponse.model_validate(p) for p in profiles],
        total=len(profiles),
    )


@router.get("/active", response_model=ProfileResponse)
def get_active_profile(db: DBSession) -> ProfileResponse:
    """Obtiene el perfil actualmente activo."""
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

    return ProfileResponse.model_validate(profile)


@router.get("/{profile_id}", response_model=ProfileResponse)
def get_profile(profile_id: str, db: DBSession) -> ProfileResponse:
    """Obtiene un perfil por ID."""
    stmt = select(Profile).where(
        Profile.id == profile_id,
        Profile.activo == True,
    )
    profile = db.execute(stmt).scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Perfil no encontrado", "code": "PROFILE_NOT_FOUND"},
        )

    return ProfileResponse.model_validate(profile)


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(data: ProfileCreate, db: DBSession) -> ProfileResponse:
    """
    Crea un nuevo perfil.

    Si es el primer perfil, se activa automáticamente.
    """
    # Verificar si ya existe un perfil con ese email
    stmt = select(Profile).where(Profile.email_outlook == data.email_outlook)
    existing = db.execute(stmt).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Ya existe un perfil con ese email",
                "code": "PROFILE_EXISTS",
                "profile_id": existing.id,
            },
        )

    # Verificar si hay otros perfiles
    count_stmt = select(Profile).where(Profile.activo == True)
    existing_profiles = db.execute(count_stmt).scalars().all()
    is_first = len(existing_profiles) == 0

    profile = Profile(
        email_outlook=data.email_outlook,
        nombre=data.nombre,
        descripcion=data.descripcion,
        icono=data.icono or "👤",
        es_activo=is_first,  # Activar si es el primero
        activo=True,
    )

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return ProfileResponse.model_validate(profile)


@router.patch("/{profile_id}", response_model=ProfileResponse)
def update_profile(
    profile_id: str,
    data: ProfileUpdate,
    db: DBSession,
) -> ProfileResponse:
    """Actualiza un perfil existente."""
    stmt = select(Profile).where(
        Profile.id == profile_id,
        Profile.activo == True,
    )
    profile = db.execute(stmt).scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Perfil no encontrado", "code": "PROFILE_NOT_FOUND"},
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    return ProfileResponse.model_validate(profile)


@router.post("/{profile_id}/activate", response_model=ProfileResponse)
def activate_profile(profile_id: str, db: DBSession) -> ProfileResponse:
    """
    Activa un perfil y desactiva los demás.

    Solo un perfil puede estar activo a la vez.
    """
    # Verificar que el perfil existe
    stmt = select(Profile).where(
        Profile.id == profile_id,
        Profile.activo == True,
    )
    profile = db.execute(stmt).scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Perfil no encontrado", "code": "PROFILE_NOT_FOUND"},
        )

    # Desactivar todos los perfiles
    all_profiles_stmt = select(Profile).where(Profile.activo == True)
    all_profiles = db.execute(all_profiles_stmt).scalars().all()
    for p in all_profiles:
        p.es_activo = False

    # Activar el perfil seleccionado
    profile.es_activo = True

    db.commit()
    db.refresh(profile)

    return ProfileResponse.model_validate(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: str, db: DBSession) -> None:
    """
    Elimina un perfil (soft delete).

    No se puede eliminar el perfil activo.
    """
    stmt = select(Profile).where(
        Profile.id == profile_id,
        Profile.activo == True,
    )
    profile = db.execute(stmt).scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Perfil no encontrado", "code": "PROFILE_NOT_FOUND"},
        )

    if profile.es_activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "No se puede eliminar el perfil activo",
                "code": "CANNOT_DELETE_ACTIVE",
                "hint": "Activa otro perfil primero",
            },
        )

    # Soft delete
    profile.activo = False
    db.commit()
