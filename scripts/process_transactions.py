"""Script para procesar transacciones desde correos bancarios."""

from pathlib import Path
import sys

# Agregar el directorio src al path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import init_db
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.services.email_fetcher import EmailFetcher
from finanzas_tracker.services.auth_manager import auth_manager
from finanzas_tracker.services.transaction_processor import transaction_processor

logger = get_logger(__name__)


def main() -> None:
    """Función principal."""
    logger.info("=" * 80)
    logger.info("💰 PROCESADOR DE TRANSACCIONES BANCARIAS")
    logger.info("=" * 80)
    logger.info("")

    # 1. Inicializar base de datos
    logger.info("📊 Paso 1: Inicializando base de datos...")
    try:
        init_db()
    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")
        return

    logger.info("")

    # 2. Obtener correos
    logger.info("📧 Paso 2: Extrayendo correos de Outlook...")
    try:
        # Obtener email del usuario autenticado
        user_email = auth_manager.get_current_user_email()
        if not user_email:
            logger.error("No se pudo obtener el email del usuario autenticado")
            return

        logger.info(f"Usuario: {user_email}")

        # Extraer correos
        fetcher = EmailFetcher()
        emails = fetcher.fetch_all_emails(days_back=None)  # Todos desde este año

        if not emails:
            logger.warning("⚠️  No se encontraron correos de transacciones")
            return

        logger.success(f"✅ {len(emails)} correos de transacciones encontrados")

    except Exception as e:
        logger.error(f"Error extrayendo correos: {e}")
        return

    logger.info("")

    # 3. Procesar transacciones
    logger.info("⚙️  Paso 3: Procesando transacciones...")
    try:
        stats = transaction_processor.process_emails(emails, user_email)

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 ESTADÍSTICAS DEL PROCESAMIENTO")
        logger.info("=" * 80)
        logger.info(f"  Total de correos procesados: {stats['total']}")
        logger.info(f"  Transacciones guardadas: {stats['procesados']}")
        logger.info(f"  Transacciones duplicadas: {stats['duplicados']}")
        logger.info(f"  Errores: {stats['errores']}")
        logger.info("")
        logger.info("📊 Por Banco:")
        logger.info(f"  BAC Credomatic: {stats['bac']}")
        logger.info(f"  Banco Popular: {stats['popular']}")
        logger.info("")
        logger.info(f"💱 Transacciones en USD convertidas: {stats['usd_convertidos']}")
        logger.info("")
        logger.info("🤖 Categorización con IA:")
        logger.info(f"  ✅ Categorizadas automáticamente: {stats['categorizadas_automaticamente']}")
        logger.info(f"  🤔 Necesitan revisión: {stats['necesitan_revision']}")
        logger.info("")

        if stats["procesados"] > 0:
            logger.success("=" * 80)
            logger.success("✅ PROCESAMIENTO EXITOSO")
            logger.success("=" * 80)
            logger.success("")
            logger.success(f"🎉 {stats['procesados']} nuevas transacciones guardadas en la base de datos")
            logger.success("")
            logger.info("💡 Próximos pasos:")
            if stats.get('necesitan_revision', 0) > 0:
                logger.info(f"   1. Revisa las {stats['necesitan_revision']} transacciones: make review")
                logger.info("   2. Ejecuta el dashboard con: make run-dashboard")
                logger.info("   3. Visualiza tus finanzas")
            else:
                logger.info("   1. Ejecuta el dashboard con: make run-dashboard")
                logger.info("   2. Visualiza tus finanzas")
        else:
            logger.info("ℹ️  No se guardaron nuevas transacciones (posiblemente todas son duplicadas)")

    except Exception as e:
        logger.error(f"Error procesando transacciones: {e}")
        raise


if __name__ == "__main__":
    main()

