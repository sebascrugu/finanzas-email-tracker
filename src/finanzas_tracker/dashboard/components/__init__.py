"""Dashboard UI components."""

from finanzas_tracker.dashboard.components.accounts import (
    crear_cuenta_form,
    editar_cuenta,
    gestionar_cuentas,
)
from finanzas_tracker.dashboard.components.incomes import (
    calcular_proximo_ingreso,
    es_tipo_recurrente,
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
