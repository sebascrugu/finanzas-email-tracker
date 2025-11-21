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

__all__ = [
    "gestionar_cuentas",
    "editar_cuenta",
    "crear_cuenta_form",
    "mostrar_perfiles",
    "activar_perfil",
    "editar_perfil",
    "crear_perfil_nuevo",
]
