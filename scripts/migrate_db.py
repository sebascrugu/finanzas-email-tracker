"""
Script de migración de base de datos.

Este script resetea completamente la base de datos y la recrea con el nuevo schema.
ADVERTENCIA: Esto borrará TODOS los datos existentes.

Uso:
    poetry run python scripts/migrate_db.py

Para desarrollo/testing es seguro usarlo ya que los datos son de prueba (Nov-Dic 2025).
"""

import sys
from pathlib import Path

# Agregar el directorio src al path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import Base, engine, init_db
from finanzas_tracker.core.logging import get_logger

logger = get_logger(__name__)


def reset_database() -> None:
    """
    Elimina todas las tablas y las vuelve a crear.

    ADVERTENCIA: Esto borrará TODOS los datos.
    """
    logger.warning("=" * 80)
    logger.warning("⚠️  ADVERTENCIA: ESTO BORRARÁ TODOS LOS DATOS DE LA BASE DE DATOS")
    logger.warning("=" * 80)
    logger.info("")
    logger.info("Esta operación:")
    logger.info("  • Eliminará todas las tablas existentes")
    logger.info("  • Creará las nuevas tablas con el schema actualizado")
    logger.info("  • BORRARÁ todos los usuarios, transacciones, categorías, etc.")
    logger.info("")
    logger.info("Esto es SEGURO para desarrollo (Nov-Dic 2025 son datos de prueba)")
    logger.info("")

    respuesta = input("¿Estás seguro de continuar? (escribe 'SI' para confirmar): ")

    if respuesta.strip().upper() != "SI":
        logger.info("❌ Migración cancelada")
        return

    logger.info("")
    logger.info("🔄 Iniciando migración...")

    try:
        # 1. Eliminar todas las tablas
        logger.info("📦 Eliminando tablas antiguas...")
        Base.metadata.drop_all(bind=engine)
        logger.success("✅ Tablas eliminadas")

        # 2. Crear nuevas tablas
        logger.info("🏗️  Creando nuevas tablas con schema mejorado...")
        init_db()
        logger.success("✅ Tablas creadas")

        logger.info("")
        logger.success("=" * 80)
        logger.success("✨ MIGRACIÓN COMPLETADA EXITOSAMENTE")
        logger.success("=" * 80)
        logger.info("")
        logger.info("📋 Próximos pasos:")
        logger.info("  1. make setup-user   → Configurar tu usuario")
        logger.info("  2. make seed          → Poblar categorías")
        logger.info("  3. make process       → Procesar correos")
        logger.info("  4. make review        → Revisar transacciones")
        logger.info("")
        logger.info("🎯 Las nuevas funcionalidades incluyen:")
        logger.info("  • ✅ Enums type-safe (CardType, BankName, Currency, etc.)")
        logger.info("  • ✅ Soft deletes en todas las tablas")
        logger.info("  • ✅ Check constraints a nivel DB")
        logger.info("  • ✅ Índices compuestos para mejor performance")
        logger.info("  • ✅ Modelo de Ingresos (Income)")
        logger.info("  • ✅ Campos especiales en Transaction (intermediaria, excluir_presupuesto)")
        logger.info("  • ✅ Límite de crédito en Card")
        logger.info("  • ✅ Métodos helper en modelos")
        logger.info("")

    except Exception as e:
        logger.error(f"❌ Error durante la migración: {e}")
        logger.error("La base de datos podría estar en un estado inconsistente")
        logger.error("Intenta ejecutar el script nuevamente")
        raise


def main() -> None:
    """Función principal."""
    reset_database()


if __name__ == "__main__":
    main()

