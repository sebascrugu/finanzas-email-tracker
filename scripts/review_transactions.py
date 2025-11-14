"""Script interactivo mejorado para revisar y categorizar transacciones."""

import sys
from pathlib import Path

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
    print("\n" + "=" * 80)
    print(f"📝 TRANSACCIÓN {index}/{total} - ID: {transaction.id[:8]}")
    print("=" * 80)
    print(f"🏪 Comercio:  {transaction.comercio}")
    print(f"💰 Monto:     {transaction.monto_display}")
    print(f"📅 Fecha:     {transaction.fecha_transaccion.strftime('%d/%m/%Y %H:%M')}")
    print(f"🏦 Banco:     {transaction.banco.value.upper()}")
    print(f"🔖 Tipo:      {transaction.tipo_transaccion.value}")

    if transaction.card:
        print(f"💳 Tarjeta:   {transaction.card.nombre_display}")

    if transaction.ciudad or transaction.pais:
        print(f"📍 Ubicación: {transaction.ciudad or 'N/A'}, {transaction.pais or 'N/A'}")

    print()

    # Mostrar sugerencia de IA
    if transaction.categoria_sugerida_por_ia:
        confianza = (
            f"({transaction.confianza_categoria}%)"
            if hasattr(transaction, "confianza_categoria")
            else ""
        )
        print(f"🤖 IA sugiere: {transaction.categoria_sugerida_por_ia} {confianza}")
    else:
        print("🤖 IA sugiere: Sin sugerencia")


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
    print("  a. ✅ Aceptar sugerencia IA")
    print("  0. ⏭️  Omitir / Revisar después")
    print()


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
    print("\n" + "─" * 80)
    print("⚠️  DETECTADA TRANSFERENCIA/SINPE")
    print("─" * 80)

    # Mostrar patrón si existe
    if patron:
        print(
            f"🔍 Patrón detectado: Últimas {patron['frecuencia']} veces "
            f"marcaste '{transaction.comercio}' como:"
        )
        tipo_nombre = {
            SpecialTransactionType.INTERMEDIATE: "Intermediaria (dinero que solo pasas)",
            SpecialTransactionType.SHARED: "Compartida (tu parte de algo grupal)",
            SpecialTransactionType.FAMILY_SUPPORT: "Ayuda familiar",
            SpecialTransactionType.LOAN_GIVEN: "Préstamo dado",
            SpecialTransactionType.REIMBURSEMENT: "Reembolso",
        }
        print(f"   → {tipo_nombre.get(patron['tipo_especial'], 'Otro')}")
        if patron["relacionada_con"]:
            print(f"   → {patron['relacionada_con']}")
        print()

    print("¿Qué tipo de transferencia es?")
    print()
    print("  1. 💵 Normal (tu gasto regular - SÍ cuenta en presupuesto)")
    print("  2. 🔄 Intermediaria (dinero que solo pasas - NO cuenta en presupuesto)")
    print("     Ej: Alquiler que pasas, compras para otros")
    print("  3. 🤝 Compartida (tu parte de algo grupal - SÍ cuenta en presupuesto)")
    print("     Ej: Fútbol semanal, pizza con amigos")
    print("  4. 👪 Ayuda familiar (das dinero a familiar - SÍ cuenta en presupuesto)")
    print("     Ej: Ayuda a abuela, mesada a hermano")
    print("  5. 💸 Préstamo dado (le prestas a alguien - SÍ cuenta en presupuesto)")
    print()

    # Sugerir el patrón si existe
    if patron:
        tipo_map = {
            SpecialTransactionType.INTERMEDIATE: "2",
            SpecialTransactionType.SHARED: "3",
            SpecialTransactionType.FAMILY_SUPPORT: "4",
            SpecialTransactionType.LOAN_GIVEN: "5",
        }
        sugerencia = tipo_map.get(patron["tipo_especial"], "1")
        print(f"💡 Sugerencia: {sugerencia} (basado en patrón detectado)")

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
        elif choice == "2":
            desc = input("Descripción (ej: 'Alquiler Nov-2025'): ").strip()
            return SpecialTransactionType.INTERMEDIATE, True, desc or None
        elif choice == "3":
            desc = input("Descripción (ej: 'Fútbol semanal'): ").strip()
            return SpecialTransactionType.SHARED, False, desc or None
        elif choice == "4":
            desc = input("Descripción (ej: 'Ayuda a abuela'): ").strip()
            return SpecialTransactionType.FAMILY_SUPPORT, False, desc or None
        elif choice == "5":
            desc = input("A quién prestaste: ").strip()
            return SpecialTransactionType.LOAN_GIVEN, False, desc or None
        else:
            print("❌ Opción inválida. Intenta de nuevo.")


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
            logger.success(f"✅ Categoría: {transaction.categoria_sugerida_por_ia}")
            break

        elif choice == "0":
            # Omitir
            logger.info("⏭️  Transacción omitida para revisar después")
            return False

        elif choice.isdigit():
            choice_num = int(choice)
            if 1 <= choice_num <= len(subcategories):
                # Asignar categoría seleccionada
                selected = subcategories[choice_num - 1]
                transaction.subcategory_id = selected.id
                transaction.categoria_sugerida_por_ia = selected.nombre_completo
                transaction.necesita_revision = False
                logger.success(f"✅ Categoría: {selected.nombre_completo}")
                break
            else:
                print("❌ Número fuera de rango. Intenta de nuevo.")
        else:
            print("❌ Opción inválida. Usa número, 'a' o '0'.")

    # PASO 2: Solo para transferencias/SINPEs, preguntar tipo especial
    if es_transferencia_o_sinpe(transaction):
        # Buscar patrón histórico
        patron = buscar_patron_historico(transaction.comercio, user_email, session)

        tipo_especial, excluir, relacionada = preguntar_tipo_especial(transaction, patron)

        transaction.tipo_especial = tipo_especial
        transaction.excluir_de_presupuesto = excluir
        transaction.relacionada_con = relacionada

        # Mensaje de confirmación
        if excluir:
            print("\n⚠️  Esta transacción NO contará en tu presupuesto (dinero intermediario)")
        elif tipo_especial:
            print("\n✅ Esta transacción SÍ contará en tu presupuesto (tu gasto)")

    return True


def main() -> None:
    """Función principal."""
    logger.info("=" * 80)
    logger.info("🔍 REVISIÓN INTELIGENTE DE TRANSACCIONES")
    logger.info("=" * 80)
    logger.info("")

    try:
        with get_session() as session:
            # Obtener usuario activo (simplificado - tomar el primero)
            from finanzas_tracker.models.user import User

            user = session.query(User).filter(User.activo == True).first()  # noqa: E712
            if not user:
                logger.error("❌ No hay usuario activo. Ejecuta 'make setup-user' primero.")
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
                logger.success("✅ ¡Excelente! No hay transacciones pendientes de revisión")
                return

            logger.info(f"📊 {len(transactions)} transacciones para revisar")
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
                logger.success("🎉 ¡Todas las transacciones están categorizadas!")
            else:
                logger.info("💡 Ejecuta 'make review' de nuevo para continuar")

    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Revisión cancelada por el usuario")
    except Exception as e:
        logger.error(f"\n\n❌ Error en revisión: {e}")
        raise


if __name__ == "__main__":
    main()
