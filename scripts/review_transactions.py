"""Script interactivo mejorado para revisar y categorizar transacciones."""

from pathlib import Path
import sys


# Agregar el directorio src al path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.enums import SpecialTransactionType, TransactionType
from finanzas_tracker.models.transaction import Transaction


logger = get_logger(__name__)


def display_transaction(transaction: Transaction, index: int, total: int) -> None:
    """
    Muestra información detallada de una transacción.

    Args:
        transaction: Transacción a mostrar
        index: Índice actual
        total: Total de transacciones
    """

    if transaction.card:
        pass

    if transaction.ciudad or transaction.pais:
        pass

    # Mostrar sugerencia de IA
    if transaction.categoria_sugerida_por_ia:
        (
            f"({transaction.confianza_categoria}%)"
            if hasattr(transaction, "confianza_categoria")
            else ""
        )
    else:
        pass


def get_all_subcategories() -> list[Subcategory]:
    """
    Obtiene todas las subcategorías disponibles, agrupadas por categoría.

    Returns:
        Lista de subcategorías ordenadas
    """
    with get_session() as session:
        categories = session.query(Category).all()

        all_subcats = []
        for cat in sorted(categories, key=lambda c: c.tipo.value):
            subcats = sorted(cat.subcategories, key=lambda s: s.nombre)
            all_subcats.extend(subcats)

        return all_subcats


def display_categories_menu(subcategories: list[Subcategory]) -> None:
    """
    Muestra el menú de categorías disponibles.

    Args:
        subcategories: Lista de subcategorías
    """

    current_category = None
    for _i, subcat in enumerate(subcategories, 1):
        # Si cambiamos de categoría principal, mostrar header
        if current_category != subcat.category.tipo:
            current_category = subcat.category.tipo
            subcat.category.nombre.upper()

        # Mostrar subcategoría


def es_transferencia_o_sinpe(transaction: Transaction) -> bool:
    """
    Determina si una transacción es transferencia o SINPE.

    Args:
        transaction: Transacción a evaluar

    Returns:
        bool: True si es transferencia o SINPE
    """
    return transaction.tipo_transaccion in [
        TransactionType.TRANSFER,
        TransactionType.SINPE,
    ]


def buscar_patron_historico(comercio: str, user_email: str, session) -> dict | None:
    """
    Busca patrones en transacciones anteriores del mismo comercio.

    Args:
        comercio: Nombre del comercio
        user_email: Email del usuario
        session: Sesión de base de datos

    Returns:
        dict con información del patrón o None
    """
    # Buscar transacciones anteriores del mismo comercio
    transacciones_anteriores = (
        session.query(Transaction)
        .filter(
            Transaction.user_email == user_email,
            Transaction.comercio == comercio,
            Transaction.tipo_especial.isnot(None),
        )
        .order_by(Transaction.fecha_transaccion.desc())
        .limit(3)
        .all()
    )

    if not transacciones_anteriores:
        return None

    # Si todas tienen el mismo tipo especial, es un patrón
    tipos = [tx.tipo_especial for tx in transacciones_anteriores]
    if len(set(tipos)) == 1:
        tx_ref = transacciones_anteriores[0]
        return {
            "tipo_especial": tx_ref.tipo_especial,
            "relacionada_con": tx_ref.relacionada_con,
            "excluir_presupuesto": tx_ref.excluir_de_presupuesto,
            "frecuencia": len(transacciones_anteriores),
        }

    return None


def preguntar_tipo_especial(
    transaction: Transaction, patron: dict | None
) -> tuple[SpecialTransactionType | None, bool, str | None]:
    """
    Pregunta al usuario sobre el tipo especial de transacción.

    Args:
        transaction: Transacción a clasificar
        patron: Patrón histórico detectado o None

    Returns:
        tuple: (tipo_especial, excluir_de_presupuesto, relacionada_con)
    """

    # Mostrar patrón si existe
    if patron and patron["relacionada_con"]:
        pass

    # Sugerir el patrón si existe
    if patron:
        tipo_map = {
            SpecialTransactionType.INTERMEDIATE: "2",
            SpecialTransactionType.SHARED: "3",
            SpecialTransactionType.FAMILY_SUPPORT: "4",
            SpecialTransactionType.LOAN_GIVEN: "5",
        }
        tipo_map.get(patron["tipo_especial"], "1")

    while True:
        choice = input("\nElige una opción (1-5) o Enter para aceptar sugerencia: ").strip()

        # Si hay patrón y presiona Enter, usar sugerencia
        if not choice and patron:
            tipo_map_reverse = {
                SpecialTransactionType.INTERMEDIATE: "2",
                SpecialTransactionType.SHARED: "3",
                SpecialTransactionType.FAMILY_SUPPORT: "4",
                SpecialTransactionType.LOAN_GIVEN: "5",
            }
            choice = tipo_map_reverse.get(patron["tipo_especial"], "1")

        if choice == "1":
            return None, False, None
        if choice == "2":
            desc = input("Descripción (ej: 'Alquiler Nov-2025'): ").strip()
            return SpecialTransactionType.INTERMEDIATE, True, desc or None
        if choice == "3":
            desc = input("Descripción (ej: 'Fútbol semanal'): ").strip()
            return SpecialTransactionType.SHARED, False, desc or None
        if choice == "4":
            desc = input("Descripción (ej: 'Ayuda a abuela'): ").strip()
            return SpecialTransactionType.FAMILY_SUPPORT, False, desc or None
        if choice == "5":
            desc = input("A quién prestaste: ").strip()
            return SpecialTransactionType.LOAN_GIVEN, False, desc or None


def review_transaction(
    transaction: Transaction,
    subcategories: list[Subcategory],
    user_email: str,
    session,
) -> bool:
    """
    Revisa una transacción interactivamente.

    Args:
        transaction: Transacción a revisar
        subcategories: Lista de subcategorías disponibles
        user_email: Email del usuario
        session: Sesión de base de datos

    Returns:
        bool: True si se modificó, False si se omitió
    """
    # PASO 1: Categorización
    while True:
        display_categories_menu(subcategories)

        choice = input("Elige opción: ").strip().lower()

        if choice == "a" and transaction.categoria_sugerida_por_ia:
            # Aceptar sugerencia
            if not transaction.subcategory_id:
                # Extraer nombre de subcategoría
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
            logger.success(f" Categoría: {transaction.categoria_sugerida_por_ia}")
            break

        if choice == "0":
            # Omitir
            logger.info("  Transacción omitida para revisar después")
            return False

        if choice.isdigit():
            choice_num = int(choice)
            if 1 <= choice_num <= len(subcategories):
                # Asignar categoría seleccionada
                selected = subcategories[choice_num - 1]
                transaction.subcategory_id = selected.id
                transaction.categoria_sugerida_por_ia = selected.nombre_completo
                transaction.necesita_revision = False
                logger.success(f" Categoría: {selected.nombre_completo}")
                break
        else:
            pass

    # PASO 2: Solo para transferencias/SINPEs, preguntar tipo especial
    if es_transferencia_o_sinpe(transaction):
        # Buscar patrón histórico
        patron = buscar_patron_historico(transaction.comercio, user_email, session)

        tipo_especial, excluir, relacionada = preguntar_tipo_especial(transaction, patron)

        transaction.tipo_especial = tipo_especial
        transaction.excluir_de_presupuesto = excluir
        transaction.relacionada_con = relacionada

        # Mensaje de confirmación
        if excluir or tipo_especial:
            pass

    return True


def main() -> None:
    """Función principal."""
    logger.info("=" * 80)
    logger.info(" REVISIÓN INTELIGENTE DE TRANSACCIONES")
    logger.info("=" * 80)
    logger.info("")

    try:
        with get_session() as session:
            # Obtener usuario activo (simplificado - tomar el primero)
            from finanzas_tracker.models.user import User

            user = session.query(User).filter(User.activo == True).first()  # noqa: E712
            if not user:
                logger.error(" No hay usuario activo. Ejecuta 'make setup-user' primero.")
                return

            # Obtener transacciones que necesitan revisión
            transactions = (
                session.query(Transaction)
                .filter(
                    Transaction.user_email == user.email,
                    Transaction.necesita_revision == True,  # noqa: E712
                )
                .order_by(Transaction.fecha_transaccion.desc())
                .all()
            )

            if not transactions:
                logger.success(" ¡Excelente! No hay transacciones pendientes de revisión")
                return

            logger.info(f" {len(transactions)} transacciones para revisar")
            logger.info("")

            # Obtener subcategorías disponibles
            subcategories = get_all_subcategories()

            # Revisar cada transacción
            modified_count = 0
            for i, transaction in enumerate(transactions, 1):
                display_transaction(transaction, i, len(transactions))

                if review_transaction(transaction, subcategories, user.email, session):
                    session.commit()
                    modified_count += 1

                # Preguntar si continuar
                if i < len(transactions):
                    continue_review = input("¿Continuar con la siguiente? (S/n): ").strip().lower()
                    if continue_review == "n":
                        logger.info(f"\n⏸️  Revisión pausada. Progreso: {i}/{len(transactions)}")
                        break

            # Resumen final
            logger.info("")
            logger.success("=" * 80)
            logger.success(" REVISIÓN COMPLETADA")
            logger.success("=" * 80)
            logger.info(f"  Categorizadas:  {modified_count}")

            remaining = (
                session.query(Transaction)
                .filter(
                    Transaction.user_email == user.email,
                    Transaction.necesita_revision == True,  # noqa: E712
                )
                .count()
            )
            logger.info(f"  Pendientes:     {remaining}")
            logger.info("")

            if remaining == 0:
                logger.success(" ¡Todas las transacciones están categorizadas!")
            else:
                logger.info(" Ejecuta 'make review' de nuevo para continuar")

    except KeyboardInterrupt:
        logger.warning("\n\n  Revisión cancelada por el usuario")
    except Exception as e:
        logger.error(f"\n\n Error en revisión: {e}")
        raise


if __name__ == "__main__":
    main()
