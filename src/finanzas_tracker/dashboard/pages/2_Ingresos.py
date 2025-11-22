"""Pagina de Gestion de Ingresos."""

import streamlit as st


st.set_page_config(
    page_title="Ingresos - Finanzas Tracker",
    page_icon="",
    layout="wide",
)

from pathlib import Path
import sys


src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.dashboard.components.incomes import (
    formulario_agregar_ingreso,
    listar_ingresos,
)
from finanzas_tracker.dashboard.helpers import require_profile


def main() -> None:
    """Pagina principal de gestion de ingresos."""
    st.title("Gestion de Ingresos")

    perfil_activo = require_profile()
    st.caption(f"Perfil: **{perfil_activo.nombre_completo}**")

    tab1, tab2 = st.tabs(["Agregar Ingreso", "Mis Ingresos"])

    with tab1:
        formulario_agregar_ingreso(perfil_activo)

    with tab2:
        listar_ingresos(perfil_activo)


if __name__ == "__main__":
    main()
