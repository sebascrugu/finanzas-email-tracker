"""Dashboard UI components."""

from finanzas_tracker.dashboard.components.accounts import (
    gestionar_cuentas,
    editar_cuenta,
    crear_cuenta_form,
)
from finanzas_tracker.dashboard.components.profiles import (
    mostrar_perfiles,
    activar_perfil,
    editar_perfil,
    crear_perfil_nuevo,
)
from finanzas_tracker.dashboard.components.incomes import (
    formulario_agregar_ingreso,
    listar_ingresos,
    es_tipo_recurrente,
    calcular_proximo_ingreso,
)
from finanzas_tracker.dashboard.components.transactions import (
    procesar_correos_bancarios,
    revisar_transacciones,
    mostrar_estado_vacio,
)

__all__ = [
    "gestionar_cuentas",
    "editar_cuenta",
    "crear_cuenta_form",
    "mostrar_perfiles",
    "activar_perfil",
    "editar_perfil",
    "crear_perfil_nuevo",
    "formulario_agregar_ingreso",
    "listar_ingresos",
    "es_tipo_recurrente",
    "calcular_proximo_ingreso",
    "procesar_correos_bancarios",
    "revisar_transacciones",
    "mostrar_estado_vacio",
]
