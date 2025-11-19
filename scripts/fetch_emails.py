"""
Script para ejecutar la extracción de correos bancarios.

Este script puede ejecutarse manualmente o programarse con cron/launchd.
"""

from pathlib import Path
import sys


# Agregar el directorio src al path para importar módulos
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.services.auth_manager import auth_manager
from finanzas_tracker.services.email_fetcher import EmailFetcher


logger = get_logger(__name__)


def test_connection() -> bool:
    """
    Prueba la conexión con Microsoft Graph API.

    Returns:
        bool: True si la conexión es exitosa
    """
    logger.info("🔌 Probando conexión con Microsoft Graph...")

    if not auth_manager.test_connection():
        logger.error(" No se pudo conectar con Microsoft Graph API")
        return False

    return True


def fetch_emails(days_back: int = 30, bank: str | None = None) -> None:
    """
    Extrae correos de los bancos.

    Args:
        days_back: Días hacia atrás para buscar (default: 30)
        bank: Banco específico ('bac', 'popular') o None para ambos
    """
    logger.info(" Iniciando extracción de correos...")

    fetcher = EmailFetcher()

    # Obtener correos del usuario autenticado
    emails = fetcher.fetch_all_emails(days_back=days_back, bank=bank)

    # Obtener email del usuario actual
    user_email = auth_manager.get_current_user_email()

    # Mostrar resumen
    total = len(emails)

    logger.info("=" * 60)
    logger.info(" RESUMEN DE EXTRACCIÓN")
    logger.info("=" * 60)
    logger.success(f" Usuario autenticado: {user_email}")
    logger.success(f" Correos encontrados: {total}")
    logger.info("=" * 60)

    # Mostrar muestra de correos
    if total > 0:
        logger.info("\n Muestra de correos (primeros 5):")
        for i, email in enumerate(emails[:5], 1):
            subject = email.get("subject", "Sin asunto")
            from_email = email.get("from", {}).get("emailAddress", {}).get("address", "Unknown")
            date = email.get("receivedDateTime", "Unknown")
            logger.info(f"\n  {i}. {subject}")
            logger.info(f"     De: {from_email}")
            logger.info(f"     Fecha: {date}")
    else:
        logger.warning("\n  No se encontraron correos bancarios")
        logger.info("Posibles razones:")
        logger.info("  • No hay correos de BAC o Banco Popular en los últimos 30 días")
        logger.info("  • Los correos fueron eliminados")
        logger.info("  • Los remitentes son diferentes a los configurados")

    # Información sobre cambio de cuenta
    logger.info("\n" + "=" * 60)
    logger.info(" CAMBIAR DE CUENTA")
    logger.info("=" * 60)
    logger.info("Para ver correos de otra cuenta:")
    logger.info("  1. Ejecuta: poetry run python scripts/logout.py")
    logger.info("  2. Vuelve a ejecutar este script")
    logger.info("  3. Inicia sesión con la otra cuenta")

    # TODO: Siguiente fase - parsear correos y guardar en BD
    logger.info("\n⏳ Próximos pasos:")
    logger.info("  1. Parsear HTML de correos (Fase 3)")
    logger.info("  2. Guardar transacciones en base de datos (Fase 4)")
    logger.info("  3. Categorizar con Claude AI (Fase 5)")


def main() -> None:
    """Función principal para ejecutar el fetch de correos."""
    logger.info("=" * 60)
    logger.info("🚀 FINANZAS EMAIL TRACKER - EXTRACCIÓN DE CORREOS")
    logger.info("=" * 60)
    logger.info("")
    logger.info("🔐 AUTENTICACIÓN INTERACTIVA")
    logger.info("Se abrirá tu navegador para que inicies sesión")
    logger.info("con tu cuenta de Outlook/Hotmail")
    logger.info("")

    try:
        # 1. Probar conexión (esto abre el navegador si es necesario)
        if not test_connection():
            sys.exit(1)

        logger.success(" Conexión exitosa con Microsoft Graph API\n")

        # 2. Extraer correos
        fetch_emails(days_back=30)  # Últimos 30 días

        logger.success("\n Extracción completada exitosamente")

    except KeyboardInterrupt:
        logger.warning("\n  Extracción interrumpida por el usuario")
        sys.exit(0)

    except Exception as e:
        logger.error(f"\n Error durante la extracción de correos: {e}")
        logger.exception("Detalles del error:")
        sys.exit(1)

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
