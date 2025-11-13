"""Script interactivo para revisar y categorizar transacciones."""

from pathlib import Path
import sys

# Agregar el directorio src al path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.transaction import Transaction

logger = get_logger(__name__)


def display_transaction(transaction: Transaction, index: int, total: int) -> None:
    """
    Muestra información de una transacción.

    Args:
        transaction: Transacción a mostrar
        index: Índice actual
        total: Total de transacciones
    """
    print("\n" + "=" * 80)
    print(f"📝 TRANSACCIÓN {index}/{total}")
    print("=" * 80)
    print(f"🏪 Comercio: {transaction.comercio}")
    print(f"💰 Monto: ₡{transaction.monto_crc:,.2f} CRC")
    print(f"📅 Fecha: {transaction.fecha_transaccion.strftime('%d/%m/%Y %H:%M')}")
    print(f"🏦 Banco: {transaction.banco.upper()}")
    print(f"📍 Ubicación: {transaction.ciudad or 'N/A'}, {transaction.pais or 'N/A'}")
    print()

    if transaction.categoria_sugerida_por_ia:
        print(f"🤖 Sugerencia de IA: {transaction.categoria_sugerida_por_ia}")
    else:
        print("🤖 Sugerencia de IA: Sin sugerencia")


def get_all_subcategories() -> list[Subcategory]:
    """
    Obtiene todas las subcategorías disponibles, agrupadas por categoría.

    Returns:
        Lista de subcategorías ordenadas
    """
    with get_session() as session:
        categories = session.query(Category).all()
        
        all_subcats = []
        for cat in sorted(categories, key=lambda c: c.tipo):
            subcats = sorted(cat.subcategories, key=lambda s: s.nombre)
            all_subcats.extend(subcats)
        
        return all_subcats


def display_categories_menu(subcategories: list[Subcategory]) -> None:
    """
    Muestra el menú de categorías disponibles.

    Args:
        subcategories: Lista de subcategorías
    """
    print("\n📊 CATEGORÍAS DISPONIBLES:")
    print()
    
    current_category = None
    for i, subcat in enumerate(subcategories, 1):
        # Si cambiamos de categoría principal, mostrar header
        if current_category != subcat.category.tipo:
            current_category = subcat.category.tipo
            icon = subcat.category.icono
            name = subcat.category.nombre.upper()
            print(f"\n{icon} {name}:")
        
        # Mostrar subcategoría
        print(f"  {i:2d}. {subcat.icono} {subcat.nombre}")
    
    print()
    print("  0. ❌ Sin categoría / Omitir")
    print()


def review_transaction(transaction: Transaction, subcategories: list[Subcategory]) -> bool:
    """
    Revisa una transacción interactivamente.

    Args:
        transaction: Transacción a revisar
        subcategories: Lista de subcategorías disponibles

    Returns:
        bool: True si se modificó, False si se omitió
    """
    while True:
        display_categories_menu(subcategories)
        
        choice = input("Elige una categoría (número) o 'a' para aceptar sugerencia: ").strip().lower()
        
        if choice == "a" and transaction.categoria_sugerida_por_ia:
            # Aceptar sugerencia
            # Buscar el subcategory_id si no está asignado
            if not transaction.subcategory_id:
                with get_session() as session:
                    # Extraer nombre de subcategoría de "Categoría/Subcategoría"
                    if "/" in transaction.categoria_sugerida_por_ia:
                        _, subcat_name = transaction.categoria_sugerida_por_ia.split("/", 1)
                    else:
                        subcat_name = transaction.categoria_sugerida_por_ia
                    
                    subcat = (
                        session.query(Subcategory)
                        .filter(Subcategory.nombre == subcat_name.strip())
                        .first()
                    )
                    
                    if subcat:
                        transaction.subcategory_id = subcat.id
            
            transaction.necesita_revision = False
            logger.success(f"✅ Aceptada sugerencia: {transaction.categoria_sugerida_por_ia}")
            return True
        
        elif choice == "0":
            # Omitir
            logger.info("⏭️  Transacción omitida")
            return False
        
        elif choice.isdigit():
            choice_num = int(choice)
            if 1 <= choice_num <= len(subcategories):
                # Asignar categoría seleccionada
                selected = subcategories[choice_num - 1]
                transaction.subcategory_id = selected.id
                transaction.categoria_sugerida_por_ia = selected.nombre_completo
                transaction.necesita_revision = False
                logger.success(f"✅ Categorizada como: {selected.nombre_completo}")
                return True
            else:
                print("❌ Opción inválida. Intenta de nuevo.")
        else:
            print("❌ Opción inválida. Intenta de nuevo.")


def main() -> None:
    """Función principal."""
    logger.info("=" * 80)
    logger.info("🔍 REVISIÓN DE TRANSACCIONES")
    logger.info("=" * 80)
    logger.info("")
    
    try:
        with get_session() as session:
            # Obtener transacciones que necesitan revisión
            transactions = (
                session.query(Transaction)
                .filter(Transaction.necesita_revision == True)  # noqa: E712
                .order_by(Transaction.fecha_transaccion.desc())
                .all()
            )
            
            if not transactions:
                logger.success("✅ ¡Excelente! No hay transacciones pendientes de revisión")
                return
            
            logger.info(f"📊 Encontradas {len(transactions)} transacciones para revisar")
            logger.info("")
            
            # Obtener subcategorías disponibles
            subcategories = get_all_subcategories()
            
            # Revisar cada transacción
            modified_count = 0
            for i, transaction in enumerate(transactions, 1):
                display_transaction(transaction, i, len(transactions))
                
                if review_transaction(transaction, subcategories):
                    # Guardar cambios
                    session.commit()
                    modified_count += 1
                
                # Preguntar si continuar
                if i < len(transactions):
                    print()
                    continue_review = input("¿Continuar con la siguiente? (S/n): ").strip().lower()
                    if continue_review == "n":
                        logger.info(f"\n⏸️  Revisión pausada. Progreso: {i}/{len(transactions)}")
                        break
            
            # Resumen final
            logger.info("")
            logger.success("=" * 80)
            logger.success("✅ REVISIÓN COMPLETADA")
            logger.success("=" * 80)
            logger.info(f"  Transacciones categorizadas: {modified_count}")
            
            remaining = (
                session.query(Transaction)
                .filter(Transaction.necesita_revision == True)  # noqa: E712
                .count()
            )
            logger.info(f"  Transacciones pendientes: {remaining}")
            logger.info("")
            
            if remaining == 0:
                logger.success("🎉 ¡Todas las transacciones están categorizadas!")
            else:
                logger.info(f"💡 Ejecuta 'make review' de nuevo para continuar")
    
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Revisión cancelada por el usuario")
    except Exception as e:
        logger.error(f"\n\n❌ Error en revisión: {e}")
        raise


if __name__ == "__main__":
    main()

