"""Router de autenticación."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from finanzas_tracker.api.dependencies import CurrentUser, get_db
from finanzas_tracker.api.schemas.auth import (
    Token,
    UserLogin,
    UserRegister,
    UserResponse,
)
from finanzas_tracker.services.auth_service import auth_service


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario",
    responses={
        201: {"description": "Usuario creado exitosamente"},
        400: {"description": "Email ya registrado"},
    },
)
def register(
    data: UserRegister,
    db: Session = Depends(get_db),
) -> UserResponse:
    """
    Registra un nuevo usuario en el sistema.

    - **email**: Email único para login
    - **password**: Mínimo 8 caracteres
    - **nombre**: Nombre del usuario
    """
    try:
        user = auth_service.create_user(
            db=db,
            email=data.email,
            password=data.password,
            nombre=data.nombre,
        )
        return UserResponse(
            id=user.id,
            email=user.email,
            nombre=user.nombre,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": str(e),
                "code": "EMAIL_EXISTS",
            },
        )


@router.post(
    "/login",
    response_model=Token,
    summary="Iniciar sesión",
    responses={
        200: {"description": "Login exitoso, retorna token JWT"},
        401: {"description": "Credenciales inválidas"},
    },
)
def login(
    data: UserLogin,
    db: Session = Depends(get_db),
) -> Token:
    """
    Autentica un usuario y retorna un token JWT.

    El token debe enviarse en el header `Authorization: Bearer <token>`
    para acceder a endpoints protegidos.
    """
    result = auth_service.login(db, data.email, data.password)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Email o password incorrectos",
                "code": "INVALID_CREDENTIALS",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(
        access_token=result["access_token"],
        token_type=result["token_type"],
        expires_in=result["expires_in"],
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtener usuario actual",
    responses={
        200: {"description": "Datos del usuario autenticado"},
        401: {"description": "No autenticado"},
    },
)
def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """
    Obtiene información del usuario autenticado.

    Requiere token JWT en header Authorization.
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        nombre=current_user.nombre,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at.isoformat(),
    )
