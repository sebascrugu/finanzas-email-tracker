"""Base Repository Pattern.

Proporciona operaciones CRUD genéricas siguiendo el Repository Pattern.
Cada entidad tiene su propio repository que hereda de BaseRepository.
"""

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.core.database import Base


# Tipo genérico para modelos SQLAlchemy
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Repositorio base con operaciones CRUD genéricas.

    Implementa el patrón Repository para separar la lógica de acceso
    a datos de la lógica de negocio en los services.

    Attributes:
        model: Clase del modelo SQLAlchemy
        db: Sesión de base de datos

    Example:
        ```python
        class ProfileRepository(BaseRepository[Profile]):
            def __init__(self, db: Session) -> None:
                super().__init__(Profile, db)

            def get_by_email(self, email: str) -> Profile | None:
                stmt = select(self.model).where(self.model.email_outlook == email)
                return self.db.execute(stmt).scalar_one_or_none()
        ```
    """

    def __init__(self, model: type[ModelType], db: Session) -> None:
        """
        Inicializa el repositorio.

        Args:
            model: Clase del modelo SQLAlchemy
            db: Sesión de base de datos activa
        """
        self.model = model
        self.db = db

    def _has_soft_delete(self) -> bool:
        """Verifica si el modelo soporta soft delete."""
        return hasattr(self.model, "deleted_at")

    def get(self, entity_id: str | UUID) -> ModelType | None:
        """
        Obtiene una entidad por ID (excluyendo soft-deleted si aplica).

        Args:
            entity_id: ID de la entidad (string o UUID)

        Returns:
            Entidad encontrada o None
        """
        id_str = str(entity_id) if isinstance(entity_id, UUID) else entity_id
        stmt = select(self.model).where(self.model.id == id_str)

        if self._has_soft_delete():
            stmt = stmt.where(self.model.deleted_at.is_(None))

        return self.db.execute(stmt).scalar_one_or_none()

    def get_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
    ) -> list[ModelType]:
        """
        Lista todas las entidades con paginación.

        Args:
            skip: Registros a saltar
            limit: Máximo de registros
            include_deleted: Incluir soft-deleted

        Returns:
            Lista de entidades
        """
        stmt = select(self.model)

        if not include_deleted and self._has_soft_delete():
            stmt = stmt.where(self.model.deleted_at.is_(None))

        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, data: dict[str, Any]) -> ModelType:
        """
        Crea una nueva entidad.

        Args:
            data: Diccionario con los campos del modelo

        Returns:
            Entidad creada
        """
        entity: ModelType = self.model(**data)
        self.db.add(entity)
        self.db.flush()  # Para obtener el ID generado
        return entity

    def update(self, entity: ModelType, data: dict[str, Any]) -> ModelType:
        """
        Actualiza una entidad existente.

        Args:
            entity: Entidad a actualizar
            data: Campos a modificar

        Returns:
            Entidad actualizada
        """
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.db.flush()
        return entity

    def delete(self, entity: ModelType, *, hard: bool = False) -> None:
        """
        Elimina una entidad (soft delete por defecto si el modelo lo soporta).

        Args:
            entity: Entidad a eliminar
            hard: Si True, elimina permanentemente (NO RECOMENDADO)
        """
        if hard or not self._has_soft_delete():
            self.db.delete(entity)
        else:
            from datetime import UTC, datetime

            entity.deleted_at = datetime.now(UTC)
        self.db.flush()

    def exists(self, entity_id: str | UUID) -> bool:
        """
        Verifica si existe una entidad con el ID dado.

        Args:
            entity_id: ID a verificar

        Returns:
            True si existe y no está eliminada
        """
        return self.get(entity_id) is not None
