"""
Script para cerrar sesión y limpiar el cache de tokens.

Útil cuando quieres cambiar de cuenta o resolver problemas de autenticación.
"""

import sys
from pathlib import Path

# Agregar el directorio src al path para importar módulos
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.services.auth_manager import auth_manager


logger = get_logger(__name__)


def main() -> None:
    """Función principal para cerrar sesión."""
    logger.info("=" * 60)
    logger.info("🔐 CERRAR SESIÓN")
    logger.info("=" * 60)

    # Obtener usuario actual si existe
    current_user = auth_manager.get_current_user_email()

    if current_user:
        logger.info(f"Usuario actual: {current_user}")
    else:
        logger.info("No hay sesión activa")

    # Cerrar sesión
    logger.info("\n🔄 Cerrando sesión...")
    auth_manager.logout()

    logger.success("✅ Sesión cerrada correctamente")
    logger.info("\nLa próxima vez que ejecutes el script de extracción,")
    logger.info("se te pedirá que inicies sesión nuevamente.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

