"""Dashboard components for Streamlit UI."""

from finanzas_tracker.dashboard.components.incomes import (
    formulario_agregar_ingreso,
    listar_ingresos,
)
from finanzas_tracker.dashboard.components.profiles import (
    activar_perfil,
    crear_perfil_nuevo,
    editar_perfil,
    mostrar_perfiles,
)
from finanzas_tracker.dashboard.components.transactions import (
    mostrar_estado_vacio,
    procesar_correos_bancarios,
    revisar_transacciones,
)


__all__ = [
    # Incomes
    "formulario_agregar_ingreso",
    "listar_ingresos",
    # Profiles
    "activar_perfil",
    "crear_perfil_nuevo",
    "editar_perfil",
    "mostrar_perfiles",
    # Transactions
    "mostrar_estado_vacio",
    "procesar_correos_bancarios",
    "revisar_transacciones",
]
