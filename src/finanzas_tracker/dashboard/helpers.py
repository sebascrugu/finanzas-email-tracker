"""Helpers compartidos para las páginas del dashboard."""

import streamlit as st
from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.user import User
from finanzas_tracker.models.profile import Profile


def get_active_profile() -> tuple[User | None, Profile | None]:
    """
    Obtiene el usuario y perfil activo.

    Returns:
        tuple[User | None, Profile | None]: Usuario y perfil activo, o (None, None) si no existen
    """
    with get_session() as session:
        user = session.query(User).filter(User.activo == True).first()  # noqa: E712
        if not user:
            return None, None

        # Obtener perfil activo
        perfil_activo = (
            session.query(Profile)
            .filter(
                Profile.owner_email == user.email,
                Profile.es_activo == True,  # noqa: E712
                Profile.activo == True,  # noqa: E712
            )
            .first()
        )

        return user, perfil_activo


def require_profile():
    """
    Verifica que exista un perfil activo.
    Si no existe, muestra un mensaje y detiene la ejecución.

    Returns:
        tuple[User, Profile]: Usuario y perfil activo (garantizados)
    """
    user, perfil_activo = get_active_profile()

    if not user:
        st.warning("⚠️ No hay usuario configurado")
        st.info("👉 Ve a la página **Setup** para configurar tu cuenta")
        st.stop()

    if not perfil_activo:
        st.warning("⚠️ No tienes perfiles configurados")
        st.info("👉 Ve a la página **Setup** para crear tu primer perfil")
        st.stop()

    return user, perfil_activo
