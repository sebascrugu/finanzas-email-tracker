"""Pagina de Setup y Gestion de Perfiles."""

import streamlit as st


st.set_page_config(
    page_title="Setup - Finanzas Tracker",
    page_icon=":gear:",
    layout="wide",
)

from pathlib import Path
import sys


src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.dashboard.components import (
    crear_perfil_nuevo,
    gestionar_cuentas,
    mostrar_perfiles,
)
from finanzas_tracker.models.profile import Profile


logger = get_logger(__name__)


def setup_page() -> None:
    """Pagina principal de setup y gestion de perfiles."""
    st.title("Setup y Gestion de Perfiles")

    with get_session() as session:
        perfiles = session.query(Profile).filter(Profile.activo.is_(True)).all()

        if not perfiles:
            st.info("Bienvenido! Vamos a crear tu primer perfil.")
            crear_perfil_nuevo(session, es_primero=True)
        else:
            _gestionar_perfiles(session, perfiles)


def _gestionar_perfiles(session, perfiles: list[Profile]) -> None:
    """Gestion de perfiles existentes."""
    st.success(f"Tienes **{len(perfiles)}** perfil(es) configurado(s)")

    tab1, tab2, tab3 = st.tabs(["Mis Perfiles", "Mis Cuentas", "Crear Perfil"])

    with tab1:
        mostrar_perfiles(session, perfiles)

    with tab2:
        perfil_activo = next((p for p in perfiles if p.es_activo), None)
        if perfil_activo:
            gestionar_cuentas(session, perfil_activo)
        else:
            st.warning("No hay un perfil activo. Por favor activa un perfil primero.")

    with tab3:
        crear_perfil_nuevo(session, es_primero=False)


if __name__ == "__main__":
    setup_page()
