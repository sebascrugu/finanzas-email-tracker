"""Schemas para autenticación."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    """Schema para registro de usuario."""

    email: EmailStr = Field(
        ...,
        description="Email del usuario (será el login)",
        examples=["usuario@ejemplo.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Password (mínimo 8 caracteres)",
        examples=["MiPassword123!"],
    )
    nombre: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Nombre del usuario",
        examples=["Sebastián Cruz"],
    )


class UserLogin(BaseModel):
    """Schema para login."""

    email: EmailStr = Field(
        ...,
        description="Email del usuario",
        examples=["usuario@ejemplo.com"],
    )
    password: str = Field(
        ...,
        description="Password del usuario",
        examples=["MiPassword123!"],
    )


class Token(BaseModel):
    """Schema de respuesta con token JWT."""

    access_token: str = Field(
        ...,
        description="Token JWT para autenticación",
    )
    token_type: str = Field(
        default="bearer",
        description="Tipo de token (siempre 'bearer')",
    )
    expires_in: int = Field(
        ...,
        description="Tiempo de expiración en segundos",
    )


class TokenData(BaseModel):
    """Datos extraídos del token."""

    user_id: str | None = None
    email: str | None = None


class UserResponse(BaseModel):
    """Schema de respuesta de usuario."""

    id: str
    email: str
    nombre: str
    is_active: bool
    is_verified: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    """Schema de respuesta de login exitoso."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class MessageResponse(BaseModel):
    """Schema para mensajes simples."""

    message: str
    code: str | None = None
