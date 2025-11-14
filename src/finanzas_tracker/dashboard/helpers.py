"""Helpers compartidos para las páginas del dashboard."""

import streamlit as st
from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.profile import Profile


def get_active_profile() -> Profile | None:
    """
    Obtiene el perfil activo.

    Returns:
        Profile | None: Perfil activo, o None si no existe
    """
    with get_session() as session:
        # Obtener perfil activo
        perfil_activo = (
            session.query(Profile)
            .filter(
                Profile.es_activo == True,  # noqa: E712
                Profile.activo == True,  # noqa: E712
            )
            .first()
        )

        return perfil_activo


def require_profile() -> Profile:
    """
    Verifica que exista un perfil activo.
    Si no existe, muestra un mensaje y detiene la ejecución.

    Returns:
        Profile: Perfil activo (garantizado)
    """
    perfil_activo = get_active_profile()

    if not perfil_activo:
        st.warning("⚠️ No tienes perfiles configurados")
        st.info("👉 Ve a la página **⚙️ Setup** para crear tu primer perfil")
        st.stop()

    return perfil_activo
