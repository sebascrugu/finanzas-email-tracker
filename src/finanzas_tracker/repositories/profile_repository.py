"""Repository para Perfiles."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.models.profile import Profile
from finanzas_tracker.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[Profile]):
    """
    Repositorio para operaciones de Perfiles.

    Extiende BaseRepository con queries específicas para perfiles
    como búsqueda por email o nombre.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(Profile, db)

    def get_by_email(self, email: str) -> Profile | None:
        """
        Busca perfil por email de Outlook.

        Args:
            email: Dirección de correo electrónico

        Returns:
            Perfil encontrado o None
        """
        stmt = select(self.model).where(
            self.model.email_outlook == email,
            self.model.activo.is_(True),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name(self, nombre: str) -> Profile | None:
        """
        Busca perfil por nombre exacto.

        Args:
            nombre: Nombre del perfil

        Returns:
            Perfil encontrado o None
        """
        stmt = select(self.model).where(
            self.model.nombre == nombre,
            self.model.activo.is_(True),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active(self) -> list[Profile]:
        """
        Lista todos los perfiles habilitados (activo=True).

        Returns:
            Lista de perfiles habilitados
        """
        stmt = select(self.model).where(
            self.model.activo.is_(True),
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_currently_active(self) -> Profile | None:
        """
        Obtiene el perfil actualmente activo en el dashboard.

        Returns:
            Perfil con es_activo=True o None
        """
        stmt = select(self.model).where(
            self.model.es_activo.is_(True),
            self.model.activo.is_(True),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def set_as_active(self, profile: Profile) -> None:
        """
        Establece un perfil como activo (desactiva los demás).

        Args:
            profile: Perfil a establecer como activo
        """
        # Desactivar todos los demás
        all_profiles = self.get_all()
        for p in all_profiles:
            if p.es_activo and p.id != profile.id:
                p.es_activo = False

        # Activar este perfil
        profile.es_activo = True
        self.db.flush()
