"""
Script para migrar el token cache del archivo al keyring del sistema.

Este script es de uso único para usuarios que ya tienen tokens almacenados
en el archivo data/.token_cache.bin del sistema antiguo.

Ejecuta este script una vez después de actualizar a la nueva versión
con almacenamiento seguro en keyring.
"""

from pathlib import Path

import keyring

from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)

# Configuración
OLD_TOKEN_CACHE_FILE = Path("data/.token_cache.bin")
KEYRING_SERVICE_NAME = "finanzas-email-tracker"
KEYRING_USERNAME = "msal-token-cache"


def migrate_token_cache() -> None:
    """Migra el token cache del archivo al keyring."""
    logger.info("Iniciando migración de token cache al keyring del sistema...")

    # Verificar si existe el archivo antiguo
    if not OLD_TOKEN_CACHE_FILE.exists():
        logger.warning(
            "No se encontró el archivo de token cache antiguo. "
            "Es posible que ya hayas migrado o nunca te hayas autenticado."
        )
        return

    try:
        # Leer el cache del archivo
        cache_data = OLD_TOKEN_CACHE_FILE.read_text()

        if not cache_data.strip():
            logger.warning("El archivo de token cache está vacío")
            return

        # Guardar en keyring
        keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME, cache_data)
        logger.success(" Token cache migrado exitosamente al keyring del sistema")

        # Crear backup del archivo antiguo antes de eliminarlo
        backup_file = OLD_TOKEN_CACHE_FILE.with_suffix(".bin.backup")
        OLD_TOKEN_CACHE_FILE.rename(backup_file)
        logger.info(f"Archivo antiguo respaldado como: {backup_file}")
        logger.info("Puedes eliminar el backup manualmente si todo funciona correctamente")

    except Exception as e:
        logger.error(f"Error durante la migración: {e}")
        logger.error("Por favor, reporta este error si persiste")
        raise


def verify_migration() -> None:
    """Verifica que la migración fue exitosa."""
    logger.info("Verificando migración...")

    # Intentar leer del keyring
    cached_data = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_USERNAME)

    if cached_data:
        logger.success(" Verificación exitosa: Token cache encontrado en keyring")
        logger.info(f"Tamaño del cache: {len(cached_data)} caracteres")
        return True

    logger.error(" Verificación fallida: No se encontró token cache en keyring")
    return False


if __name__ == "__main__":
    logger.info("=== Migración de Token Cache al Keyring ===")
    migrate_token_cache()
    verify_migration()
    logger.info("=== Migración Completada ===")
