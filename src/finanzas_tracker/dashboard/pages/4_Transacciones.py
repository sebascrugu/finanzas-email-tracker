"""Pagina de Revision y Categorizacion de Transacciones."""

import streamlit as st

st.set_page_config(
    page_title="Transacciones - Finanzas Tracker",
    page_icon="",
    layout="wide",
)

from pathlib import Path
import sys

src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.dashboard.components.transactions import (
    mostrar_estado_vacio,
    revisar_transacciones,
)
from finanzas_tracker.dashboard.helpers import require_profile
from finanzas_tracker.models.transaction import Transaction


def main() -> None:
    """Pagina principal de revision de transacciones."""
    st.title("Revision de Transacciones")

    perfil_activo = require_profile()
    st.caption(f"Perfil: **{perfil_activo.nombre_completo}**")

    # Obtener transacciones pendientes
    with get_session() as session:
        transacciones = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == perfil_activo.id,
                Transaction.necesita_revision.is_(True),
                Transaction.deleted_at.is_(None),
            )
            .order_by(Transaction.fecha_transaccion.desc())
            .all()
        )

        if not transacciones:
            mostrar_estado_vacio(perfil_activo)
        else:
            revisar_transacciones(perfil_activo, transacciones)


if __name__ == "__main__":
    main()
