"""Schemas para Perfiles."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProfileBase(BaseModel):
    """Campos base de perfil."""

    email_outlook: EmailStr = Field(
        ..., description="Email de Outlook para buscar correos bancarios"
    )
    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre del perfil")


class ProfileCreate(ProfileBase):
    """Schema para crear perfil."""

    descripcion: str | None = Field(None, max_length=500, description="Descripción opcional")
    icono: str | None = Field("👤", max_length=10, description="Emoji del perfil")


class ProfileUpdate(BaseModel):
    """Schema para actualizar perfil (todos opcionales)."""

    nombre: str | None = Field(None, min_length=1, max_length=100)
    descripcion: str | None = Field(None, max_length=500)
    icono: str | None = Field(None, max_length=10)


class ProfileResponse(BaseModel):
    """Schema de respuesta de perfil."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email_outlook: str
    nombre: str
    descripcion: str | None
    icono: str | None
    es_activo: bool = Field(..., description="Si es el perfil actualmente activo")
    created_at: datetime
    updated_at: datetime


class ProfileListResponse(BaseModel):
    """Schema de respuesta de lista de perfiles."""

    items: list[ProfileResponse]
    total: int
